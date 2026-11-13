// resolve.cpp: name resolution.
//
// Confidence levels on edges:
//   exact     - qualified call, call through `this`/class scope, or receiver of known type
//   likely    - only one function with that name exists in the codebase
//   ambiguous - several candidates; one edge per candidate (max 6)
//   heuristic - pattern based (SendMessage -> message handler)
//   external  - target not in the indexed code (MFC, Win32, CRT, 3rd party)
#include "resolve.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <functional>
#include <set>
#include <tuple>
#include <unordered_map>

#include "util.h"

namespace mg {

namespace {

const std::set<std::string>& framework_virtuals() {
  static const std::set<std::string> s = {
      "InitInstance", "ExitInstance", "OnIdle", "Run", "PreTranslateMessage", "OnInitDialog", "DoDataExchange",
      "OnOK", "OnCancel", "OnDraw", "OnInitialUpdate", "OnUpdate", "OnNewDocument", "OnOpenDocument",
      "OnSaveDocument", "OnCloseDocument", "DeleteContents", "Serialize", "PreCreateWindow", "OnCreateClient",
      "OnCmdMsg", "WindowProc", "DefWindowProc", "OnCommand", "OnNotify", "OnChildNotify", "PostNcDestroy",
      "OnPrepareDC", "OnPreparePrinting", "OnBeginPrinting", "OnEndPrinting", "OnPrint", "OnActivateView",
      "OnSetActive", "OnKillActive", "OnApply", "OnWizardNext", "OnWizardBack", "OnWizardFinish", "DrawItem",
      "MeasureItem", "CompareItem", "DeleteItem", "AssertValid", "Dump", "PreSubclassWindow", "OnToolHitTest",
      "OnAmbientProperty", "ContinueModal", "OnFileNew", "OnFileOpen", "SaveModified", "OnDragEnter",
      "OnDragOver", "OnDrop", "OnScroll", "OnScrollBy", "CreateDocument", "OnUpdateFrameTitle",
      "LoadFrame", "RecalcLayout", "OnShowViewMenu", "OnHelpInfo", "OnWndMsg", "OnDestroy"};
  return s;
}

std::string last_component(const std::string& q) {
  size_t p = q.rfind("::");
  return p == std::string::npos ? q : q.substr(p + 2);
}

void add_flag(Node& n, const std::string& f) {
  if (n.flags.empty()) n.flags = f;
  else if (("," + n.flags + ",").find("," + f + ",") == std::string::npos) n.flags += "," + f;
}

class Resolver {
 public:
  Resolver(const RawData& r, Graph& g) : r_(r), g_(g) {}

  void run() {
    g_.files = r_.files;
    make_file_nodes();
    make_classes();
    make_functions();
    make_inheritance();
    make_overrides();
    make_ids();
    make_msgmaps();
    make_resources();
    make_calls();
    make_includes();
    compute_stats();
  }

 private:
  const RawData& r_;
  Graph& g_;
  std::vector<int> file_node_;
  std::unordered_map<std::string, std::vector<int>> class_by_name_;  // simple name -> class nodes
  std::unordered_map<int, std::vector<std::string>> bases_;          // class node -> base names
  std::unordered_map<int, std::unordered_map<std::string, std::vector<int>>> methods_;  // class -> name -> fns
  std::unordered_map<std::string, std::vector<int>> free_by_name_;
  std::unordered_map<std::string, std::vector<int>> method_by_name_;
  std::unordered_map<std::string, int> ext_;   // external name -> node
  std::unordered_map<std::string, int> ids_;   // identifier -> id node
  std::unordered_map<std::string, int> dialogs_;
  std::set<std::string> msg_ids_;              // ids used in message maps as messages
  std::unordered_map<int, std::map<std::string, std::string>> fields_;  // class -> member -> type
  std::set<std::tuple<int, int, std::string>> edge_seen_;
  std::map<std::string, int> conf_count_;
  int handlers_total_ = 0, handlers_resolved_ = 0, handlers_framework_ = 0;
  int includes_total_ = 0, includes_resolved_ = 0;

