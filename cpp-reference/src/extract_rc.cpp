// extract_rc.cpp: Windows resource script parser (dialogs, menus, accelerators,
// toolbars, string tables). Tolerant: unknown resource types are skipped.
#include <cctype>
#include <set>
#include <string>

#include "extract.h"
#include "util.h"

namespace mg {

namespace {

bool is_begin(const Token& t) { return (t.k == TK::Ident && t.s == "BEGIN") || (t.k == TK::Punct && t.s == "{"); }
bool is_end(const Token& t) { return (t.k == TK::Ident && t.s == "END") || (t.k == TK::Punct && t.s == "}"); }

const std::set<std::string>& control_keywords() {
  static const std::set<std::string> s = {"LTEXT", "RTEXT", "CTEXT", "PUSHBUTTON", "DEFPUSHBUTTON", "EDITTEXT",
                                          "COMBOBOX", "LISTBOX", "GROUPBOX", "CONTROL", "CHECKBOX",
                                          "AUTOCHECKBOX", "STATE3", "AUTO3STATE", "RADIOBUTTON",
                                          "AUTORADIOBUTTON", "ICON", "SCROLLBAR", "PUSHBOX"};
  return s;
}

std::string strip_menu_text(std::string s) {
  size_t tab = s.find("\\t");
  if (tab != std::string::npos) s = s.substr(0, tab);
  tab = s.find('\t');
  if (tab != std::string::npos) s = s.substr(0, tab);
  std::string r;
  for (size_t i = 0; i < s.size(); ++i) {
    if (s[i] == '&') {
      if (i + 1 < s.size() && s[i + 1] == '&') {
        r += '&';
        ++i;
      }
      continue;
    }
    r += s[i];
  }
  return trim(r);
}

class RcWalker {
 public:
  RcWalker(const std::vector<Token>& t, int file, RawData& out) : t_(t), file_(file), out_(out), n_((int)t.size()) {}

  void run() {
    int i = 0;
    while (i < n_) {
      const Token& k = t_[i];
      if (k.k == TK::PP) {
        ++i;
        continue;
      }
      if (k.k == TK::Ident && k.s == "STRINGTABLE") {
        i = parse_stringtable(i + 1);
        continue;
      }
      if ((k.k == TK::Ident || k.k == TK::Number) && i + 1 < n_ && t_[i + 1].k == TK::Ident) {
        const std::string& type = t_[i + 1].s;
        if (type == "DIALOG" || type == "DIALOGEX") {
          i = parse_dialog(i);
          continue;
        }
        if (type == "MENU" || type == "MENUEX") {
          i = parse_menu(i);
          continue;
        }
        if (type == "ACCELERATORS") {
          i = parse_accel(i);
          continue;
        }
        if (type == "TOOLBAR") {
          i = parse_toolbar(i);
          continue;
        }
        // any other resource: skip the header line and an optional BEGIN..END block
        int line = t_[i].line;
        int j = i + 2;
        while (j < n_ && t_[j].line == line && !is_begin(t_[j])) ++j;
        while (j < n_ && t_[j].k == TK::Ident && !is_begin(t_[j]) && t_[j].line != line &&
               (t_[j].s == "LANGUAGE" || t_[j].s == "CHARACTERISTICS" || t_[j].s == "VERSION" ||
                t_[j].s == "FILEVERSION" || t_[j].s == "PRODUCTVERSION" || t_[j].s == "FILEFLAGSMASK" ||
                t_[j].s == "FILEFLAGS" || t_[j].s == "FILEOS" || t_[j].s == "FILETYPE" || t_[j].s == "FILESUBTYPE")) {
          int l2 = t_[j].line;
          while (j < n_ && t_[j].line == l2) ++j;
        }
        if (j < n_ && is_begin(t_[j])) j = skip_block(j);
        i = j;
        continue;
      }
      ++i;
    }
  }

 private:
  const std::vector<Token>& t_;
  int file_;
  RawData& out_;
  int n_;

