// extract_cpp.cpp: heuristic, error-tolerant C++ structure extraction with MFC awareness.
//
// This is NOT a compiler front end. It walks the token stream keeping a
// namespace/class scope stack, recognises function definitions by the
// "name ( ... ) [qualifiers] {" shape, and scans function bodies for calls.
// MFC constructs (message maps, DDX, RUNTIME_CLASS, IDD, IMPLEMENT_*) are
// recognised explicitly because ordinary parsers treat them as opaque macros.
#include <cctype>
#include <map>
#include <set>
#include <string>

#include "extract.h"
#include "util.h"

namespace mg {

namespace {

const std::set<std::string>& keywords() {
  static const std::set<std::string> k = {
      "if", "else", "for", "while", "do", "switch", "case", "default", "return", "sizeof", "catch", "try",
      "throw", "new", "delete", "typeid", "alignof", "alignas", "decltype", "static_cast", "dynamic_cast",
      "reinterpret_cast", "const_cast", "goto", "break", "continue", "using", "typedef", "template",
      "typename", "namespace", "class", "struct", "union", "enum", "public", "private", "protected",
      "virtual", "static", "const", "volatile", "inline", "explicit", "friend", "operator", "this",
      "__declspec", "__try", "__except", "__finally", "__leave", "__stdcall", "__cdecl", "__fastcall",
      "extern", "register", "auto", "mutable", "unsigned", "signed", "int", "char", "short", "long",
      "float", "double", "bool", "void", "wchar_t", "noexcept", "override", "final", "nullptr", "true",
      "false", "defined", "static_assert", "afx_msg", "__forceinline", "__inline", "constexpr", "and",
      "or", "not", "co_return", "co_await", "__super"};
  return k;
}

// Function-like macros / intrinsics that are noise in a call graph.
const std::set<std::string>& call_stoplist() {
  static const std::set<std::string> s = {
      "_T", "TEXT", "_TEXT", "ASSERT", "VERIFY", "TRACE", "TRACE0", "TRACE1", "TRACE2", "TRACE3",
      "ASSERT_VALID", "ASSERT_KINDOF", "RGB", "MAKELONG", "MAKEWORD", "LOWORD", "HIWORD", "LOBYTE",
      "HIBYTE", "MAKEWPARAM", "MAKELPARAM", "MAKEINTRESOURCE", "_countof", "ARRAYSIZE", "UNREFERENCED_PARAMETER",
      "UNUSED", "UNUSED_ALWAYS", "DEBUG_NEW", "ENSURE", "ENSURE_VALID", "ATLASSERT", "ATLTRACE", "SUCCEEDED",
      "FAILED", "_ASSERTE", "_ASSERT", "min", "max", "__min", "__max", "STATIC_DOWNCAST", "DYNAMIC_DOWNCAST",
      "offsetof", "va_start", "va_end", "va_arg", "AFX_MANAGE_STATE", "METHOD_PROLOGUE", "USES_CONVERSION"};
  return s;
}

const std::set<std::string>& send_apis() {
  static const std::set<std::string> s = {
      "SendMessage", "PostMessage", "SendMessageW", "SendMessageA", "PostMessageW", "PostMessageA",
      "SendNotifyMessage", "PostThreadMessage", "SendDlgItemMessage", "SendMessageTimeout",
      "SendMessageToDescendants"};
  return s;
}

std::string join_tokens(const std::vector<Token>& t, int b, int e) {  // [b, e)
  std::string r;
  for (int i = b; i < e; ++i) {
    const Token& k = t[i];
    std::string s = k.k == TK::String ? "\"" + k.s + "\"" : k.k == TK::Char ? "'" + k.s + "'" : k.s;
    if (!r.empty()) {
      char last = r.back();
      bool word_l = std::isalnum((unsigned char)last) || last == '_' || last == '"';
      bool word_r = !s.empty() && (std::isalnum((unsigned char)s[0]) || s[0] == '_' || s[0] == '"');
      if ((word_l && word_r) || s == "*" || s == "&" || last == ',') r += ' ';
    }
    r += s;
  }
  return r;
}

class CppWalker {
 public:
  CppWalker(const std::vector<Token>& toks, int file, RawData& out) : t_(toks), file_(file), out_(out) {}