  int add_node(Node n) {
    n.id = (int)g_.nodes.size();
    g_.nodes.push_back(n);
    return n.id;
  }

  void add_edge(int s, int d, const std::string& kind, int file, int line, const std::string& conf,
                const std::string& extra = "") {
    auto key = std::make_tuple(s, d, kind + "|" + extra);
    if (edge_seen_.count(key)) return;
    edge_seen_.insert(key);
    Edge e;
    e.src = s;
    e.dst = d;
    e.kind = kind;
    e.file = file;
    e.line = line;
    e.conf = conf;
    e.extra = extra;
    g_.edges.push_back(e);
  }

  int external(const std::string& name, const std::string& kind_hint = "") {
    auto it = ext_.find(name);
    if (it != ext_.end()) return it->second;
    Node n;
    n.kind = "external";
    n.name = last_component(name);
    n.qname = name;
    n.extra = kind_hint;
    int id = add_node(n);
    ext_[name] = id;
    return id;
  }

  int id_node(const std::string& name) {
    auto it = ids_.find(name);
    if (it != ids_.end()) return it->second;
    Node n;
    n.kind = "id";
    n.name = name;
    n.qname = name;
    int id = add_node(n);
    ids_[name] = id;
    return id;
  }

  void make_file_nodes() {
    file_node_.resize(r_.files.size());
    for (size_t i = 0; i < r_.files.size(); ++i) {
      Node n;
      n.kind = "file";
      n.name = r_.files[i].path;
      n.qname = r_.files[i].path;
      n.file = (int)i;
      n.line = 1;
      n.end = r_.files[i].lines;
      file_node_[i] = add_node(n);
    }
  }

  int find_class(const std::string& name) const {
    auto it = class_by_name_.find(last_component(name));
    if (it == class_by_name_.end() || it->second.empty()) return -1;
    if (it->second.size() > 1 && name.find("::") != std::string::npos) {
      for (int c : it->second)
        if (ends_with(g_.nodes[c].qname, name)) return c;
    }
    return it->second.front();
  }

  void make_classes() {
    for (const RawClass& c : r_.classes) {
      Node n;
      n.kind = "class";
      n.name = last_component(c.name);
      n.qname = c.ns.empty() ? c.name : c.ns + "::" + c.name;
      n.file = c.file;
      n.line = c.line;
      n.end = c.end ? c.end : c.line;
      n.extra = c.bases.empty() ? "" : "bases: " + join(c.bases, ", ");
      if (!c.idd.empty()) n.extra += (n.extra.empty() ? "" : "; ") + std::string("IDD=") + c.idd;
      int id = add_node(n);
      class_by_name_[n.name].push_back(id);
      bases_[id] = c.bases;
      fields_[id] = c.fields;
    }
    // IMPLEMENT_DYNCREATE etc. give base info when a header was not found
    for (const RawDynamic& d : r_.dynamics) {
      int c = find_class(d.cls);
      if (c < 0) {
        Node n;
        n.kind = "class";
        n.name = last_component(d.cls);
        n.qname = d.cls;
        n.file = d.file;
        n.line = d.line;
        n.end = d.line;
        n.extra = "bases: " + d.base + " (from " + d.macro + ")";
        c = add_node(n);
        class_by_name_[n.name].push_back(c);
      }
      if (bases_[c].empty()) bases_[c].push_back(d.base);
    }
  }

