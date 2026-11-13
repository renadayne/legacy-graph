#include "lexer.h"

#include <cctype>
#include <cstring>

#include "util.h"

namespace mg {

namespace {

bool ident_start(unsigned char c) { return std::isalpha(c) || c == '_' || c >= 0x80 || c == '$'; }
bool ident_char(unsigned char c) { return std::isalnum(c) || c == '_' || c >= 0x80 || c == '$'; }

const char* kPuncts3[] = {"<<=", ">>=", "->*", "...", nullptr};
const char* kPuncts2[] = {"::", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "+=",
                          "-=", "*=", "/=", "%=", "&=", "|=", "^=", ".*", "##", nullptr};

}  // namespace

std::vector<Token> lex(const std::string& src, bool rc_mode) {
  std::vector<Token> out;
  const size_t n = src.size();
  size_t i = 0;
  int line = 1;
  bool line_start = true;  // only whitespace seen since the last newline

  auto peek = [&](size_t k) -> char { return i + k < n ? src[i + k] : '\0'; };

  while (i < n) {
    char c = src[i];
    if (c == '\n') {
      ++line;
      ++i;
      line_start = true;
      continue;
    }
    if (c == ' ' || c == '\t' || c == '\r' || c == '\f' || c == '\v') {
      ++i;
      continue;
    }
    if (c == '\\' && (peek(1) == '\n' || (peek(1) == '\r' && peek(2) == '\n'))) {  // line splice
      i += (peek(1) == '\n') ? 2 : 3;
      ++line;
      continue;
    }
    // comments
    if (c == '/' && peek(1) == '/') {
      while (i < n && src[i] != '\n') ++i;
      continue;
    }
    if (c == '/' && peek(1) == '*') {
      i += 2;
      while (i < n && !(src[i] == '*' && peek(1) == '/')) {
        if (src[i] == '\n') ++line;
        ++i;
      }
      i = (i < n) ? i + 2 : n;
      continue;
    }
    // preprocessor directive
    if (c == '#' && line_start) {
      int start_line = line;
      ++i;
      std::string text;
      while (i < n) {
        char d = src[i];
        if (d == '\\' && (peek(1) == '\n' || (peek(1) == '\r' && peek(2) == '\n'))) {
          i += (peek(1) == '\n') ? 2 : 3;
          ++line;
          text += ' ';
          continue;
        }
        if (d == '\n') break;
        if (d == '/' && peek(1) == '/') {
          while (i < n && src[i] != '\n') ++i;
          break;
        }
        if (d == '/' && peek(1) == '*') {
          i += 2;
          while (i < n && !(src[i] == '*' && peek(1) == '/')) {
            if (src[i] == '\n') ++line;
            ++i;
          }
          i = (i < n) ? i + 2 : n;
          text += ' ';
          continue;
        }
        text += d;
        ++i;
      }
      out.push_back({TK::PP, trim(text), start_line});
      continue;
    }
    line_start = false;

    // identifiers (and string prefixes / raw strings)
    if (ident_start((unsigned char)c)) {
      size_t b = i;
      while (i < n && ident_char((unsigned char)src[i])) ++i;
      std::string id = src.substr(b, i - b);
      if (i < n && src[i] == '"' && !rc_mode) {
        bool raw = !id.empty() && id.back() == 'R' &&
                   (id == "R" || id == "LR" || id == "uR" || id == "UR" || id == "u8R");
        bool prefix = raw || id == "L" || id == "u" || id == "U" || id == "u8";
        if (raw) {
          // R"delim( ... )delim"
          size_t q = i + 1;
          std::string delim;
          while (q < n && src[q] != '(' && src[q] != '\n' && delim.size() < 16) delim += src[q++];
          std::string close = ")" + delim + "\"";
          size_t end = src.find(close, q);
          if (end == std::string::npos) end = n;
          std::string body = src.substr(q + 1 < n ? q + 1 : n, end > q + 1 ? end - q - 1 : 0);
          int sl = line;
          for (char ch : src.substr(i, (end < n ? end + close.size() : n) - i))
            if (ch == '\n') ++line;
          i = end < n ? end + close.size() : n;
          out.push_back({TK::String, body, sl});
          continue;
        }
        if (prefix) {
          c = src[i];  // fall through to the string reader below
        } else {
          out.push_back({TK::Ident, id, line});
          continue;
        }
      } else if (i < n && src[i] == '\'' && (id == "L" || id == "u" || id == "U" || id == "u8")) {
        c = src[i];  // char literal with prefix
      } else {
        out.push_back({TK::Ident, id, line});
        continue;
      }
    }
    // string literal
    if (c == '"') {
      ++i;
      std::string s;
      while (i < n) {
        char d = src[i];
        if (d == '\n') break;  // unterminated: stop at end of line (tolerant)
        if (rc_mode) {
          if (d == '"') {
            if (peek(1) == '"') {
              s += '"';
              i += 2;
              continue;
            }
            ++i;
            break;
          }
          s += d;
          ++i;
        } else {
          if (d == '\\' && i + 1 < n) {
            s += d;
            s += src[i + 1];
            if (src[i + 1] == '\n') ++line;
            i += 2;
            continue;
          }
          if (d == '"') {
            ++i;
            break;
          }
          s += d;
          ++i;
        }
      }
      out.push_back({TK::String, s, line});
      continue;
    }
    // char literal
    if (c == '\'') {
      ++i;
      std::string s;
      while (i < n && src[i] != '\n') {
        if (src[i] == '\\' && i + 1 < n) {
          s += src[i];
          s += src[i + 1];
          i += 2;
          continue;
        }
        if (src[i] == '\'') {
          ++i;
          break;
        }
        s += src[i++];
      }
      out.push_back({TK::Char, s, line});
      continue;
    }
    // numbers (incl. C++14 digit separators 1'000)
    if (std::isdigit((unsigned char)c) || (c == '.' && std::isdigit((unsigned char)peek(1)))) {
      size_t b = i;
      while (i < n) {
        char d = src[i];
        if (std::isalnum((unsigned char)d) || d == '.' || d == '_') {
          ++i;
        } else if (d == '\'' && i + 1 < n && std::isalnum((unsigned char)src[i + 1])) {
          ++i;
        } else if ((d == '+' || d == '-') && i > b &&
                   (src[i - 1] == 'e' || src[i - 1] == 'E' || src[i - 1] == 'p' || src[i - 1] == 'P')) {
          ++i;
        } else {
          break;
        }
      }
      out.push_back({TK::Number, src.substr(b, i - b), line});
      continue;
    }
    // punctuation
    bool matched = false;
    for (int k = 0; kPuncts3[k]; ++k) {
      if (src.compare(i, 3, kPuncts3[k]) == 0) {
        out.push_back({TK::Punct, kPuncts3[k], line});
        i += 3;
        matched = true;
        break;
      }
    }
    if (matched) continue;
    for (int k = 0; kPuncts2[k]; ++k) {
      if (src.compare(i, 2, kPuncts2[k]) == 0) {
        out.push_back({TK::Punct, kPuncts2[k], line});
        i += 2;
        matched = true;
        break;
      }
    }
    if (matched) continue;
    out.push_back({TK::Punct, std::string(1, c), line});
    ++i;
  }
  return out;
}

std::vector<Token> filter_conditionals(const std::vector<Token>& in, size_t* dropped) {
  struct Frame {
    bool parent_active;
    bool active;
    bool taken;
  };
  std::vector<Frame> st;
  std::vector<Token> out;
  out.reserve(in.size());
  size_t drop = 0;
  auto cur_active = [&]() { return st.empty() || st.back().active; };
  auto is_false_cond = [](const std::string& rest) {
    std::string r = trim(rest);
    return r == "0" || r == "(0)" || r == "FALSE";
  };
  for (const Token& t : in) {
    if (t.k == TK::PP) {
      std::string d = t.s;
      size_t sp = 0;
      while (sp < d.size() && !std::isspace((unsigned char)d[sp])) ++sp;
      std::string word = d.substr(0, sp), rest = d.substr(sp);
      if (word == "if" || word == "ifdef" || word == "ifndef") {
        bool parent = cur_active();
        bool cond = !(word == "if" && is_false_cond(rest));
        st.push_back({parent, parent && cond, cond});
        continue;
      }
      if (word == "elif" && !st.empty()) {
        Frame& f = st.back();
        if (f.taken) {
          f.active = false;
        } else {
          bool cond = !is_false_cond(rest);
          f.active = f.parent_active && cond;
          f.taken = cond;
        }
        continue;
      }
      if (word == "else" && !st.empty()) {
        Frame& f = st.back();
        f.active = f.parent_active && !f.taken;
        f.taken = true;
        continue;
      }
      if (word == "endif") {
        if (!st.empty()) st.pop_back();
        continue;
      }
    }
    if (cur_active())
      out.push_back(t);
    else
      ++drop;
  }
  if (dropped) *dropped = drop;
  return out;
}

}  // namespace mg