  void run() {
    n_ = (int)t_.size();
    compute_matches();
    int i = 0, stmt = 0;
    while (i < n_) {
      if (!scopes_.empty() && i == scopes_.back().close) {
        if (scopes_.back().kind == kClass && scopes_.back().cls >= 0)
          out_.classes[scopes_.back().cls].end = t_[i].line;
        scopes_.pop_back();
        ++i;
        stmt = i;
        continue;
      }
      const Token& k = t_[i];
      if (k.k == TK::PP) {
        handle_pp(k);
        ++i;
        stmt = i;
        continue;
      }
      if (k.k == TK::Punct && k.s == ";") {
        if (in_class() && i > stmt) analyze_field(stmt, i);
        ++i;
        stmt = i;
        continue;
      }
      if (k.k == TK::Punct && k.s == "}") {  // stray / unmatched
        ++i;
        stmt = i;
        continue;
      }
      if (k.k == TK::Ident) {
        const std::string& s = k.s;
        if (s == "template" && next_is(i, "<")) {
          i = skip_angles(i + 1);
          continue;
        }
        if (s == "namespace") {
          if (i > 0 && t_[i - 1].s == "using") {
            i = skip_to_semicolon(i);
            continue;
          }
          int j = i + 1;
          std::string name;
          while (j < n_ && (t_[j].k == TK::Ident || t_[j].s == "::")) name += t_[j++].s;
          if (j < n_ && t_[j].s == "{" && bm_[j] > 0) {
            scopes_.push_back({kNamespace, name, -1, bm_[j]});
            i = j + 1;
            stmt = i;
            continue;
          }
          i = skip_to_semicolon(i);
          continue;
        }
        if (s == "extern" && i + 2 < n_ && t_[i + 1].k == TK::String && t_[i + 2].s == "{" && bm_[i + 2] > 0) {
          scopes_.push_back({kNamespace, "", -1, bm_[i + 2]});
          i += 3;
          stmt = i;
          continue;
        }
        if ((s == "class" || s == "struct" || s == "union") && !(i > 0 && t_[i - 1].s == "enum") &&
            !(i > 0 && (t_[i - 1].s == "friend" || t_[i - 1].s == "<" || t_[i - 1].s == ","))) {
          int ni = try_class(i);
          if (ni > i) {
            i = ni;
            stmt = i;
            continue;
          }
        }
        if (s == "enum") {
          int j = i + 1;
          while (j < n_ && t_[j].s != "{" && t_[j].s != ";") ++j;
          if (j < n_ && t_[j].s == "{" && bm_[j] > 0) {
            if (in_class()) scan_idd(j, bm_[j]);
            i = bm_[j] + 1;
            continue;
          }
          i = j + 1;
          stmt = i;
          continue;
        }
        if (in_class() && (s == "public" || s == "private" || s == "protected") && next_is(i, ":")) {
          i += 2;
          stmt = i;
          continue;
        }
      }
      if (k.k == TK::Punct && k.s == "(" && i > 0) {
        int ni = handle_paren(i, stmt);
        if (ni > i) {
          i = ni;
          stmt = i;
          continue;
        }
      }
      if (k.k == TK::Punct && k.s == "{") {
        if (bm_[i] > 0) {
          i = bm_[i] + 1;  // initializer / unknown block: skip
          continue;
        }
        ++i;
        continue;
      }
      ++i;
    }
  }

 private:
  enum { kNamespace = 0, kClass = 1 };
  struct Scope {
    int kind;
    std::string name;
    int cls;    // index in out_.classes
    int close;  // token index of matching '}'
  };

  const std::vector<Token>& t_;
  int file_;
  RawData& out_;
  int n_ = 0;
  std::vector<int> bm_, pm_;  // brace / paren matches (-1 = none)
  std::vector<Scope> scopes_;

  bool next_is(int i, const char* s) const { return i + 1 < n_ && t_[i + 1].s == s && t_[i + 1].k == TK::Punct; }
  bool is_p(int i, const char* s) const { return i >= 0 && i < n_ && t_[i].k == TK::Punct && t_[i].s == s; }
  bool is_id(int i) const { return i >= 0 && i < n_ && t_[i].k == TK::Ident; }
  bool in_class() const { return !scopes_.empty() && scopes_.back().kind == kClass; }

  void compute_matches() {
    bm_.assign(n_, -1);
    pm_.assign(n_, -1);
    std::vector<int> bs, ps;
    for (int i = 0; i < n_; ++i) {
      if (t_[i].k != TK::Punct) continue;
      const std::string& s = t_[i].s;
      if (s == "{") bs.push_back(i);
      else if (s == "}") {
        if (!bs.empty()) {
          bm_[bs.back()] = i;
          bm_[i] = bs.back();
          bs.pop_back();
        } else {
          out_.files[file_].brace_error = true;
        }
      } else if (s == "(") ps.push_back(i);
      else if (s == ")") {
        if (!ps.empty()) {
          pm_[ps.back()] = i;
          pm_[i] = ps.back();
          ps.pop_back();
        }
      }
    }
    if (!bs.empty()) out_.files[file_].brace_error = true;
  }

  int skip_to_semicolon(int i) const {
    while (i < n_ && !(t_[i].k == TK::Punct && t_[i].s == ";")) ++i;
    return i + 1;
  }