  void make_functions() {
    // definitions first, then declarations that have no definition
    std::set<std::pair<int, std::string>> defined;
    for (int pass = 0; pass < 2; ++pass) {
      for (size_t fi = 0; fi < r_.funcs.size(); ++fi) {
        const RawFunc& f = r_.funcs[fi];
        if ((pass == 0) != f.is_def) continue;
        int owner = f.cls.empty() ? -1 : find_class(f.cls);
        if (pass == 1 && defined.count({owner, f.name})) continue;
        Node n;
        n.kind = "function";
        n.name = f.name;
        if (owner >= 0) n.qname = g_.nodes[owner].qname + "::" + f.name;
        else {
          std::string q = f.cls.empty() ? f.ns : (f.ns.empty() ? f.cls : f.ns + "::" + f.cls);
          n.qname = q.empty() ? f.name : q + "::" + f.name;
        }
        n.file = f.file;
        n.line = f.line;
        n.end = f.end;
        n.owner = owner;
        n.sig = f.sig;
        if (f.is_virtual) add_flag(n, "virtual");
        if (!f.is_def) add_flag(n, "decl");
        int id = add_node(n);
        func_node_[fi] = id;
        if (owner >= 0) {
          methods_[owner][f.name].push_back(id);
          method_by_name_[f.name].push_back(id);
          if (pass == 0) defined.insert({owner, f.name});
        } else {
          free_by_name_[f.name].push_back(id);
        }
      }
    }
  }
  std::unordered_map<size_t, int> func_node_;  // raw func index -> node

  // All known ancestor classes (BFS) and external base names reached.
  void ancestors(int cls, std::vector<int>& known, std::vector<std::string>& ext) const {
    std::set<int> seen{cls};
    std::vector<int> queue{cls};
    std::set<std::string> ext_seen;
    for (size_t qi = 0; qi < queue.size(); ++qi) {
      auto it = bases_.find(queue[qi]);
      if (it == bases_.end()) continue;
      for (const std::string& b : it->second) {
        int bc = find_class(b);
        if (bc >= 0) {
          if (!seen.count(bc)) {
            seen.insert(bc);
            known.push_back(bc);
            queue.push_back(bc);
          }
        } else if (!ext_seen.count(b)) {
          ext_seen.insert(b);
          ext.push_back(b);
        }
      }
    }
  }

  std::vector<int> find_method(int cls, const std::string& name, bool search_bases = true) const {
    auto it = methods_.find(cls);
    if (it != methods_.end()) {
      auto m = it->second.find(name);
      if (m != it->second.end()) return m->second;
    }
    if (!search_bases) return {};
    std::vector<int> known;
    std::vector<std::string> ext;
    ancestors(cls, known, ext);
    for (int a : known) {
      auto r = find_method(a, name, false);
      if (!r.empty()) return r;
    }
    return {};
  }

  std::string first_external_base(int cls) const {
    std::vector<int> known;
    std::vector<std::string> ext;
    ancestors(cls, known, ext);
    return ext.empty() ? "" : ext.front();
  }

  void make_inheritance() {
    for (auto& kv : bases_) {
      for (const std::string& b : kv.second) {
        int bc = find_class(b);
        const Node& n = g_.nodes[kv.first];
        if (bc >= 0) add_edge(kv.first, bc, "inherits", n.file, n.line, "exact");
        else add_edge(kv.first, external(b, "class"), "inherits", n.file, n.line, "external");
      }
    }
  }

  void make_overrides() {
    for (auto& cm : methods_) {
      std::vector<int> known;
      std::vector<std::string> ext;
      ancestors(cm.first, known, ext);
      for (auto& nm : cm.second) {
        bool found = false;
        for (int a : known) {
          auto r = find_method(a, nm.first, false);
          if (!r.empty()) {
            for (int fn : nm.second) add_edge(fn, r.front(), "overrides", g_.nodes[fn].file, g_.nodes[fn].line, "exact");
            found = true;
            break;
          }
        }
        if (!ext.empty() && framework_virtuals().count(nm.first)) {
          for (int fn : nm.second) {
            add_flag(g_.nodes[fn], "framework-entry");
            if (!found)
              add_edge(fn, external(ext.front() + "::" + nm.first, "framework"), "overrides", g_.nodes[fn].file,
                       g_.nodes[fn].line, "external");
          }
        }
      }
    }
  }