  int skip_block(int j) const {  // j at BEGIN; returns index after matching END
    int depth = 0;
    for (; j < n_; ++j) {
      if (is_begin(t_[j])) ++depth;
      else if (is_end(t_[j]) && --depth == 0) return j + 1;
    }
    return n_;
  }

  int find_begin(int j) const {
    while (j < n_ && !is_begin(t_[j])) ++j;
    return j;
  }

  // Tokens of one logical line inside a block (stops at BEGIN/END).
  std::vector<int> line_tokens(int& j) const {
    std::vector<int> r;
    if (j >= n_) return r;
    int line = t_[j].line;
    while (j < n_ && t_[j].line == line && !is_begin(t_[j]) && !is_end(t_[j])) r.push_back(j++);
    // continuation: a line ending with ',' continues on the next line
    while (!r.empty() && t_[r.back()].s == "," && j < n_ && !is_begin(t_[j]) && !is_end(t_[j])) {
      line = t_[j].line;
      while (j < n_ && t_[j].line == line && !is_begin(t_[j]) && !is_end(t_[j])) r.push_back(j++);
    }
    return r;
  }

  int parse_dialog(int i) {
    RcDialog d;
    d.file = file_;
    d.id = t_[i].s;
    d.line = t_[i].line;
    int j = i + 2;
    while (j < n_ && !is_begin(t_[j])) {
      if (t_[j].k == TK::Ident && t_[j].s == "CAPTION" && j + 1 < n_ && t_[j + 1].k == TK::String)
        d.caption = t_[j + 1].s;
      ++j;
    }
    if (j >= n_) return j;
    int end = skip_block(j);
    ++j;
    while (j < end - 1) {
      if (t_[j].k == TK::Ident && control_keywords().count(t_[j].s)) {
        RcControl c;
        c.type = t_[j].s;
        c.line = t_[j].line;
        int k = j + 1;
        // collect args until next control keyword or END
        std::vector<int> args;
        while (k < end - 1 && !(t_[k].k == TK::Ident && control_keywords().count(t_[k].s) && t_[k].line != c.line))
          args.push_back(k++);
        // split by commas
        std::vector<std::string> parts;
        std::vector<TK> kinds;
        std::string cur;
        TK curk = TK::Punct;
        for (int a : args) {
          if (t_[a].k == TK::Punct && t_[a].s == ",") {
            parts.push_back(trim(cur));
            kinds.push_back(curk);
            cur.clear();
            curk = TK::Punct;
            continue;
          }
          if (cur.empty()) curk = t_[a].k;
          cur += (cur.empty() ? "" : " ") + t_[a].s;
        }
        parts.push_back(trim(cur));
        kinds.push_back(curk);
        bool text_first = !(c.type == "EDITTEXT" || c.type == "COMBOBOX" || c.type == "LISTBOX" ||
                            c.type == "SCROLLBAR");
        if (text_first && parts.size() >= 2) {
          c.text = strip_menu_text(parts[0]);
          c.id = parts[1];
        } else if (!parts.empty()) {
          c.id = parts[0];
        }
        if (!c.id.empty()) d.controls.push_back(c);
        j = k;
        continue;
      }
      ++j;
    }
    out_.dialogs.push_back(d);
    return end;
  }

  int parse_menu(int i) {
    std::string menu_id = t_[i].s;
    int j = find_begin(i + 2);
    if (j >= n_) return j;
    int end = skip_block(j);
    std::vector<std::string> path;
    std::vector<int> depth_at_popup;
    int depth = 0;
    std::string pending_popup;
    for (int k = j; k < end; ++k) {
      const Token& t = t_[k];
      if (is_begin(t)) {
        ++depth;
        if (!pending_popup.empty() || depth > 1) {
          path.push_back(pending_popup);
          depth_at_popup.push_back(depth);
        }
        pending_popup.clear();
        continue;
      }
      if (is_end(t)) {
        if (!depth_at_popup.empty() && depth_at_popup.back() == depth) {
          depth_at_popup.pop_back();
          path.pop_back();
        }
        --depth;
        continue;
      }
      if (t.k == TK::Ident && t.s == "POPUP" && k + 1 < end && t_[k + 1].k == TK::String) {
        pending_popup = strip_menu_text(t_[k + 1].s);
        ++k;
        continue;
      }
      if (t.k == TK::Ident && t.s == "MENUITEM") {
        if (k + 1 < end && t_[k + 1].k == TK::Ident && t_[k + 1].s == "SEPARATOR") continue;
        if (k + 3 < end && t_[k + 1].k == TK::String && t_[k + 2].s == ",") {
          RcUiItem u;
          u.file = file_;
          u.kind = "menu";
          u.owner = menu_id;
          std::vector<std::string> p;
          for (auto& s : path)
            if (!s.empty()) p.push_back(s);
          p.push_back(strip_menu_text(t_[k + 1].s));
          u.label = join(p, " > ");
          u.id = t_[k + 3].s;
          u.line = t.line;
          out_.uiitems.push_back(u);
        }
      }
    }
    return end;
  }