  int skip_angles(int i) const {  // i at '<'
    int depth = 0;
    for (; i < n_; ++i) {
      const std::string& s = t_[i].s;
      if (t_[i].k != TK::Punct) continue;
      if (s == "<") ++depth;
      else if (s == ">") {
        if (--depth <= 0) return i + 1;
      } else if (s == ">>") {
        depth -= 2;
        if (depth <= 0) return i + 1;
      } else if (s == "{" || s == ";") return i;
    }
    return i;
  }

  std::string ns_path() const {
    std::string r;
    for (const auto& s : scopes_)
      if (s.kind == kNamespace && !s.name.empty()) r += (r.empty() ? "" : "::") + s.name;
    return r;
  }

  std::string class_path() const {
    std::string r;
    for (const auto& s : scopes_)
      if (s.kind == kClass) r += (r.empty() ? "" : "::") + s.name;
    return r;
  }

  int current_class() const {
    for (int k = (int)scopes_.size() - 1; k >= 0; --k)
      if (scopes_[k].kind == kClass) return scopes_[k].cls;
    return -1;
  }

  void handle_pp(const Token& k) {
    const std::string& d = k.s;
    if (starts_with(d, "include")) {
      size_t a = d.find_first_of("\"<");
      if (a == std::string::npos) return;
      char close = d[a] == '"' ? '"' : '>';
      size_t b = d.find(close, a + 1);
      if (b == std::string::npos) return;
      out_.includes.push_back({file_, d.substr(a + 1, b - a - 1), k.line});
    } else if (starts_with(d, "define")) {
      std::string rest = trim(d.substr(6));
      size_t e = 0;
      while (e < rest.size() && (std::isalnum((unsigned char)rest[e]) || rest[e] == '_')) ++e;
      if (e == 0) return;
      std::string name = rest.substr(0, e);
      if (e < rest.size() && rest[e] == '(') return;  // function-like macro
      out_.defines.push_back({file_, name, trim(rest.substr(e)), k.line});
    }
  }

  // enum { IDD = IDD_EXPORT };
  void scan_idd(int b, int e) {
    int cls = current_class();
    if (cls < 0) return;
    for (int j = b; j + 2 < e; ++j)
      if (is_id(j) && t_[j].s == "IDD" && is_p(j + 1, "=") && t_[j + 2].k != TK::Punct)
        out_.classes[cls].idd = t_[j + 2].s;
  }

  int try_class(int i) {
    int j = i + 1;
    std::string name;
    while (j < n_) {
      if (is_id(j) && t_[j].s == "__declspec" && is_p(j + 1, "(") && pm_[j + 1] > 0) {
        j = pm_[j + 1] + 1;
        continue;
      }
      if (is_id(j)) {
        if (t_[j].s != "final" && t_[j].s != "sealed") name = t_[j].s;
        ++j;
        continue;
      }
      if (is_p(j, "::")) {
        ++j;
        continue;
      }
      if (is_p(j, "<")) {
        j = skip_angles(j);
        continue;
      }
      break;
    }
    if (j >= n_) return i;
    std::vector<std::string> bases;
    if (is_p(j, ":")) {
      std::string cur;
      int depth = 0;
      ++j;
      for (; j < n_; ++j) {
        const Token& k = t_[j];
        if (k.k == TK::Punct && k.s == "{" && depth == 0) break;
        if (k.k == TK::Punct && k.s == ";") return i;
        if (k.k == TK::Punct && k.s == "<") {
          ++depth;
          continue;
        }
        if (k.k == TK::Punct && (k.s == ">" || k.s == ">>")) {
          depth -= (k.s == ">>") ? 2 : 1;
          continue;
        }
        if (depth > 0) continue;
        if (k.k == TK::Punct && k.s == ",") {
          if (!cur.empty()) bases.push_back(cur);
          cur.clear();
          continue;
        }
        if (k.k == TK::Ident) {
          if (k.s == "public" || k.s == "private" || k.s == "protected" || k.s == "virtual") continue;
          cur += k.s;
        } else if (k.s == "::") {
          cur += "::";
        }
      }
      if (!cur.empty()) bases.push_back(cur);
    }
    if (!is_p(j, "{") || bm_[j] < 0) return i;
    if (name.empty()) return bm_[j] + 1;  // anonymous struct/union: skip body
    RawClass c;
    c.file = file_;
    std::string outer = class_path();
    c.name = outer.empty() ? name : outer + "::" + name;
    c.ns = ns_path();
    c.bases = bases;
    c.line = t_[i].line;
    out_.classes.push_back(c);
    scopes_.push_back({kClass, name, (int)out_.classes.size() - 1, bm_[j]});
    return j + 1;
  }