  void make_ids() {
    for (const RawDefine& d : r_.defines) {
      const std::string& nm = d.name;
      bool resource_like = starts_with(nm, "ID") && nm.size() > 3 && (nm.find('_') != std::string::npos) &&
                           is_all_caps_ident(nm);
      bool msg_like = starts_with(nm, "WM_") || starts_with(nm, "UWM_") || nm.find("_MSG") != std::string::npos;
      if (!resource_like && !msg_like) continue;
      int id = id_node(nm);
      Node& n = g_.nodes[id];
      if (n.file < 0) {
        n.file = d.file;
        n.line = d.line;
        n.extra = "value=" + d.value;
      }
    }
    for (const RcString& s : r_.strings) {
      int id = id_node(s.id);
      Node& n = g_.nodes[id];
      n.extra += (n.extra.empty() ? "" : "; ") + std::string("text=\"") + s.text + "\"";
      if (n.file < 0) {
        n.file = s.file;
        n.line = s.line;
      }
    }
  }

  static bool parse_int(const std::string& v, long& out) {
    std::string s = trim(v);
    while (!s.empty() && s.front() == '(' && s.back() == ')') s = trim(s.substr(1, s.size() - 2));
    if (s.empty()) return false;
    char* end = nullptr;
    long x = std::strtol(s.c_str(), &end, 0);
    if (end && *end == '\0') {
      out = x;
      return true;
    }
    return false;
  }

  void make_msgmaps() {
    for (const RawMsgMap& mm : r_.msgmaps) {
      int cls = find_class(mm.cls);
      for (const RawMsgEntry& e : mm.entries) {
        ++handlers_total_;
        std::string hname = last_component(e.handler);
        std::string hqual = e.handler.size() > hname.size() ? e.handler.substr(0, e.handler.size() - hname.size() - 2) : "";
        int hcls = cls;
        if (!hqual.empty()) {
          int q = find_class(hqual);
          if (q < 0) {  // handler implemented by an MFC base class, e.g. &CWinApp::OnFileNew
            ++handlers_framework_;
            int x = external(hqual + "::" + hname, "framework-handler");
            std::string extra = e.macro + "@" + mm.cls;
            add_edge(id_node(e.id), x, "handled_by", mm.file, e.line, "external", extra);
            if (!e.id2.empty()) add_edge(id_node(e.id2), x, "handled_by", mm.file, e.line, "external", extra);
            continue;
          }
          hcls = q;
        }
        std::vector<int> h = hcls >= 0 ? find_method(hcls, hname) : std::vector<int>{};
        if (h.empty()) {
          auto it = method_by_name_.find(hname);
          if (hcls < 0 && it != method_by_name_.end() && it->second.size() == 1) h = it->second;
        }
        if (e.kind == "message") msg_ids_.insert(e.id);
        std::vector<std::string> idnames{e.id};
        if (!e.id2.empty()) {
          idnames.push_back(e.id2);
          long lo = 0, hi = 0;  // ids inside a numeric range
          auto a = ids_.find(e.id), b = ids_.find(e.id2);
          if (a != ids_.end() && b != ids_.end() && parse_int(value_of(a->second), lo) &&
              parse_int(value_of(b->second), hi)) {
            for (auto& kv : ids_) {
              long v = 0;
              if (parse_int(value_of(kv.second), v) && v > lo && v < hi) idnames.push_back(kv.first);
            }
          }
        }
        std::string extra = e.macro + "@" + mm.cls;
        if (h.empty()) {
          int x = external(mm.cls + "::" + hname, "unresolved-handler");
          for (auto& idn : idnames) add_edge(id_node(idn), x, "handled_by", mm.file, e.line, "external", extra);
          continue;
        }
        ++handlers_resolved_;
        for (int fn : h) {
          add_flag(g_.nodes[fn], e.kind == "update_ui" ? "update-ui-handler" : "msg-handler");
          for (auto& idn : idnames) add_edge(id_node(idn), fn, "handled_by", mm.file, e.line, "exact", extra);
        }
      }
    }
  }

  std::string value_of(int id_node_index) const {
    const std::string& x = g_.nodes[id_node_index].extra;
    if (!starts_with(x, "value=")) return "";
    size_t semi = x.find(';');
    return x.substr(6, semi == std::string::npos ? std::string::npos : semi - 6);
  }

