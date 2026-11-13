#include "json.h"

#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace mg {

const JVal* JVal::get(const std::string& k) const {
  if (t != Obj) return nullptr;
  for (auto& kv : o)
    if (kv.first == k) return &kv.second;
  return nullptr;
}

std::string JVal::str(const std::string& k, const std::string& def) const {
  const JVal* v = get(k);
  return (v && v->t == Str) ? v->s : def;
}

int JVal::integer(const std::string& k, int def) const {
  const JVal* v = get(k);
  if (v && v->t == Num) return (int)v->n;
  if (v && v->t == Str) return std::atoi(v->s.c_str());
  return def;
}

bool JVal::boolean(const std::string& k, bool def) const {
  const JVal* v = get(k);
  return (v && v->t == Bool) ? v->b : def;
}

namespace {

struct Parser {
  const std::string& s;
  size_t i = 0;
  std::string err;
  explicit Parser(const std::string& in) : s(in) {}

  void ws() {
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) ++i;
  }
  bool fail(const char* m) {
    if (err.empty()) err = std::string(m) + " at " + std::to_string(i);
    return false;
  }
  static void put_utf8(std::string& o, unsigned cp) {
    if (cp < 0x80) o += (char)cp;
    else if (cp < 0x800) {
      o += (char)(0xC0 | (cp >> 6));
      o += (char)(0x80 | (cp & 0x3F));
    } else if (cp < 0x10000) {
      o += (char)(0xE0 | (cp >> 12));
      o += (char)(0x80 | ((cp >> 6) & 0x3F));
      o += (char)(0x80 | (cp & 0x3F));
    } else {
      o += (char)(0xF0 | (cp >> 18));
      o += (char)(0x80 | ((cp >> 12) & 0x3F));
      o += (char)(0x80 | ((cp >> 6) & 0x3F));
      o += (char)(0x80 | (cp & 0x3F));
    }
  }
  bool hex4(unsigned& v) {
    if (i + 4 > s.size()) return false;
    v = 0;
    for (int k = 0; k < 4; ++k) {
      char c = s[i++];
      v <<= 4;
      if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
      else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
      else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
      else return false;
    }
    return true;
  }
  bool str(std::string& out) {
    if (s[i] != '"') return fail("expected string");
    ++i;
    while (i < s.size()) {
      char c = s[i++];
      if (c == '"') return true;
      if (c != '\\') {
        out += c;
        continue;
      }
      if (i >= s.size()) return fail("bad escape");
      char e = s[i++];
      switch (e) {
        case '"': out += '"'; break;
        case '\\': out += '\\'; break;
        case '/': out += '/'; break;
        case 'b': out += '\b'; break;
        case 'f': out += '\f'; break;
        case 'n': out += '\n'; break;
        case 'r': out += '\r'; break;
        case 't': out += '\t'; break;
        case 'u': {
          unsigned cp;
          if (!hex4(cp)) return fail("bad \\u");
          if (cp >= 0xD800 && cp <= 0xDBFF && i + 6 <= s.size() && s[i] == '\\' && s[i + 1] == 'u') {
            i += 2;
            unsigned lo;
            if (!hex4(lo)) return fail("bad surrogate");
            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
          }
          put_utf8(out, cp);
          break;
        }
        default: return fail("bad escape");
      }
    }
    return fail("unterminated string");
  }
  bool val(JVal& v, int depth) {
    if (depth > 64) return fail("too deep");
    ws();
    if (i >= s.size()) return fail("unexpected end");
    char c = s[i];
    if (c == '{') {
      v.t = JVal::Obj;
      ++i;
      ws();
      if (i < s.size() && s[i] == '}') {
        ++i;
        return true;
      }
      while (true) {
        ws();
        std::string k;
        if (i >= s.size() || !str(k)) return fail("expected key");
        ws();
        if (i >= s.size() || s[i] != ':') return fail("expected ':'");
        ++i;
        JVal x;
        if (!val(x, depth + 1)) return false;
        v.o.push_back({k, std::move(x)});
        ws();
        if (i < s.size() && s[i] == ',') {
          ++i;
          continue;
        }
        if (i < s.size() && s[i] == '}') {
          ++i;
          return true;
        }
        return fail("expected ',' or '}'");
      }
    }
    if (c == '[') {
      v.t = JVal::Arr;
      ++i;
      ws();
      if (i < s.size() && s[i] == ']') {
        ++i;
        return true;
      }
      while (true) {
        JVal x;
        if (!val(x, depth + 1)) return false;
        v.a.push_back(std::move(x));
        ws();
        if (i < s.size() && s[i] == ',') {
          ++i;
          continue;
        }
        if (i < s.size() && s[i] == ']') {
          ++i;
          return true;
        }
        return fail("expected ',' or ']'");
      }
    }
    if (c == '"') {
      v.t = JVal::Str;
      return str(v.s);
    }
    if (s.compare(i, 4, "true") == 0) {
      v.t = JVal::Bool;
      v.b = true;
      i += 4;
      return true;
    }
    if (s.compare(i, 5, "false") == 0) {
      v.t = JVal::Bool;
      i += 5;
      return true;
    }
    if (s.compare(i, 4, "null") == 0) {
      v.t = JVal::Null;
      i += 4;
      return true;
    }
    if (c == '-' || (c >= '0' && c <= '9')) {
      size_t b = i;
      ++i;
      while (i < s.size() && (std::isdigit((unsigned char)s[i]) || s[i] == '.' || s[i] == 'e' || s[i] == 'E' ||
                              s[i] == '+' || s[i] == '-'))
        ++i;
      v.t = JVal::Num;
      v.n = std::strtod(s.substr(b, i - b).c_str(), nullptr);
      return true;
    }
    return fail("unexpected character");
  }
};

}  // namespace

bool json_parse(const std::string& in, JVal& out, std::string& err) {
  Parser p(in);
  out = JVal();
  if (!p.val(out, 0)) {
    err = p.err;
    return false;
  }
  return true;
}

std::string json_quote(const std::string& s) {
  std::string r = "\"";
  for (unsigned char c : s) {
    switch (c) {
      case '"': r += "\\\""; break;
      case '\\': r += "\\\\"; break;
      case '\n': r += "\\n"; break;
      case '\r': r += "\\r"; break;
      case '\t': r += "\\t"; break;
      default:
        if (c < 0x20) {
          char buf[8];
          std::snprintf(buf, sizeof buf, "\\u%04x", c);
          r += buf;
        } else {
          r += (char)c;
        }
    }
  }
  return r + "\"";
}

std::string json_dump(const JVal& v) {
  switch (v.t) {
    case JVal::Null: return "null";
    case JVal::Bool: return v.b ? "true" : "false";
    case JVal::Num: {
      char buf[64];
      if (std::floor(v.n) == v.n && std::fabs(v.n) < 1e15) std::snprintf(buf, sizeof buf, "%.0f", v.n);
      else std::snprintf(buf, sizeof buf, "%.17g", v.n);
      return buf;
    }
    case JVal::Str: return json_quote(v.s);
    case JVal::Arr: {
      std::string r = "[";
      for (size_t i = 0; i < v.a.size(); ++i) r += (i ? "," : "") + json_dump(v.a[i]);
      return r + "]";
    }
    case JVal::Obj: {
      std::string r = "{";
      for (size_t i = 0; i < v.o.size(); ++i) r += (i ? "," : "") + json_quote(v.o[i].first) + ":" + json_dump(v.o[i].second);
      return r + "}";
    }
  }
  return "null";
}

}  // namespace mg