  void analyze_field(int b, int e) {
    int cls = current_class();
    if (cls < 0) return;
    for (int j = b; j < e; ++j) {
      if (t_[j].k == TK::Punct && (t_[j].s == "(" || t_[j].s == "{")) return;
      if (is_id(j) && (t_[j].s == "typedef" || t_[j].s == "using" || t_[j].s == "friend" || t_[j].s == "enum"))
        return;
    }
    // split by top-level commas
    std::string type;
    int seg_b = b;
    int depth = 0;
    for (int j = b; j <= e; ++j) {
      bool end = (j == e);
      if (!end && t_[j].k == TK::Punct) {
        if (t_[j].s == "<") ++depth;
        else if (t_[j].s == ">") --depth;
        else if (t_[j].s == ">>") depth -= 2;
      }
      if (end || (depth == 0 && is_p(j, ","))) {
        std::string name;
        for (int q = seg_b; q < j; ++q) {
          if (t_[q].k == TK::Punct && (t_[q].s == "=" || t_[q].s == "[" || t_[q].s == ":")) break;
          if (is_id(q)) {
            if (type.empty()) {
              const std::string& s = t_[q].s;
              if (s != "static" && s != "const" && s != "mutable" && s != "volatile" && s != "unsigned" &&
                  s != "signed" && s != "struct" && s != "class" && s != "typename" && s != "constexpr")
                type = s;
            }
            name = t_[q].s;
          }
        }
        if (!name.empty() && !type.empty() && name != type) out_.classes[cls].fields[name] = type;
        seg_b = j + 1;
      }
    }
  }

  std::vector<std::vector<int>> split_args(int p) const {  // p at '('; returns token index ranges
    std::vector<std::vector<int>> args;
    int close = pm_[p];
    if (close < 0) return args;
    std::vector<int> cur;
    int depth = 0;
    for (int j = p + 1; j < close; ++j) {
      if (t_[j].k == TK::Punct) {
        if (t_[j].s == "(" || t_[j].s == "{" || t_[j].s == "[") ++depth;
        else if (t_[j].s == ")" || t_[j].s == "}" || t_[j].s == "]") --depth;
        else if (t_[j].s == "," && depth == 0) {
          args.push_back(cur);
          cur.clear();
          continue;
        }
      }
      cur.push_back(j);
    }
    if (!cur.empty() || !args.empty()) args.push_back(cur);
    return args;
  }

  std::string arg_text(const std::vector<int>& a) const {
    if (a.empty()) return "";
    return join_tokens(t_, a.front(), a.back() + 1);
  }

  // "&CMainFrame::OnFoo" -> "CMainFrame::OnFoo"; qualifier kept so that handlers
  // implemented in an MFC base class (&CWinApp::OnFileNew) can be recognised.
  static std::string clean_handler(std::string h) {
    h = replace_all(h, "&", "");
    h = replace_all(h, " ", "");
    return trim(h);
  }