  void make_resources() {
    for (const RcDialog& d : r_.dialogs) {
      Node n;
      n.kind = "dialog";
      n.name = d.id;
      n.qname = d.id;
      n.file = d.file;
      n.line = d.line;
      n.extra = d.caption.empty() ? "" : "caption=\"" + d.caption + "\"";
      int dn = add_node(n);
      dialogs_[d.id] = dn;
      for (const RcControl& c : d.controls) {
        if (c.id == "IDC_STATIC" || c.id == "-1") continue;
        std::string extra = c.type + (c.text.empty() ? "" : " \"" + c.text + "\"");
        add_edge(dn, id_node(c.id), "contains", d.file, c.line, "exact", extra);
      }
    }
    for (const RcUiItem& u : r_.uiitems) {
      Node n;
      n.kind = "ui";
      if (u.kind == "menu") n.name = "Menu " + u.owner + ": " + u.label;
      else if (u.kind == "accel") n.name = "Accelerator " + u.label;
      else n.name = "Toolbar " + u.owner + " " + u.label;
      n.qname = n.name;
      n.file = u.file;
      n.line = u.line;
      n.extra = u.kind;
      int un = add_node(n);
      add_edge(un, id_node(u.id), "triggers", u.file, u.line, "exact");
    }
    // dialog class <-> dialog template, DDX bindings
    for (auto& kv : class_by_name_) {
      for (int c : kv.second) {
        const std::string& ex = g_.nodes[c].extra;
        size_t p = ex.find("IDD=");
        if (p == std::string::npos) continue;
        std::string idd = ex.substr(p + 4);
        auto d = dialogs_.find(idd);
        add_edge(c, d != dialogs_.end() ? d->second : id_node(idd), "uses_dialog", g_.nodes[c].file,
                 g_.nodes[c].line, "exact");
      }
    }
  }

  // receiver variable -> class node (locals, then fields of the class and its ancestors)
  int receiver_class(const RawFunc& f, int owner, const std::string& recv) const {
    if (recv.empty()) return -1;
    auto lt = f.locals.find(recv);
    if (lt != f.locals.end()) return find_class(lt->second);
    if (owner < 0) return -1;
    std::vector<int> chain{owner};
    std::vector<std::string> ext;
    ancestors(owner, chain, ext);
    for (int c : chain) {
      auto fm = fields_.find(c);
      if (fm == fields_.end()) continue;
      auto ft = fm->second.find(recv);
      if (ft != fm->second.end()) return find_class(ft->second);
    }
    return -1;
  }

  std::string receiver_type_name(const RawFunc& f, int owner, const std::string& recv) const {
    auto lt = f.locals.find(recv);
    if (lt != f.locals.end()) return lt->second;
    if (owner < 0) return "";
    auto fm = fields_.find(owner);
    if (fm != fields_.end()) {
      auto ft = fm->second.find(recv);
      if (ft != fm->second.end()) return ft->second;
    }
    return "";
  }

  // GetDocument()->X(): find the called function and read a known class from its return type.
  int return_class_of(const std::string& fn, int owner) const {
    std::vector<int> cands = owner >= 0 ? find_method(owner, fn) : std::vector<int>{};
    if (cands.empty()) {
      auto fr = free_by_name_.find(fn);
      if (fr != free_by_name_.end() && fr->second.size() == 1) cands = fr->second;
    }
    if (cands.empty()) return -1;
    const std::string& sig = g_.nodes[cands[0]].sig;
    size_t pos = sig.find(fn + "(");
    if (pos == std::string::npos) pos = sig.find(fn + " (");
    if (pos == std::string::npos) return -1;
    std::string ret = sig.substr(0, pos);  // "CLegacyDoc* CLegacyView::"
    while (true) {                         // drop trailing "Class::" qualifiers
      std::string t = trim(ret);
      if (!ends_with(t, "::")) break;
      t = t.substr(0, t.size() - 2);
      size_t b = t.size();
      while (b > 0 && (std::isalnum((unsigned char)t[b - 1]) || t[b - 1] == '_')) --b;
      ret = t.substr(0, b);
    }
    std::string cur;
    for (size_t i = 0; i <= ret.size(); ++i) {
      char ch = i < ret.size() ? ret[i] : ' ';
      if (std::isalnum((unsigned char)ch) || ch == '_') {
        cur += ch;
        continue;
      }
      if (!cur.empty()) {
        int c = find_class(cur);
        if (c >= 0) return c;
        cur.clear();
      }
    }
    return -1;
  }