  int parse_accel(int i) {
    std::string owner = t_[i].s;
    int j = find_begin(i + 2);
    if (j >= n_) return j;
    int end = skip_block(j);
    ++j;
    while (j < end - 1) {
      std::vector<int> lt = line_tokens(j);
      if (lt.empty()) {
        ++j;
        continue;
      }
      // key , ID , flags...
      std::vector<std::string> parts;
      std::string cur;
      for (int a : lt) {
        if (t_[a].s == "," && t_[a].k == TK::Punct) {
          parts.push_back(trim(cur));
          cur.clear();
        } else {
          cur += (cur.empty() ? "" : " ") + (t_[a].k == TK::String ? "\"" + t_[a].s + "\"" : t_[a].s);
        }
      }
      parts.push_back(trim(cur));
      if (parts.size() < 2) continue;
      std::string key = parts[0];
      if (key.size() >= 2 && key.front() == '"') key = key.substr(1, key.size() - 2);
      if (starts_with(key, "VK_")) key = key.substr(3);
      std::string mods;
      for (size_t p = 2; p < parts.size(); ++p) {
        if (parts[p] == "CONTROL") mods += "Ctrl+";
        else if (parts[p] == "SHIFT") mods += "Shift+";
        else if (parts[p] == "ALT") mods += "Alt+";
      }
      if (!key.empty() && key[0] == '^' && key.size() == 2) {
        mods += "Ctrl+";
        key = key.substr(1);
      }
      RcUiItem u;
      u.file = file_;
      u.kind = "accel";
      u.owner = owner;
      u.label = mods + key;
      u.id = parts[1];
      u.line = t_[lt[0]].line;
      out_.uiitems.push_back(u);
    }
    return end;
  }

  int parse_toolbar(int i) {
    std::string owner = t_[i].s;
    int j = find_begin(i + 2);
    if (j >= n_) return j;
    int end = skip_block(j);
    int idx = 0;
    for (int k = j; k < end; ++k) {
      if (t_[k].k == TK::Ident && t_[k].s == "BUTTON" && k + 1 < end) {
        ++idx;
        RcUiItem u;
        u.file = file_;
        u.kind = "toolbar";
        u.owner = owner;
        u.label = "button " + std::to_string(idx);
        u.id = t_[k + 1].s;
        u.line = t_[k].line;
        out_.uiitems.push_back(u);
      }
    }
    return end;
  }

  int parse_stringtable(int j) {
    j = find_begin(j);
    if (j >= n_) return j;
    int end = skip_block(j);
    ++j;
    while (j < end - 1) {
      std::vector<int> lt = line_tokens(j);
      if (lt.empty()) {
        ++j;
        continue;
      }
      std::string id, text;
      for (int a : lt) {
        if (id.empty() && (t_[a].k == TK::Ident || t_[a].k == TK::Number)) id = t_[a].s;
        else if (t_[a].k == TK::String) text += t_[a].s;
      }
      if (!id.empty() && !text.empty()) out_.strings.push_back({file_, id, text, t_[lt[0]].line});
    }
    return end;
  }
};

}  // namespace

void extract_rc(const std::vector<Token>& toks, int file_index, RawData& out) {
  RcWalker w(toks, file_index, out);
  w.run();
}

}  // namespace mg