  // Returns new position (> p) if consumed.
  int handle_paren(int p, int stmt) {
    int close = pm_[p];
    if (close < 0) return p;
    int j = p - 1;
    std::string name;
    if (is_id(j)) {
      name = t_[j].s;
      if (is_p(j - 1, "~")) {
        name = "~" + name;
        --j;
      } else if (j - 1 >= 0 && t_[j - 1].s == "operator") {
        name = "operator " + name;
        --j;
      }
    } else if (t_[j].k == TK::Punct && j - 1 >= 0 && t_[j - 1].s == "operator") {
      name = "operator" + t_[j].s;
      --j;
    } else {
      return p;
    }
    if (keywords().count(name)) return p;
    std::string qual;
    int q = j;
    while (q - 2 >= 0 && is_p(q - 1, "::") && is_id(q - 2)) {
      qual = t_[q - 2].s + (qual.empty() ? "" : "::" + qual);
      q -= 2;
    }
    if (q - 1 >= 0 && t_[q - 1].k == TK::Punct &&
        (t_[q - 1].s == "." || t_[q - 1].s == "->" || t_[q - 1].s == "=" || t_[q - 1].s == "(" ||
         t_[q - 1].s == ","))
      return p;  // expression, not a declaration

    // MFC / macro invocations at namespace or class scope
    if (qual.empty() && is_all_caps_ident(name)) {
      int after = close + 1;
      if (!is_p(after, "{")) {
        handle_scope_macro(name, p);
        if (name == "BEGIN_MESSAGE_MAP" || name == "BEGIN_TEMPLATE_MESSAGE_MAP") return parse_msgmap(p);
        return is_p(after, ";") ? after + 1 : after;
      }
    }

    // what follows the parameter list
    int a = close + 1;
    while (a < n_) {
      const Token& k = t_[a];
      if (k.k == TK::Ident && (k.s == "const" || k.s == "volatile" || k.s == "override" || k.s == "final" ||
                               k.s == "PURE" || k.s == "noexcept" || k.s == "throw" || k.s == "sealed")) {
        if ((k.s == "throw" || k.s == "noexcept") && is_p(a + 1, "(") && pm_[a + 1] > 0) a = pm_[a + 1] + 1;
        else ++a;
        continue;
      }
      if (k.k == TK::Punct && (k.s == "&" || k.s == "&&")) {
        ++a;
        continue;
      }
      if (k.k == TK::Punct && k.s == "->") {  // trailing return type
        while (a < n_ && !is_p(a, "{") && !is_p(a, ";")) ++a;
        continue;
      }
      break;
    }
    if (a >= n_) return p;

    bool in_cls = in_class();
    int body = -1;
    bool decl = false;
    if (is_p(a, "{")) {
      body = a;
    } else if (is_p(a, ":")) {  // constructor initializer list
      int b = a + 1;
      while (b < n_) {
        while (b < n_ && (is_id(b) || is_p(b, "::"))) ++b;
        if (is_p(b, "<")) b = skip_angles(b);
        if (is_p(b, "(") && pm_[b] > 0) b = pm_[b] + 1;
        else if (is_p(b, "{") && bm_[b] > 0) b = bm_[b] + 1;
        else break;
        if (is_p(b, ",")) {
          ++b;
          continue;
        }
        break;
      }
      if (is_p(b, "{")) body = b;
      else return p;
    } else if (is_p(a, ";") || is_p(a, "=")) {
      decl = true;
    } else if (is_id(a) && t_[a].s == "try" && is_p(a + 1, "{")) {
      body = a + 1;
    } else {
      return p;
    }

    bool is_virtual = false;
    for (int s = stmt; s < q; ++s)
      if (is_id(s) && t_[s].s == "virtual") is_virtual = true;

    if (decl) {
      int end = is_p(a, ";") ? a : skip_to_semicolon(a) - 1;
      if (in_cls && qual.empty()) {
        RawFunc f;
        f.file = file_;
        f.cls = class_path();
        f.ns = ns_path();
        f.name = name;
        f.line = t_[j].line;
        f.end = f.line;
        f.sig = join_tokens(t_, stmt, close + 1);
        if (f.sig.size() > 240) f.sig = f.sig.substr(0, 240) + "...";
        f.is_def = false;
        f.is_virtual = is_virtual;
        out_.funcs.push_back(f);
      }
      return end + 1;
    }

    int e = bm_[body];
    if (e < 0) e = n_ - 1;
    RawFunc f;
    f.file = file_;
    if (!qual.empty()) {
      std::string outer = class_path();
      f.cls = outer.empty() ? qual : outer + "::" + qual;
    } else if (in_cls) {
      f.cls = class_path();
    }
    f.ns = ns_path();
    f.name = name;
    f.line = t_[j].line;
    f.end = t_[e].line;
    f.sig = join_tokens(t_, stmt, close + 1);
    if (f.sig.size() > 240) f.sig = f.sig.substr(0, 240) + "...";
    f.is_def = true;
    f.is_virtual = is_virtual;
    scan_locals(f, p + 1, close);
    scan_body(f, body + 1, e);
    out_.funcs.push_back(std::move(f));
    return e + 1;
  }

  void handle_scope_macro(const std::string& name, int p) {
    if (name == "IMPLEMENT_DYNCREATE" || name == "IMPLEMENT_DYNAMIC" || name == "IMPLEMENT_SERIAL") {
      auto args = split_args(p);
      if (args.size() >= 2)
        out_.dynamics.push_back({file_, name, arg_text(args[0]), arg_text(args[1]), t_[p].line});
    }
  }

  int parse_msgmap(int p) {
    auto args = split_args(p);
    RawMsgMap mm;
    mm.file = file_;
    mm.line = t_[p].line;
    if (!args.empty()) mm.cls = arg_text(args.front());
    if (args.size() >= 2) mm.base = arg_text(args.back());
    int a = pm_[p] + 1;
    while (a < n_) {
      if (is_id(a) && t_[a].s == "END_MESSAGE_MAP") {
        a = (is_p(a + 1, "(") && pm_[a + 1] > 0) ? pm_[a + 1] + 1 : a + 1;
        break;
      }
      if (t_[a].k == TK::PP) {
        handle_pp(t_[a]);
        ++a;
        continue;
      }
      if (is_p(a, "{") || is_p(a, "}")) break;  // malformed map
      if (is_id(a) && is_p(a + 1, "(") && pm_[a + 1] > 0) {
        add_msg_entry(mm, t_[a].s, a + 1);
        a = pm_[a + 1] + 1;
        continue;
      }
      ++a;
    }
    out_.msgmaps.push_back(mm);
    return a;
  }