  void link(int src, const std::vector<int>& targets, const std::string& conf, int file, int line) {
    if (targets.size() == 1) {
      add_edge(src, targets[0], "calls", file, line, conf);
      conf_count_[conf]++;
      return;
    }
    size_t lim = std::min<size_t>(targets.size(), 6);
    for (size_t i = 0; i < lim; ++i) add_edge(src, targets[i], "calls", file, line, "ambiguous");
    conf_count_["ambiguous"]++;
  }

  void make_calls() {
    for (size_t fi = 0; fi < r_.funcs.size(); ++fi) {
      const RawFunc& f = r_.funcs[fi];
      if (!f.is_def) continue;
      auto itn = func_node_.find(fi);
      if (itn == func_node_.end()) continue;
      int src = itn->second;
      int owner = g_.nodes[src].owner;
      for (const RawCall& c : f.calls) {
        if (!c.qual.empty() && c.qual != "::") {
          int qc = find_class(c.qual);
          if (qc >= 0) {
            auto m = find_method(qc, c.name);
            if (!m.empty()) {
              link(src, m, "exact", f.file, c.line);
              continue;
            }
            std::string eb = first_external_base(qc);
            add_edge(src, external((eb.empty() ? c.qual : eb) + "::" + c.name), "calls", f.file, c.line, "external");
            conf_count_["external"]++;
            continue;
          }
          // namespace-qualified free function
          std::vector<int> exact;
          auto fr = free_by_name_.find(c.name);
          if (fr != free_by_name_.end())
            for (int fn : fr->second)
              if (ends_with(g_.nodes[fn].qname, c.qual + "::" + c.name)) exact.push_back(fn);
          if (!exact.empty()) {
            link(src, exact, "exact", f.file, c.line);
            continue;
          }
          add_edge(src, external(c.qual + "::" + c.name), "calls", f.file, c.line, "external");
          conf_count_["external"]++;
          continue;
        }
        if (c.qual == "::") {
          auto fr = free_by_name_.find(c.name);
          if (fr != free_by_name_.end() && !fr->second.empty()) {
            link(src, fr->second, fr->second.size() == 1 ? "likely" : "ambiguous", f.file, c.line);
            continue;
          }
          add_edge(src, external("::" + c.name), "calls", f.file, c.line, "external");
          conf_count_["external"]++;
          continue;
        }
        if (c.member) {
          int rc = -1;
          if (c.recv == "this") rc = owner;
          else if (!c.recv_type.empty()) rc = find_class(c.recv_type);
          else if (!c.recv_call.empty()) rc = return_class_of(c.recv_call, owner);
          else rc = receiver_class(f, owner, c.recv);
          if (rc >= 0) {
            auto m = find_method(rc, c.name);
            if (!m.empty()) {
              link(src, m, "exact", f.file, c.line);
              continue;
            }
            std::string eb = first_external_base(rc);
            add_edge(src, external((eb.empty() ? g_.nodes[rc].name : eb) + "::" + c.name), "calls", f.file, c.line,
                     "external");
            conf_count_["external"]++;
            continue;
          }
          std::string tname = !c.recv_type.empty() ? c.recv_type
                              : c.recv.empty()     ? ""
                                                   : receiver_type_name(f, owner, c.recv);
          if (!tname.empty()) {  // receiver of a known but external type (CString, CListCtrl ...)
            add_edge(src, external(tname + "::" + c.name), "calls", f.file, c.line, "external");
            conf_count_["external"]++;
            continue;
          }
          auto mb = method_by_name_.find(c.name);
          if (mb != method_by_name_.end() && !mb->second.empty()) {
            link(src, mb->second, mb->second.size() == 1 ? "likely" : "ambiguous", f.file, c.line);
            continue;
          }
          add_edge(src, external("?::" + c.name), "calls", f.file, c.line, "external");
          conf_count_["external"]++;
          continue;
        }
        // plain call: class scope first, then free functions
        if (owner >= 0) {
          auto m = find_method(owner, c.name);
          if (!m.empty()) {
            link(src, m, "exact", f.file, c.line);
            continue;
          }
        }
        auto fr = free_by_name_.find(c.name);
        if (fr != free_by_name_.end() && !fr->second.empty()) {
          // prefer same namespace
          std::vector<int> same;
          for (int fn : fr->second)
            if (!f.ns.empty() && starts_with(g_.nodes[fn].qname, f.ns + "::")) same.push_back(fn);
          if (!same.empty()) link(src, same, same.size() == 1 ? "exact" : "ambiguous", f.file, c.line);
          else link(src, fr->second, fr->second.size() == 1 ? "likely" : "ambiguous", f.file, c.line);
          continue;
        }
        // Afx*, CRT (lower-case) and _xxx names are global functions, not inherited members
        bool global_like = starts_with(c.name, "Afx") || c.name[0] == '_' ||
                           std::islower((unsigned char)c.name[0]);
        std::string eb = (owner >= 0 && !global_like) ? first_external_base(owner) : "";
        add_edge(src, external(eb.empty() ? c.name : eb + "::" + c.name), "calls", f.file, c.line, "external");
        conf_count_["external"]++;
      }
      for (auto& rc : f.runtime) {
        int c = find_class(rc.first);
        add_edge(src, c >= 0 ? c : external(rc.first, "class"), "runtime_class", f.file, rc.second,
                 c >= 0 ? "exact" : "external");
      }
      for (const RawSend& s : f.sends) {
        for (const std::string& cap : s.caps) {
          if (msg_ids_.count(cap) || starts_with(cap, "WM_") || ids_.count(cap)) {
            add_edge(src, id_node(cap), "sends", f.file, s.line, "heuristic", s.api);
            break;
          }
        }
      }
      if (!f.ddx.empty() && owner >= 0) {
        for (const RawDDX& d : f.ddx)
          add_edge(owner, id_node(d.id), "binds", f.file, d.line, "exact", d.macro + " " + d.member);
      }
    }
  }

