#include "util.h"

#include <cctype>
#include <cstdio>
#include <fstream>
#include <sstream>

namespace mg {

std::string lower(const std::string& s) {
  std::string r = s;
  for (auto& c : r) c = (char)std::tolower((unsigned char)c);
  return r;
}

bool icontains(const std::string& hay, const std::string& needle) {
  if (needle.empty()) return true;
  return lower(hay).find(lower(needle)) != std::string::npos;
}

bool iequals(const std::string& a, const std::string& b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i)
    if (std::tolower((unsigned char)a[i]) != std::tolower((unsigned char)b[i])) return false;
  return true;
}

bool starts_with(const std::string& s, const std::string& p) {
  return s.size() >= p.size() && s.compare(0, p.size(), p) == 0;
}

bool ends_with(const std::string& s, const std::string& p) {
  return s.size() >= p.size() && s.compare(s.size() - p.size(), p.size(), p) == 0;
}

std::string trim(const std::string& s) {
  size_t b = 0, e = s.size();
  while (b < e && std::isspace((unsigned char)s[b])) ++b;
  while (e > b && std::isspace((unsigned char)s[e - 1])) --e;
  return s.substr(b, e - b);
}

std::vector<std::string> split(const std::string& s, char sep) {
  std::vector<std::string> out;
  std::string cur;
  for (char c : s) {
    if (c == sep) {
      out.push_back(cur);
      cur.clear();
    } else {
      cur += c;
    }
  }
  out.push_back(cur);
  return out;
}

std::string join(const std::vector<std::string>& v, const std::string& sep) {
  std::string r;
  for (size_t i = 0; i < v.size(); ++i) {
    if (i) r += sep;
    r += v[i];
  }
  return r;
}

std::string replace_all(std::string s, const std::string& from, const std::string& to) {
  if (from.empty()) return s;
  size_t pos = 0;
  while ((pos = s.find(from, pos)) != std::string::npos) {
    s.replace(pos, from.size(), to);
    pos += to.size();
  }
  return s;
}

bool is_all_caps_ident(const std::string& s) {
  if (s.size() < 2) return false;
  bool letter = false;
  for (char c : s) {
    if (c >= 'A' && c <= 'Z') letter = true;
    else if (!((c >= '0' && c <= '9') || c == '_')) return false;
  }
  return letter;
}

bool read_file_bytes(const fs::path& p, std::string& out) {
  std::ifstream f(p, std::ios::binary);
  if (!f) return false;
  std::ostringstream ss;
  ss << f.rdbuf();
  out = ss.str();
  return true;
}

bool write_file_bytes(const fs::path& p, const std::string& data) {
  std::ofstream f(p, std::ios::binary | std::ios::trunc);
  if (!f) return false;
  f.write(data.data(), (std::streamsize)data.size());
  return (bool)f;
}

uint64_t fnv1a(const std::string& data) {
  uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : data) {
    h ^= c;
    h *= 1099511628211ULL;
  }
  return h;
}

std::string hex64(uint64_t v) {
  char buf[17];
  std::snprintf(buf, sizeof buf, "%016llx", (unsigned long long)v);
  return buf;
}

std::string esc(const std::string& s) {
  std::string r;
  r.reserve(s.size());
  for (char c : s) {
    switch (c) {
      case '\\': r += "\\\\"; break;
      case '\t': r += "\\t"; break;
      case '\n': r += "\\n"; break;
      case '\r': r += "\\r"; break;
      default: r += c;
    }
  }
  return r;
}

std::string unesc(const std::string& s) {
  std::string r;
  r.reserve(s.size());
  for (size_t i = 0; i < s.size(); ++i) {
    if (s[i] == '\\' && i + 1 < s.size()) {
      char n = s[++i];
      if (n == 't') r += '\t';
      else if (n == 'n') r += '\n';
      else if (n == 'r') r += '\r';
      else r += n;
    } else {
      r += s[i];
    }
  }
  return r;
}

fs::path u8_to_path(const std::string& u8) { return fs::u8path(u8); }

std::string path_to_u8(const fs::path& p) { return p.generic_u8string(); }

}  // namespace mg