  static std::string wm_handler(const std::string& macro) {
    static const std::map<std::string, std::string> m = {
        {"ON_WM_CREATE", "OnCreate"}, {"ON_WM_DESTROY", "OnDestroy"}, {"ON_WM_PAINT", "OnPaint"},
        {"ON_WM_SIZE", "OnSize"}, {"ON_WM_MOVE", "OnMove"}, {"ON_WM_CLOSE", "OnClose"},
        {"ON_WM_TIMER", "OnTimer"}, {"ON_WM_ERASEBKGND", "OnEraseBkgnd"}, {"ON_WM_CTLCOLOR", "OnCtlColor"},
        {"ON_WM_CTLCOLOR_REFLECT", "CtlColor"}, {"ON_WM_SYSCOMMAND", "OnSysCommand"},
        {"ON_WM_QUERYDRAGICON", "OnQueryDragIcon"}, {"ON_WM_LBUTTONDOWN", "OnLButtonDown"},
        {"ON_WM_LBUTTONUP", "OnLButtonUp"}, {"ON_WM_LBUTTONDBLCLK", "OnLButtonDblClk"},
        {"ON_WM_RBUTTONDOWN", "OnRButtonDown"}, {"ON_WM_RBUTTONUP", "OnRButtonUp"},
        {"ON_WM_RBUTTONDBLCLK", "OnRButtonDblClk"}, {"ON_WM_MBUTTONDOWN", "OnMButtonDown"},
        {"ON_WM_MBUTTONUP", "OnMButtonUp"}, {"ON_WM_MOUSEMOVE", "OnMouseMove"},
        {"ON_WM_MOUSEWHEEL", "OnMouseWheel"}, {"ON_WM_MOUSELEAVE", "OnMouseLeave"},
        {"ON_WM_KEYDOWN", "OnKeyDown"}, {"ON_WM_KEYUP", "OnKeyUp"}, {"ON_WM_CHAR", "OnChar"},
        {"ON_WM_SYSKEYDOWN", "OnSysKeyDown"}, {"ON_WM_SETFOCUS", "OnSetFocus"},
        {"ON_WM_KILLFOCUS", "OnKillFocus"}, {"ON_WM_HSCROLL", "OnHScroll"}, {"ON_WM_VSCROLL", "OnVScroll"},
        {"ON_WM_CONTEXTMENU", "OnContextMenu"}, {"ON_WM_DROPFILES", "OnDropFiles"},
        {"ON_WM_GETMINMAXINFO", "OnGetMinMaxInfo"}, {"ON_WM_SETCURSOR", "OnSetCursor"},
        {"ON_WM_SHOWWINDOW", "OnShowWindow"}, {"ON_WM_ACTIVATE", "OnActivate"},
        {"ON_WM_ACTIVATEAPP", "OnActivateApp"}, {"ON_WM_NCDESTROY", "OnNcDestroy"},
        {"ON_WM_NCHITTEST", "OnNcHitTest"}, {"ON_WM_NCPAINT", "OnNcPaint"}, {"ON_WM_DRAWITEM", "OnDrawItem"},
        {"ON_WM_MEASUREITEM", "OnMeasureItem"}, {"ON_WM_INITMENUPOPUP", "OnInitMenuPopup"},
        {"ON_WM_MENUSELECT", "OnMenuSelect"}, {"ON_WM_COPYDATA", "OnCopyData"},
        {"ON_WM_SETTINGCHANGE", "OnSettingChange"}, {"ON_WM_ENDSESSION", "OnEndSession"},
        {"ON_WM_QUERYENDSESSION", "OnQueryEndSession"}, {"ON_WM_WINDOWPOSCHANGED", "OnWindowPosChanged"},
        {"ON_WM_WINDOWPOSCHANGING", "OnWindowPosChanging"}, {"ON_WM_SIZING", "OnSizing"},
        {"ON_WM_ENABLE", "OnEnable"}, {"ON_WM_MOUSEACTIVATE", "OnMouseActivate"},
        {"ON_WM_DEVICECHANGE", "OnDeviceChange"}, {"ON_WM_HELPINFO", "OnHelpInfo"},
        {"ON_WM_NOTIFYFORMAT", "OnNotifyFormat"}, {"ON_WM_GETDLGCODE", "OnGetDlgCode"},
        {"ON_WM_PARENTNOTIFY", "OnParentNotify"}, {"ON_WM_CAPTURECHANGED", "OnCaptureChanged"},
        {"ON_WM_NCCALCSIZE", "OnNcCalcSize"}, {"ON_WM_NCLBUTTONDOWN", "OnNcLButtonDown"},
        {"ON_WM_CANCELMODE", "OnCancelMode"}, {"ON_WM_SYSCOLORCHANGE", "OnSysColorChange"},
        {"ON_WM_PALETTECHANGED", "OnPaletteChanged"}, {"ON_WM_QUERYNEWPALETTE", "OnQueryNewPalette"},
        {"ON_WM_NCCREATE", "OnNcCreate"}, {"ON_WM_CHILDACTIVATE", "OnChildActivate"},
        {"ON_WM_MDIACTIVATE", "OnMDIActivate"}, {"ON_WM_INITMENU", "OnInitMenu"},
        {"ON_WM_ENTERIDLE", "OnEnterIdle"}, {"ON_WM_COMPAREITEM", "OnCompareItem"},
        {"ON_WM_DELETEITEM", "OnDeleteItem"}, {"ON_WM_CHARTOITEM", "OnCharToItem"},
        {"ON_WM_VKEYTOITEM", "OnVKeyToItem"}, {"ON_WM_STYLECHANGED", "OnStyleChanged"},
        {"ON_WM_TCARD", "OnTCard"}, {"ON_WM_DESTROYCLIPBOARD", "OnDestroyClipboard"},
        {"ON_WM_RENDERFORMAT", "OnRenderFormat"}, {"ON_WM_CLIPBOARDUPDATE", "OnClipboardUpdate"},
        {"ON_WM_POWERBROADCAST", "OnPowerBroadcast"}, {"ON_WM_DPICHANGED", "OnDpiChanged"},
        {"ON_WM_NCMOUSEMOVE", "OnNcMouseMove"}, {"ON_WM_SYSCHAR", "OnSysChar"},
        {"ON_WM_SYSKEYUP", "OnSysKeyUp"}, {"ON_WM_TIMECHANGE", "OnTimeChange"},
        {"ON_WM_FONTCHANGE", "OnFontChange"}, {"ON_WM_SPOOLERSTATUS", "OnSpoolerStatus"},
        {"ON_WM_DEVMODECHANGE", "OnDevModeChange"}, {"ON_WM_RASKCBFORMATNAME", "OnAskCbFormatName"},
        {"ON_WM_HSCROLL_REFLECT", "HScroll"}, {"ON_WM_VSCROLL_REFLECT", "VScroll"},
        {"ON_WM_DRAWITEM_REFLECT", "DrawItem"}, {"ON_WM_MEASUREITEM_REFLECT", "MeasureItem"}};
    auto it = m.find(macro);
    return it == m.end() ? "" : it->second;
  }