  void make_includes() {
    // index files by lower-case basename
    std::unordered_map<std::string, std::vector<int>> by_base;
    for (size_t i = 0; i < r_.files.size(); ++i) {
      std::string p = lower(r_.files[i].path);
      size_t s = p.rfind('/');
      by_base[s == std::string::npos ? p : p.substr(s + 1)].push_back((int)i);
    }
    for (const RawInclude& inc : r_.includes) {
      ++includes_total_;
      std::string t = lower(replace_all(inc.target, "\\", "/"));
      size_t s = t.rfind('/');
      std::string base = s == std::string::npos ? t : t.substr(s + 1);
      auto it = by_base.find(base);
      if (it == by_base.end()) continue;
      int best = -1;
      // prefer same directory, then any path ending with the include text
      std::string from = lower(r_.files[inc.file].path);
      size_t fs = from.rfind('/');
      std::string dir = fs == std::string::npos ? "" : from.substr(0, fs + 1);
      for (int cand : it->second) {
        std::string cp = lower(r_.files[cand].path);
        if (cp == dir + t) {
          best = cand;
          break;
        }
        if (best < 0 && ends_with(cp, t)) best = cand;
      }
      if (best < 0) best = it->second.front();
      ++includes_resolved_;
      add_edge(file_node_[inc.file], file_node_[best], "includes", inc.file, inc.line, "exact");
    }
  }

