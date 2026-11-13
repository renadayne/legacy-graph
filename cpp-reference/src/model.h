// model.h: raw facts produced by the extractors (before name resolution)
// and the resolved graph used by queries.
#pragma once
#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace mg {

// ---------- raw facts ----------

struct RawCall {
  std::string qual;  // "X" for X::f(), "::" for ::f()
  std::string recv;  // receiver for obj.f() / p->f(); "this" for this->f()
  std::string recv_type;  // ((T*)p)->f()  -> T
  std::string recv_call;  // GetDocument()->f() -> GetDocument
  std::string name;
  int line = 0;
  bool member = false;
};

struct RawSend {  // SendMessage / PostMessage
  std::string api;
  std::vector<std::string> caps;  // ALL_CAPS identifiers found in the arguments
  int line = 0;
};

struct RawDDX {
  std::string macro, id, member;
  int line = 0;
};

struct RawFunc {
  int file = -1;
  std::string cls;  // owner class (in-class) or qualifier (out-of-line X::f)
  std::string ns;   // enclosing namespace path
  std::string name;
  int line = 0, end = 0;
  std::string sig;
  bool is_def = false;
  bool is_virtual = false;
  std::vector<RawCall> calls;
  std::vector<std::pair<std::string, int>> runtime;  // RUNTIME_CLASS(X)
  std::vector<RawSend> sends;
  std::vector<RawDDX> ddx;
  std::map<std::string, std::string> locals;  // variable -> type (params + locals)
};

struct RawClass {
  int file = -1;
  std::string name;  // possibly Outer::Inner
  std::string ns;
  std::vector<std::string> bases;
  int line = 0, end = 0;
  std::map<std::string, std::string> fields;  // member -> type
  std::string idd;                            // enum { IDD = IDD_X }
};

struct RawMsgEntry {
  std::string macro, kind, id, id2, handler;
  int line = 0;
};

struct RawMsgMap {
  int file = -1;
  std::string cls, base;
  int line = 0;
  std::vector<RawMsgEntry> entries;
};

struct RawInclude {
  int file = -1;
  std::string target;
  int line = 0;
};

struct RawDefine {
  int file = -1;
  std::string name, value;
  int line = 0;
};

struct RawDynamic {  // IMPLEMENT_DYNCREATE(C, B) ...
  int file = -1;
  std::string macro, cls, base;
  int line = 0;
};

struct RcControl {
  std::string type, text, id;
  int line = 0;
};

struct RcDialog {
  int file = -1;
  std::string id, caption;
  int line = 0;
  std::vector<RcControl> controls;
};

struct RcUiItem {
  int file = -1;
  std::string kind;   // menu | accel | toolbar
  std::string owner;  // resource id of the menu / accel table / toolbar
  std::string label;  // "File > Export..." | "Ctrl+E" | "button 3"
  std::string id;
  int line = 0;
};

struct RcString {
  int file = -1;
  std::string id, text;
  int line = 0;
};

struct SrcFile {
  std::string path;  // relative to root, forward slashes, UTF-8
  std::string encoding;
  uint64_t hash = 0;
  int lines = 0;
  bool brace_error = false;
  size_t skipped_tokens = 0;
};

struct RawData {
  std::vector<SrcFile> files;
  std::vector<RawFunc> funcs;
  std::vector<RawClass> classes;
  std::vector<RawMsgMap> msgmaps;
  std::vector<RawInclude> includes;
  std::vector<RawDefine> defines;
  std::vector<RawDynamic> dynamics;
  std::vector<RcDialog> dialogs;
  std::vector<RcUiItem> uiitems;
  std::vector<RcString> strings;
  std::map<std::string, int> unknown_macros;  // ON_xxx macros we could not interpret
};

// ---------- resolved graph ----------

struct Node {
  int id = 0;
  std::string kind;  // file | class | function | id | dialog | ui | external
  std::string name;  // short name
  std::string qname; // qualified name (Class::Method, ns::func)
  int file = -1, line = 0, end = 0;
  int owner = -1;     // class node for methods
  std::string flags;  // comma list: virtual, decl, framework-entry, msg-handler
  std::string sig;
  std::string extra;  // kind-specific text (caption, value, prompt, bases ...)
};

struct Edge {
  int src = 0, dst = 0;
  std::string kind;  // calls | inherits | overrides | handled_by | triggers | contains | binds |
                     // uses_dialog | runtime_class | sends | includes
  int file = -1, line = 0;
  std::string conf;   // exact | likely | ambiguous | heuristic | external
  std::string extra;  // e.g. "ON_COMMAND@CMainFrame", "DDX_Text m_strPath"
};

struct Graph {
  std::string root;
  int codepage = 1252;
  std::string created;
  std::vector<SrcFile> files;
  std::vector<Node> nodes;
  std::vector<Edge> edges;
  std::map<std::string, std::string> stats;
  std::vector<std::vector<int>> out, in;  // edge indices
  void build_adjacency();
};

}  // namespace mg