  void add_msg_entry(RawMsgMap& mm, const std::string& macro, int p) {
    auto args = split_args(p);
    RawMsgEntry e;
    e.macro = macro;
    e.line = t_[p].line;
    std::vector<std::string> a;
    for (auto& r : args) a.push_back(arg_text(r));
    if (starts_with(macro, "ON_WM_") && a.empty()) {
      e.kind = "message";
      std::string base = macro.substr(6);
      if (ends_with(base, "_REFLECT")) base = base.substr(0, base.size() - 8);
      e.id = "WM_" + base;
      e.handler = wm_handler(macro);
      if (e.handler.empty()) {
        out_.unknown_macros[macro]++;
        return;
      }
      mm.entries.push_back(e);
      return;
    }
    if (!starts_with(macro, "ON_") || a.empty()) {
      if (starts_with(macro, "ON_")) out_.unknown_macros[macro]++;
      return;
    }
    e.handler = clean_handler(a.back());
    if (macro == "ON_MESSAGE" || macro == "ON_REGISTERED_MESSAGE" || macro == "ON_THREAD_MESSAGE" ||
        macro == "ON_REGISTERED_THREAD_MESSAGE" || macro == "ON_MESSAGE_VOID") {
      e.kind = "message";
      e.id = a[0];
    } else if (starts_with(macro, "ON_UPDATE_COMMAND_UI")) {
      e.kind = "update_ui";
      e.id = a[0];
      if (a.size() >= 3) e.id2 = a[1];
    } else if (starts_with(macro, "ON_NOTIFY")) {
      e.kind = "notify";
      if (ends_with(macro, "_REFLECT") || ends_with(macro, "_REFLECT_EX")) e.id = a[0];
      else if (a.size() >= 4) {
        e.id = a[1];
        e.id2 = a[2];
      } else if (a.size() >= 3) e.id = a[1];
      else e.id = a[0];
    } else if (starts_with(macro, "ON_CONTROL")) {
      e.kind = "command";
      if (ends_with(macro, "_REFLECT") || ends_with(macro, "_REFLECT_EX")) e.id = a[0];
      else if (a.size() >= 4) {
        e.id = a[1];
        e.id2 = a[2];
      } else if (a.size() >= 3) e.id = a[1];
      else e.id = a[0];
    } else {
      // ON_COMMAND, ON_COMMAND_EX, ON_COMMAND_RANGE, ON_BN_CLICKED, ON_EN_CHANGE, ON_CBN_*, ...
      e.kind = "command";
      if (a.size() < 2) {
        out_.unknown_macros[macro]++;
        return;
      }
      e.id = a[0];
      if (a.size() >= 3) e.id2 = a[1];
    }
    mm.entries.push_back(e);
  }