  void compute_stats() {
    auto& s = g_.stats;
    int cpp = 0, hdr = 0, rc = 0, brace = 0;
    size_t skipped = 0;
    std::map<std::string, int> enc;
    for (const SrcFile& f : r_.files) {
      std::string p = lower(f.path);
      if (ends_with(p, ".rc") || ends_with(p, ".rc2") || ends_with(p, ".dlg")) ++rc;
      else if (ends_with(p, ".h") || ends_with(p, ".hpp") || ends_with(p, ".hxx") || ends_with(p, ".hh") ||
               ends_with(p, ".inl"))
        ++hdr;
      else ++cpp;
      if (f.brace_error) ++brace;
      skipped += f.skipped_tokens;
      std::string e = f.encoding;
      enc[e]++;
    }
    s["files.total"] = std::to_string(r_.files.size());
    s["files.source"] = std::to_string(cpp);
    s["files.header"] = std::to_string(hdr);
    s["files.resource"] = std::to_string(rc);
    s["files.brace_error"] = std::to_string(brace);
    s["tokens.inactive_skipped"] = std::to_string(skipped);
    for (auto& kv : enc) s["encoding." + kv.first] = std::to_string(kv.second);
    int classes = 0, defs = 0, decls = 0, fw = 0, handlers = 0;
    for (const Node& n : g_.nodes) {
      if (n.kind == "class") ++classes;
      if (n.kind == "function") {
        if (n.flags.find("decl") != std::string::npos) ++decls;
        else ++defs;
        if (n.flags.find("framework-entry") != std::string::npos) ++fw;
        if (n.flags.find("msg-handler") != std::string::npos) ++handlers;
      }
    }
    s["classes"] = std::to_string(classes);
    s["functions.defined"] = std::to_string(defs);
    s["functions.decl_only"] = std::to_string(decls);
    s["functions.framework_entry"] = std::to_string(fw);
    s["functions.msg_handler"] = std::to_string(handlers);
    int total_calls = 0;
    for (auto& kv : conf_count_) total_calls += kv.second;
    s["calls.total"] = std::to_string(total_calls);
    for (auto& kv : conf_count_) s["calls." + kv.first] = std::to_string(kv.second);
    s["msgmap.entries"] = std::to_string(handlers_total_);
    s["msgmap.resolved"] = std::to_string(handlers_resolved_);
    s["msgmap.framework"] = std::to_string(handlers_framework_);
    s["msgmap.unresolved"] = std::to_string(handlers_total_ - handlers_resolved_ - handlers_framework_);
    int unknown = 0;
    for (auto& kv : r_.unknown_macros) unknown += kv.second;
    s["msgmap.unknown_macros"] = std::to_string(unknown);
    s["msgmap.unknown_macro_kinds"] = std::to_string(r_.unknown_macros.size());
    std::vector<std::string> names;
    for (auto& kv : r_.unknown_macros) names.push_back(kv.first + "=" + std::to_string(kv.second));
    s["msgmap.unknown_macro_names"] = join(names, ",");
    int menu = 0, accel = 0, tb = 0;
    for (auto& u : r_.uiitems) {
      if (u.kind == "menu") ++menu;
      else if (u.kind == "accel") ++accel;
      else ++tb;
    }
    s["rc.dialogs"] = std::to_string(r_.dialogs.size());
    s["rc.menu_items"] = std::to_string(menu);
    s["rc.accelerators"] = std::to_string(accel);
    s["rc.toolbar_buttons"] = std::to_string(tb);
    s["rc.strings"] = std::to_string(r_.strings.size());
    s["includes.total"] = std::to_string(includes_total_);
    s["includes.resolved"] = std::to_string(includes_resolved_);
    s["nodes"] = std::to_string(g_.nodes.size());
    s["edges"] = std::to_string(g_.edges.size());
  }
};

}  // namespace

void resolve(const RawData& raw, Graph& g) {
  Resolver r(raw, g);
  r.run();
  g.build_adjacency();
}

void Graph::build_adjacency() {
  out.assign(nodes.size(), {});
  in.assign(nodes.size(), {});
  for (size_t i = 0; i < edges.size(); ++i) {
    out[edges[i].src].push_back((int)i);
    in[edges[i].dst].push_back((int)i);
  }
}

}  // namespace mg
