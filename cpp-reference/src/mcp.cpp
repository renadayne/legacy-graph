#include "mcp.h"

#include <iostream>
#include <string>

#include "index.h"
#include "json.h"
#include "query.h"
#include "util.h"

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace mg {

namespace {

const size_t kMaxToolOutput = 16000;  // characters; keeps agent context small

struct ToolDef {
  const char* name;
  const char* description;
  const char* schema;  // JSON Schema for arguments
};

const ToolDef kTools[] = {
    {"mfc_search",
     "Find classes, functions, command/resource IDs, menu captions and dialog captions by (part of) name. "
     "Use this first when you only know a word.",
     R"({"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer"}},"required":["query"]})"},
    {"mfc_node",
     "Show one symbol: location, signature, flags (framework entry, message handler), UI triggers, "
     "caller/callee counts and its source code.",
     R"({"type":"object","properties":{"symbol":{"type":"string","description":"Class, Class::Method or function"},"code":{"type":"boolean"},"max_code_lines":{"type":"integer"}},"required":["symbol"]})"},
    {"mfc_callers",
     "Who calls this function, including MFC message-map routing up to menu items / accelerators / toolbar buttons.",
     R"({"type":"object","properties":{"symbol":{"type":"string"},"depth":{"type":"integer"}},"required":["symbol"]})"},
    {"mfc_callees",
     "What this function calls (tree). External MFC/Win32 calls are summarised on one line.",
     R"({"type":"object","properties":{"symbol":{"type":"string"},"depth":{"type":"integer"}},"required":["symbol"]})"},
    {"mfc_impact",
     "Blast radius of changing a function: affected functions, UI entry points and files.",
     R"({"type":"object","properties":{"symbol":{"type":"string"},"depth":{"type":"integer"}},"required":["symbol"]})"},
    {"mfc_trace",
     "Trace a UI action to code: menu caption (e.g. 'Export'), accelerator, command ID (ID_FILE_EXPORT) or "
     "dialog ID (IDD_EXPORT) -> message-map handler -> what it calls. For dialogs: controls, DDX members, handlers.",
     R"({"type":"object","properties":{"query":{"type":"string"},"depth":{"type":"integer"}},"required":["query"]})"},
    {"mfc_context",
     "Compact context pack for a symbol (code + callers + callees + UI triggers) in Markdown. "
     "Prefer this over reading whole files.",
     R"({"type":"object","properties":{"symbol":{"type":"string"},"max_code_lines":{"type":"integer"}},"required":["symbol"]})"},
    {"mfc_msgmap", "List the MFC message map of a class (macro, ID/message, handler, location).",
     R"({"type":"object","properties":{"class":{"type":"string"}},"required":["class"]})"},
    {"mfc_status", "Index status: root, creation time, counts.", R"({"type":"object","properties":{}})"},
};

std::string clamp(std::string s) {
  if (s.size() <= kMaxToolOutput) return s;
  size_t cut = kMaxToolOutput;
  while (cut > 0 && ((unsigned char)s[cut] & 0xC0) == 0x80) --cut;  // do not split UTF-8
  return s.substr(0, cut) + "\n... (output truncated; narrow the query)\n";
}

std::string run_tool(const Graph& g, const std::string& index_path, const std::string& name, const JVal& a,
                     bool& is_error) {
  is_error = false;
  if (name == "mfc_search") return q_search(g, a.str("query"), a.integer("limit", 30));
  if (name == "mfc_node") return q_node(g, a.str("symbol"), a.boolean("code", true), a.integer("max_code_lines", 80));
  if (name == "mfc_callers") return q_callers(g, a.str("symbol"), a.integer("depth", 5));
  if (name == "mfc_callees") return q_callees(g, a.str("symbol"), a.integer("depth", 2));
  if (name == "mfc_impact") return q_impact(g, a.str("symbol"), a.integer("depth", 5));
  if (name == "mfc_trace") return q_trace(g, a.str("query"), a.integer("depth", 2));
  if (name == "mfc_context") return q_context(g, a.str("symbol"), a.integer("max_code_lines", 80));
  if (name == "mfc_msgmap") return q_msgmap(g, a.str("class"));
  if (name == "mfc_status") return q_status(g, index_path);
  is_error = true;
  return "unknown tool: " + name;
}

void send(const std::string& json) {
  std::cout << json << "\n";
  std::cout.flush();
}

void send_result(const JVal* id, const std::string& result_json) {
  send("{\"jsonrpc\":\"2.0\",\"id\":" + (id ? json_dump(*id) : std::string("null")) + ",\"result\":" + result_json + "}");
}

void send_error(const JVal* id, int code, const std::string& msg) {
  send("{\"jsonrpc\":\"2.0\",\"id\":" + (id ? json_dump(*id) : std::string("null")) + ",\"error\":{\"code\":" +
       std::to_string(code) + ",\"message\":" + json_quote(msg) + "}}");
}

}  // namespace

int run_mcp_server(const std::string& index_path) {
#ifdef _WIN32
  _setmode(_fileno(stdin), _O_BINARY);
  _setmode(_fileno(stdout), _O_BINARY);
#endif
  Graph g;
  std::string err;
  bool loaded = load_graph(index_path, g, err);
  if (!loaded) std::cerr << "mfcgraph: " << err << "\n";  // stderr is shown in the IDE's MCP log

  std::string line;
  while (std::getline(std::cin, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (trim(line).empty()) continue;
    JVal req;
    std::string perr;
    if (!json_parse(line, req, perr)) {
      send_error(nullptr, -32700, "parse error: " + perr);
      continue;
    }
    const JVal* id = req.get("id");
    std::string method = req.str("method");
    const JVal* params = req.get("params");
    static const JVal empty_obj = [] {
      JVal v;
      v.t = JVal::Obj;
      return v;
    }();
    const JVal& p = params ? *params : empty_obj;

    if (!id) continue;  // notification (e.g. notifications/initialized): no reply

    if (method == "initialize") {
      std::string ver = p.str("protocolVersion", "2025-06-18");
      send_result(id, "{\"protocolVersion\":" + json_quote(ver) +
                          ",\"capabilities\":{\"tools\":{\"listChanged\":false}},"
                          "\"serverInfo\":{\"name\":\"mfcgraph\",\"version\":\"0.1.0\"},"
                          "\"instructions\":" +
                          json_quote("Offline code graph of a C++/MFC codebase. Start with mfc_search or mfc_trace "
                                     "(menu caption / command ID / dialog ID), then mfc_context for the symbol you "
                                     "need. Prefer these tools over reading whole files.") +
                          "}");
    } else if (method == "ping") {
      send_result(id, "{}");
    } else if (method == "tools/list") {
      std::string r = "{\"tools\":[";
      bool first = true;
      for (const ToolDef& t : kTools) {
        r += (first ? "" : ",");
        first = false;
        r += "{\"name\":" + json_quote(t.name) + ",\"description\":" + json_quote(t.description) +
             ",\"inputSchema\":" + t.schema + "}";
      }
      r += "]}";
      send_result(id, r);
    } else if (method == "tools/call") {
      std::string name = p.str("name");
      const JVal* args = p.get("arguments");
      bool is_error = false;
      std::string text;
      if (!loaded) {
        is_error = true;
        text = "Index not available: " + err;
      } else {
        text = run_tool(g, index_path, name, args ? *args : empty_obj, is_error);
      }
      send_result(id, "{\"content\":[{\"type\":\"text\",\"text\":" + json_quote(clamp(text)) +
                          "}],\"isError\":" + (is_error ? "true" : "false") + "}");
    } else if (method == "resources/list") {
      send_result(id, "{\"resources\":[]}");
    } else if (method == "prompts/list") {
      send_result(id, "{\"prompts\":[]}");
    } else {
      send_error(id, -32601, "method not found: " + method);
    }
  }
  return 0;
}

}  // namespace mg