  void scan_locals(RawFunc& f, int b, int e) {  // [b, e)
    for (int t = b; t + 2 < e + 1 && t + 1 < n_; ++t) {
      if (!is_id(t) || keywords().count(t_[t].s)) continue;
      // Type name [;=,)[(]
      if (is_id(t + 1) && !keywords().count(t_[t + 1].s) && t + 2 < n_ && t_[t + 2].k == TK::Punct) {
        const std::string& s = t_[t + 2].s;
        if (s == ";" || s == "=" || s == "," || s == ")" || s == "[") f.locals[t_[t + 1].s] = t_[t].s;
      }
      // Type* name / Type& name
      if (t + 3 < n_ && (is_p(t + 1, "*") || is_p(t + 1, "&")) && is_id(t + 2) &&
          !keywords().count(t_[t + 2].s) && t_[t + 3].k == TK::Punct) {
        const std::string& s = t_[t + 3].s;
        if (s == ";" || s == "=" || s == "," || s == ")" || s == "[") f.locals[t_[t + 2].s] = t_[t].s;
      }
    }
  }

  void scan_body(RawFunc& f, int b, int e) {  // [b, e)
    scan_locals(f, b, e);
    for (int t = b; t < e; ++t) {
      if (!is_id(t) || !is_p(t + 1, "(")) continue;
      const std::string& name = t_[t].s;
      if (keywords().count(name)) continue;
      if (name == "RUNTIME_CLASS") {
        if (is_id(t + 2)) f.runtime.push_back({t_[t + 2].s, t_[t].line});
        continue;
      }
      if (starts_with(name, "DDX_")) {
        auto args = split_args(t + 1);
        if (args.size() >= 3) f.ddx.push_back({name, arg_text(args[1]), arg_text(args[2]), t_[t].line});
        continue;
      }
      if (starts_with(name, "DDV_")) continue;
      if (call_stoplist().count(name)) continue;
      int prev = t - 1;
      if (prev >= b && is_id(prev) && !keywords().count(t_[prev].s)) {
        f.locals[name] = t_[prev].s;  // CRect rc(...): local declaration with constructor args
        continue;
      }
      if (prev >= b && is_id(prev) && t_[prev].s == "new") continue;
      RawCall c;
      c.name = name;
      c.line = t_[t].line;
      if (prev >= b && t_[prev].k == TK::Punct && (t_[prev].s == "." || t_[prev].s == "->")) {
        c.member = true;
        if (prev - 1 >= b && is_id(prev - 1)) {
          c.recv = t_[prev - 1].s;
        } else if (prev - 1 >= b && is_p(prev - 1, ")") && pm_[prev - 1] >= b) {
          int m = pm_[prev - 1];
          // ((T*)p)->f()   or   (T*)p ... handled only in the fully parenthesised form
          if (is_p(m + 1, "(") && is_id(m + 2) && (is_p(m + 3, "*") || is_p(m + 3, "&")) && is_p(m + 4, ")"))
            c.recv_type = t_[m + 2].s;
          else if (m - 1 >= b && is_id(m - 1) && !keywords().count(t_[m - 1].s))
            c.recv_call = t_[m - 1].s;  // GetDocument()->f()
        }
      } else if (prev >= b && is_p(prev, "::")) {
        int q = prev;
        std::string qual;
        while (q - 1 >= b && is_id(q - 1)) {
          qual = t_[q - 1].s + (qual.empty() ? "" : "::" + qual);
          if (q - 2 >= b && is_p(q - 2, "::")) q -= 2;
          else break;
        }
        c.qual = qual.empty() ? "::" : qual;
      }
      if (send_apis().count(name)) {
        RawSend s;
        s.api = name;
        s.line = c.line;
        int close = pm_[t + 1];
        for (int k = t + 2; close > 0 && k < close; ++k)
          if (is_id(k) && is_all_caps_ident(t_[k].s)) s.caps.push_back(t_[k].s);
        if (!s.caps.empty()) f.sends.push_back(s);
      }
      f.calls.push_back(c);
    }
  }
};

}  // namespace

void extract_cpp(const std::vector<Token>& toks, int file_index, RawData& out) {
  CppWalker w(toks, file_index, out);
  w.run();
}

}  // namespace mg
