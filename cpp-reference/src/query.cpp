#include "query.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <set>
#include <sstream>

#include "encoding.h"
#include "util.h"

namespace mg {

namespace {

std::string loc(const Graph& g, const Node& n) {
  if (n.file < 0 || n.file >= (int)g.files.size()) return "";
  return g.files[n.file].path + ":" + std::to_string(n.line);
}

std::string label(const Graph& g, const Node& n) {
  if (n.kind == "external") return n.qname + " [external]";
  if (n.kind == "function" || n.kind == "class") {
    std::string l = n.qname;
    std::string lc = loc(g, n);
    if (!lc.empty()) l += "  " + lc;
    return l;
  }
  if (n.kind == "dialog") return "Dialog " + n.name + (n.extra.empty() ? "" : " " + n.extra);
  if (n.kind == "id") return n.name;
  return n.name;
}

bool last_component_eq(const std::string& a, const std::string& b) {
  size_t p = a.rfind("::");
  return (p == std::string::npos ? a : a.substr(p + 2)) == b;
}

bool has_flag(const Node& n, const std::string& f) { return ("," + n.flags + ",").find("," + f + ",") != std::string::npos; }

std::vector<int> find_symbols(const Graph& g, const std::string& q_in, bool include_classes = true) {
  std::string q = trim(q_in);
  std::vector<int> r;
  auto ok_kind = [&](const Node& n) {
    return n.kind == "function" || (include_classes && n.kind == "class");
  };
  for (const Node& n : g.nodes)
    if (ok_kind(n) && n.qname == q) r.push_back(n.id);
  if (!r.empty()) return r;
  if (q.find("::") != std::string::npos) {
    for (const Node& n : g.nodes)
      if (ok_kind(n) && ends_with(n.qname, "::" + q)) r.push_back(n.id);
    if (!r.empty()) return r;
  }
  for (const Node& n : g.nodes)
    if (ok_kind(n) && n.name == q) r.push_back(n.id);
  if (!r.empty()) return r;
  for (const Node& n : g.nodes)
    if (ok_kind(n) && (iequals(n.name, q) || iequals(n.qname, q))) r.push_back(n.id);
  return r;
}

std::string ambiguity_text(const Graph& g, const std::string& q, const std::vector<int>& m) {
  std::ostringstream o;
  if (m.empty()) {
    o << "No symbol matches '" << q << "'. Try: search " << q << "\n";
    return o.str();
  }
  o << m.size() << " symbols match '" << q << "'. Use a qualified name:\n";
  for (size_t i = 0; i < m.size() && i < 20; ++i) o << "  " << label(g, g.nodes[m[i]]) << "\n";
  return o.str();
}

// Resolves to one node or returns false with an explanation.
bool one_symbol(const Graph& g, const std::string& q, int& out, std::string& msg, bool include_classes = true) {
  auto m = find_symbols(g, q, include_classes);
  if (m.size() == 1) {
    out = m[0];
    return true;
  }
  // prefer a single definition over declarations
  std::vector<int> defs;
  for (int x : m)
    if (!has_flag(g.nodes[x], "decl")) defs.push_back(x);
  if (defs.size() == 1) {
    out = defs[0];
    return true;
  }
  msg = ambiguity_text(g, q, m);
  return false;
}

std::vector<std::string> read_lines(const Graph& g, int file) {
  std::vector<std::string> lines;
  if (file < 0 || file >= (int)g.files.size()) return lines;
  fs::path p = u8_to_path(g.root) / u8_to_path(g.files[file].path);
  std::string bytes;
  if (!read_file_bytes(p, bytes)) return lines;
  std::string text = decode_with_label(bytes, g.files[file].encoding, g.codepage);
  std::string cur;
  for (char c : text) {
    if (c == '\n') {
      if (!cur.empty() && cur.back() == '\r') cur.pop_back();
      lines.push_back(cur);
      cur.clear();
    } else {
      cur += c;
    }
  }
  lines.push_back(cur);
  return lines;
}

std::string snippet(const Graph& g, const Node& n, int max_lines) {
  auto lines = read_lines(g, n.file);
  if (lines.empty()) return "  (source not readable from " + g.root + ")\n";
  int b = std::max(1, n.line), e = std::max(n.end, n.line);
  if (e > (int)lines.size()) e = (int)lines.size();
  std::ostringstream o;
  int shown = 0;
  for (int i = b; i <= e; ++i) {
    if (shown >= max_lines) {
      o << "  ... (" << (e - i + 1) << " more lines, " << g.files[n.file].path << ":" << i << "-" << e << ")\n";
      break;
    }
    o << i << " | " << lines[i - 1] << "\n";
    ++shown;
  }
  return o.str();
}

const std::set<std::string> kForward = {"calls", "runtime_class", "sends", "handled_by"};
const std::set<std::string> kReverse = {"calls", "handled_by", "triggers", "sends"};

void tree(const Graph& g, int node, int depth, int max_depth, bool reverse, const std::string& indent,
          std::set<int>& visited, std::ostringstream& o, int& budget) {
  if (depth >= max_depth || budget <= 0) return;
  const auto& lst = reverse ? g.in[node] : g.out[node];
  std::vector<std::string> externals;
  std::set<int> shown;
  for (int ei : lst) {
    const Edge& e = g.edges[ei];
    const std::set<std::string>& kinds = reverse ? kReverse : kForward;
    if (!kinds.count(e.kind)) continue;
    if (!reverse && e.kind == "handled_by" && g.nodes[node].kind != "id") continue;
    int other = reverse ? e.src : e.dst;
    if (shown.count(other)) continue;
    shown.insert(other);
    const Node& on = g.nodes[other];
    if (on.kind == "external") {
      externals.push_back(on.qname + (e.kind == "runtime_class" ? " (RUNTIME_CLASS)" : ""));
      continue;
    }
    if (budget-- <= 0) {
      o << indent << "... (truncated)\n";
      return;
    }
    std::string arrow = reverse ? "<- " : "-> ";
    std::string tag;
    if (e.kind == "handled_by") tag = " [" + split(e.extra, '@')[0] + "]";
    else if (e.kind == "sends") tag = " [" + e.extra + " heuristic]";
    else if (e.kind == "triggers") tag = "";
    else if (e.kind == "runtime_class") tag = " [RUNTIME_CLASS]";
    else if (e.conf != "exact") tag = " [" + e.conf + "]";
    std::string call_loc;
    if (e.kind == "calls" && e.file >= 0)
      call_loc = "  (call at " + g.files[e.file].path + ":" + std::to_string(e.line) + ")";
    if (visited.count(other)) {
      o << indent << arrow << label(g, on) << tag << "  (see above)\n";
      continue;
    }
    o << indent << arrow << label(g, on) << tag << (reverse ? call_loc : "") << "\n";
    visited.insert(other);
    tree(g, other, depth + 1, max_depth, reverse, indent + "   ", visited, o, budget);
  }
  if (!externals.empty()) {
    std::sort(externals.begin(), externals.end());
    externals.erase(std::unique(externals.begin(), externals.end()), externals.end());
    std::string line = indent + (reverse ? "<- " : "-> ") + "external: ";
    size_t lim = std::min<size_t>(externals.size(), 15);
    for (size_t i = 0; i < lim; ++i) line += (i ? ", " : "") + externals[i];
    if (externals.size() > lim) line += ", +" + std::to_string(externals.size() - lim) + " more";
    o << line << "\n";
  }
}

// UI entry points (menu/accel/toolbar) and dialog controls that reach a function.
std::vector<std::string> ui_entries(const Graph& g, int fn) {
  std::vector<std::string> r;
  for (int ei : g.in[fn]) {
    const Edge& e = g.edges[ei];
    if (e.kind != "handled_by") continue;
    const Node& idn = g.nodes[e.src];
    std::string macro = split(e.extra, '@')[0];
    std::vector<std::string> ui;
    for (int ej : g.in[idn.id]) {
      const Edge& t = g.edges[ej];
      if (t.kind == "triggers") ui.push_back(g.nodes[t.src].name);
      if (t.kind == "contains") ui.push_back(g.nodes[t.src].name + " control " + t.extra);
    }
    std::string s = idn.name + " via " + macro;
    if (!ui.empty()) s += "  <- " + join(ui, " | ");
    r.push_back(s);
  }
  return r;
}

std::string pct(const std::string& a, const std::string& b) {
  double x = std::atof(a.c_str()), y = std::atof(b.c_str());
  if (y <= 0) return "-";
  char buf[32];
  std::snprintf(buf, sizeof buf, "%.1f%%", 100.0 * x / y);
  return buf;
}

std::string stat(const Graph& g, const std::string& k) {
  auto it = g.stats.find(k);
  return it == g.stats.end() ? "0" : it->second;
}

}  // namespace

std::string q_search(const Graph& g, const std::string& query, int limit) {
  std::ostringstream o;
  struct Hit {
    int score;
    int id;
  };
  std::vector<Hit> hits;
  for (const Node& n : g.nodes) {
    if (n.kind == "file") continue;
    int score = 0;
    if (n.name == query || n.qname == query) score = 100;
    else if (iequals(n.name, query)) score = 90;
    else if (icontains(n.qname, query)) score = 60;
    else if (icontains(n.extra, query)) score = 40;
    if (!score) continue;
    if (n.kind == "function" || n.kind == "class") score += 5;
    if (n.kind == "external") score -= 30;
    hits.push_back({score, n.id});
  }
  std::stable_sort(hits.begin(), hits.end(), [](const Hit& a, const Hit& b) { return a.score > b.score; });
  if (hits.empty()) return "No match for '" + query + "'.\n";
  o << hits.size() << " match(es) for '" << query << "'" << (hits.size() > (size_t)limit ? " (showing top)" : "")
    << ":\n";
  for (size_t i = 0; i < hits.size() && (int)i < limit; ++i) {
    const Node& n = g.nodes[hits[i].id];
    o << "  [" << n.kind << "] " << label(g, n);
    if ((n.kind == "id" || n.kind == "ui") && !n.extra.empty() && n.kind != "ui") o << "  " << n.extra;
    if (n.kind == "id" && n.file >= 0) o << "  " << loc(g, n);
    o << "\n";
  }
  return o.str();
}

std::string q_node(const Graph& g, const std::string& symbol, bool with_code, int max_code_lines) {
  int id;
  std::string msg;
  if (!one_symbol(g, symbol, id, msg)) return msg;
  const Node& n = g.nodes[id];
  std::ostringstream o;
  o << "[" << n.kind << "] " << n.qname << "  " << loc(g, n);
  if (n.end > n.line) o << "-" << n.end;
  o << "\n";
  if (!n.sig.empty()) o << "  sig: " << n.sig << "\n";
  if (!n.flags.empty()) o << "  flags: " << n.flags << "\n";
  if (!n.extra.empty()) o << "  " << n.extra << "\n";
  if (n.kind == "class") {
    std::vector<std::string> methods, derived;
    for (const Node& m : g.nodes)
      if (m.kind == "function" && m.owner == id) methods.push_back(m.name + (has_flag(m, "decl") ? "(decl)" : ""));
    for (int ei : g.in[id])
      if (g.edges[ei].kind == "inherits") derived.push_back(g.nodes[g.edges[ei].src].qname);
    o << "  methods (" << methods.size() << "): " << join(methods, ", ") << "\n";
    if (!derived.empty()) o << "  derived: " << join(derived, ", ") << "\n";
    for (int ei : g.out[id])
      if (g.edges[ei].kind == "uses_dialog") o << "  dialog: " << label(g, g.nodes[g.edges[ei].dst]) << "\n";
  }
  if (n.kind == "function") {
    auto ui = ui_entries(g, id);
    for (auto& s : ui) o << "  triggered by: " << s << "\n";
    int callers = 0, callees = 0, ext = 0;
    for (int ei : g.in[id])
      if (g.edges[ei].kind == "calls") ++callers;
    for (int ei : g.out[id])
      if (g.edges[ei].kind == "calls") {
        if (g.nodes[g.edges[ei].dst].kind == "external") ++ext;
        else ++callees;
      }
    for (int ei : g.out[id])
      if (g.edges[ei].kind == "overrides") o << "  overrides: " << g.nodes[g.edges[ei].dst].qname << "\n";
    o << "  callers: " << callers << ", callees: " << callees << " in code + " << ext << " external\n";
  }
  if (with_code && (n.kind == "function" || n.kind == "class")) {
    o << "---\n" << snippet(g, n, max_code_lines);
  }
  return o.str();
}

std::string q_callers(const Graph& g, const std::string& symbol, int depth) {
  int id;
  std::string msg;
  if (!one_symbol(g, symbol, id, msg, false)) return msg;
  std::ostringstream o;
  o << label(g, g.nodes[id]) << "\n";
  std::set<int> visited{id};
  int budget = 150;
  tree(g, id, 0, depth, true, "  ", visited, o, budget);
  if (g.in[id].empty()) o << "  (no callers found";
  if (g.in[id].empty())
    o << (has_flag(g.nodes[id], "framework-entry") ? "; called by the MFC framework)\n" : ")\n");
  return o.str();
}

std::string q_callees(const Graph& g, const std::string& symbol, int depth) {
  int id;
  std::string msg;
  if (!one_symbol(g, symbol, id, msg, false)) return msg;
  std::ostringstream o;
  o << label(g, g.nodes[id]) << "\n";
  std::set<int> visited{id};
  int budget = 150;
  tree(g, id, 0, depth, false, "  ", visited, o, budget);
  return o.str();
}

std::string q_impact(const Graph& g, const std::string& symbol, int depth) {
  int id;
  std::string msg;
  if (!one_symbol(g, symbol, id, msg, false)) return msg;
  std::map<int, int> dist{{id, 0}};
  std::vector<int> queue{id};
  for (size_t qi = 0; qi < queue.size(); ++qi) {
    int cur = queue[qi];
    if (dist[cur] >= depth) continue;
    for (int ei : g.in[cur]) {
      const Edge& e = g.edges[ei];
      if (!kReverse.count(e.kind) && e.kind != "contains") continue;
      if (dist.count(e.src)) continue;
      dist[e.src] = dist[cur] + 1;
      queue.push_back(e.src);
    }
  }
  std::vector<std::pair<int, int>> fns;
  std::vector<std::string> ui;
  std::set<std::string> files;
  for (auto& kv : dist) {
    const Node& n = g.nodes[kv.first];
    if (kv.first == id) continue;
    if (n.kind == "function") {
      fns.push_back({kv.second, kv.first});
      if (n.file >= 0) files.insert(g.files[n.file].path);
    } else if (n.kind == "ui" || n.kind == "dialog") {
      ui.push_back(n.kind == "dialog" ? label(g, n) : n.name);
    }
  }
  std::sort(fns.begin(), fns.end());
  std::ostringstream o;
  o << "Impact of changing " << label(g, g.nodes[id]) << "  (reverse depth <= " << depth << ")\n";
  o << "functions affected (" << fns.size() << "):\n";
  for (size_t i = 0; i < fns.size() && i < 60; ++i)
    o << "  " << fns[i].first << "  " << label(g, g.nodes[fns[i].second]) << "\n";
  if (fns.size() > 60) o << "  ... +" << (fns.size() - 60) << " more\n";
  o << "UI entry points (" << ui.size() << "):\n";
  for (auto& s : ui) o << "  " << s << "\n";
  for (int ei : g.out[id])
    if (g.edges[ei].kind == "overrides")
      o << "note: overrides " << g.nodes[g.edges[ei].dst].qname << " (also reached by virtual dispatch)\n";
  if (has_flag(g.nodes[id], "framework-entry")) o << "note: called by the MFC framework\n";
  o << "files (" << files.size() << "): " << join(std::vector<std::string>(files.begin(), files.end()), ", ") << "\n";
  return o.str();
}

std::string q_trace(const Graph& g, const std::string& query, int depth) {
  std::ostringstream o;
  std::vector<int> ids;
  std::set<int> seen_ids;
  std::vector<int> dialogs;
  // 1) menu / accelerator / toolbar captions
  for (const Node& n : g.nodes) {
    if (n.kind == "ui" && icontains(n.name, query)) {
      for (int ei : g.out[n.id])
        if (g.edges[ei].kind == "triggers" && !seen_ids.count(g.edges[ei].dst)) {
          seen_ids.insert(g.edges[ei].dst);
          ids.push_back(g.edges[ei].dst);
        }
    }
  }
  // 2) exact identifier / dialog
  for (const Node& n : g.nodes) {
    if (n.kind == "id" && iequals(n.name, query) && !seen_ids.count(n.id)) {
      seen_ids.insert(n.id);
      ids.push_back(n.id);
    }
    if (n.kind == "dialog" && (iequals(n.name, query) || icontains(n.extra, query))) dialogs.push_back(n.id);
  }
  if (ids.empty() && dialogs.empty())
    return "Nothing matches '" + query + "' (menu caption, accelerator, command ID or dialog ID).\n";

  for (int idn : ids) {
    const Node& n = g.nodes[idn];
    bool is_dialog_id = false;
    for (int dn : dialogs)
      if (g.nodes[dn].name == n.name) is_dialog_id = true;
    bool has_links = false;
    for (int ei : g.out[idn])
      if (g.edges[ei].kind == "handled_by") has_links = true;
    if (is_dialog_id && !has_links) continue;  // shown below as a dialog
    o << "== " << n.name;
    if (!n.extra.empty()) o << "  (" << n.extra << ")";
    o << "\n";
    for (int ei : g.in[idn]) {
      const Edge& e = g.edges[ei];
      if (e.kind == "triggers") o << "  UI: " << g.nodes[e.src].name << "  " << loc(g, g.nodes[e.src]) << "\n";
      if (e.kind == "contains") o << "  UI: " << g.nodes[e.src].name << " control " << e.extra << "\n";
      if (e.kind == "sends")
        o << "  sent by: " << label(g, g.nodes[e.src]) << " [" << e.extra << " heuristic]\n";
    }
    bool any = false;
    for (int ei : g.out[idn]) {
      const Edge& e = g.edges[ei];
      if (e.kind != "handled_by") continue;
      any = true;
      std::string macro = split(e.extra, '@')[0];
      o << "  handler [" << macro << "]: " << label(g, g.nodes[e.dst]) << "\n";
      if (g.nodes[e.dst].kind == "function" && macro.find("UPDATE_COMMAND_UI") == std::string::npos) {
        std::set<int> visited{e.dst};
        int budget = 60;
        tree(g, e.dst, 0, depth, false, "     ", visited, o, budget);
      }
    }
    if (!any) o << "  (no message-map handler found in indexed code; may be handled by MFC itself)\n";
  }
  for (int dn : dialogs) {
    const Node& d = g.nodes[dn];
    o << "== " << label(g, d) << "  " << loc(g, d) << "\n";
    int cls = -1;
    for (int ei : g.in[dn])
      if (g.edges[ei].kind == "uses_dialog") cls = g.edges[ei].src;
    if (cls >= 0) o << "  class: " << label(g, g.nodes[cls]) << "\n";
    std::map<int, std::string> ddx;
    if (cls >= 0)
      for (int ei : g.out[cls])
        if (g.edges[ei].kind == "binds") ddx[g.edges[ei].dst] += (ddx[g.edges[ei].dst].empty() ? "" : ", ") + g.edges[ei].extra;
    o << "  controls:\n";
    for (int ei : g.out[dn]) {
      const Edge& e = g.edges[ei];
      if (e.kind != "contains") continue;
      const Node& c = g.nodes[e.dst];
      o << "    " << c.name << "  " << e.extra;
      auto dd = ddx.find(c.id);
      if (dd != ddx.end()) o << "  <-> " << dd->second;
      for (int ej : g.out[c.id]) {
        const Edge& h = g.edges[ej];
        if (h.kind != "handled_by") continue;
        const Node& hn = g.nodes[h.dst];
        if (cls >= 0 && hn.owner >= 0 && hn.owner != cls) continue;
        o << "  -> " << hn.name << " [" << split(h.extra, '@')[0] << "]";
      }
      o << "\n";
    }
    if (cls >= 0) {
      std::vector<std::string> fw;
      for (const Node& m : g.nodes)
        if (m.kind == "function" && m.owner == cls && has_flag(m, "framework-entry")) fw.push_back(m.name);
      if (!fw.empty()) o << "  framework entry points: " << join(fw, ", ") << "\n";
    }
  }
  return o.str();
}

std::string q_msgmap(const Graph& g, const std::string& cls) {
  int id;
  auto m = find_symbols(g, cls, true);
  std::vector<int> classes;
  for (int x : m)
    if (g.nodes[x].kind == "class") classes.push_back(x);
  if (classes.size() != 1) return classes.empty() ? "No class '" + cls + "'.\n" : ambiguity_text(g, cls, classes);
  id = classes[0];
  const Node& c = g.nodes[id];
  std::ostringstream o;
  o << "Message map of " << c.qname << "\n";
  int count = 0;
  for (const Edge& e : g.edges) {
    if (e.kind != "handled_by") continue;
    auto parts = split(e.extra, '@');
    if (parts.size() < 2 || last_component_eq(parts[1], c.name) == false) continue;
    const Node& h = g.nodes[e.dst];
    o << "  " << parts[0] << "(" << g.nodes[e.src].name << ") -> " << h.qname
      << (h.kind != "external"                ? "  " + loc(g, h)
          : h.extra == "framework-handler"    ? "  [implemented by MFC base class]"
                                              : "  [handler not found]")
      << "\n";
    ++count;
  }
  if (!count) o << "  (no message map entries)\n";
  return o.str();
}

std::string q_context(const Graph& g, const std::string& symbol, int max_code_lines) {
  int id;
  std::string msg;
  if (!one_symbol(g, symbol, id, msg)) return msg;
  const Node& n = g.nodes[id];
  std::ostringstream o;
  o << "# Context: " << n.qname << "\n\n";
  o << "## Definition (" << loc(g, n) << (n.end > n.line ? "-" + std::to_string(n.end) : "") << ")\n";
  if (!n.flags.empty()) o << "flags: " << n.flags << "\n";
  o << "```cpp\n" << snippet(g, n, max_code_lines) << "```\n";
  if (n.kind == "function") {
    auto ui = ui_entries(g, id);
    if (!ui.empty()) {
      o << "\n## Triggered by\n";
      for (auto& s : ui) o << "- " << s << "\n";
    }
    o << "\n## Called by\n";
    int c = 0;
    for (int ei : g.in[id]) {
      const Edge& e = g.edges[ei];
      if (e.kind != "calls") continue;
      o << "- " << label(g, g.nodes[e.src]) << (e.conf != "exact" ? " [" + e.conf + "]" : "") << "\n";
      ++c;
    }
    if (!c) o << "- (none in indexed code" << (has_flag(n, "framework-entry") ? "; MFC framework calls it" : "") << ")\n";
    o << "\n## Calls\n";
    std::vector<std::string> ext;
    for (int ei : g.out[id]) {
      const Edge& e = g.edges[ei];
      if (e.kind != "calls" && e.kind != "sends" && e.kind != "runtime_class") continue;
      const Node& t = g.nodes[e.dst];
      if (t.kind == "external") {
        ext.push_back(t.qname);
        continue;
      }
      o << "- " << label(g, t);
      if (!t.sig.empty()) o << "  `" << t.sig << "`";
      if (e.kind == "sends") o << " [" << e.extra << " -> message handler, heuristic]";
      else if (e.conf != "exact") o << " [" << e.conf << "]";
      o << "\n";
    }
    if (!ext.empty()) {
      std::sort(ext.begin(), ext.end());
      ext.erase(std::unique(ext.begin(), ext.end()), ext.end());
      o << "- external: " << join(ext, ", ") << "\n";
    }
    for (int ei : g.out[id])
      if (g.edges[ei].kind == "overrides") o << "\nOverrides " << g.nodes[g.edges[ei].dst].qname << "\n";
  }
  return o.str();
}

std::string q_diagnose(const Graph& g, bool show_names) {
  std::ostringstream o;
  o << "mfcgraph diagnose (counts only; no names, no code)\n";
  o << "files: " << stat(g, "files.total") << "  (source " << stat(g, "files.source") << ", header "
    << stat(g, "files.header") << ", resource " << stat(g, "files.resource") << ")\n";
  o << "encodings:";
  for (auto& kv : g.stats)
    if (starts_with(kv.first, "encoding.")) o << "  " << kv.first.substr(9) << "=" << kv.second;
  o << "\n";
  o << "files with unbalanced braces: " << stat(g, "files.brace_error") << "\n";
  o << "tokens skipped in inactive #if branches: " << stat(g, "tokens.inactive_skipped") << "\n";
  o << "classes: " << stat(g, "classes") << "\n";
  o << "functions: defined " << stat(g, "functions.defined") << ", declared-only " << stat(g, "functions.decl_only")
    << ", framework entry points " << stat(g, "functions.framework_entry") << ", message handlers "
    << stat(g, "functions.msg_handler") << "\n";
  std::string total = stat(g, "calls.total");
  o << "call sites: " << total << "  exact " << pct(stat(g, "calls.exact"), total) << ", likely "
    << pct(stat(g, "calls.likely"), total) << ", ambiguous " << pct(stat(g, "calls.ambiguous"), total)
    << ", external " << pct(stat(g, "calls.external"), total) << "\n";
  o << "message-map entries: " << stat(g, "msgmap.entries") << "  handler found in code "
    << pct(stat(g, "msgmap.resolved"), stat(g, "msgmap.entries")) << ", handled by an MFC base class "
    << pct(stat(g, "msgmap.framework"), stat(g, "msgmap.entries")) << ", NOT FOUND "
    << pct(stat(g, "msgmap.unresolved"), stat(g, "msgmap.entries")) << "\n";
  o << "unrecognised ON_ macros: " << stat(g, "msgmap.unknown_macros") << " uses of "
    << stat(g, "msgmap.unknown_macro_kinds") << " kinds";
  if (show_names) o << "  [" << stat(g, "msgmap.unknown_macro_names") << "]";
  else o << "  (add --show-names to list them)";
  o << "\n";
  o << "resources: dialogs " << stat(g, "rc.dialogs") << ", menu items " << stat(g, "rc.menu_items")
    << ", accelerators " << stat(g, "rc.accelerators") << ", toolbar buttons " << stat(g, "rc.toolbar_buttons")
    << ", strings " << stat(g, "rc.strings") << "\n";
  o << "#include resolved inside the tree: " << pct(stat(g, "includes.resolved"), stat(g, "includes.total"))
    << " of " << stat(g, "includes.total") << " (system/MFC headers are expected to be unresolved)\n";
  o << "graph: " << stat(g, "nodes") << " nodes, " << stat(g, "edges") << " edges\n";
  return o.str();
}

std::string q_status(const Graph& g, const std::string& index_path) {
  std::ostringstream o;
  o << "index: " << index_path << "\nroot: " << g.root << "\ncreated: " << g.created << "\ncodepage: " << g.codepage
    << "\nfiles: " << stat(g, "files.total") << ", classes: " << stat(g, "classes")
    << ", functions: " << stat(g, "functions.defined") << ", message-map entries: " << stat(g, "msgmap.entries")
    << ", dialogs: " << stat(g, "rc.dialogs") << ", menu items: " << stat(g, "rc.menu_items") << "\n";
  return o.str();
}

}  // namespace mg
