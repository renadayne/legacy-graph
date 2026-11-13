#include "index.h"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>

#include "encoding.h"
#include "extract.h"
#include "lexer.h"
#include "resolve.h"
#include "util.h"

namespace mg {

namespace {

const std::set<std::string>& cpp_exts() {
  static const std::set<std::string> s = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inl", ".ipp"};
  return s;
}
const std::set<std::string>& rc_exts() {
  static const std::set<std::string> s = {".rc", ".rc2", ".dlg"};
  return s;
}
const std::set<std::string>& default_skip_dirs() {
  static const std::set<std::string> s = {".git", ".svn", ".hg", ".vs", ".vscode", ".mfcgraph", "debug", "release",
                                          "x64", "win32", "ipch", "obj", "bin", "node_modules", "packages",
                                          "unicode debug", "unicode release"};
  return s;
}

std::string now_string() {
  std::time_t t = std::time(nullptr);
  char buf[64];
  std::strftime(buf, sizeof buf, "%Y-%m-%d %H:%M:%S", std::localtime(&t));
  return buf;
}

}  // namespace

std::string index_path_for_root(const std::string& root) {
  return path_to_u8(u8_to_path(root) / ".mfcgraph" / "index.mfg");
}

bool build_index(const IndexOptions& opt, Graph& g, std::string& err) {
  fs::path root = u8_to_path(opt.root);
  std::error_code ec;
  if (!fs::is_directory(root, ec)) {
    err = "not a directory: " + opt.root;
    return false;
  }
  root = fs::absolute(root, ec);
  std::set<std::string> skip = default_skip_dirs();
  for (auto& x : opt.excludes) skip.insert(lower(x));

  std::vector<fs::path> files;
  fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec), end;
  for (; it != end; it.increment(ec)) {
    if (ec) {
      ec.clear();
      continue;
    }
    const fs::path& p = it->path();
    if (it->is_directory(ec)) {
      if (skip.count(lower(path_to_u8(p.filename())))) it.disable_recursion_pending();
      continue;
    }
    if (!it->is_regular_file(ec)) continue;
    std::string ext = lower(path_to_u8(p.extension()));
    if (!cpp_exts().count(ext) && !rc_exts().count(ext)) continue;
    auto sz = it->file_size(ec);
    if (ec || sz > opt.max_file_bytes) continue;
    files.push_back(p);
  }
  // Deterministic order (same as the Python edition): sort by relative path.
  // lexically_relative does not resolve symlinks/junctions, so a linked file keeps its own path.
  std::vector<std::pair<std::string, fs::path>> ordered;
  ordered.reserve(files.size());
  for (const fs::path& p : files) ordered.push_back({path_to_u8(p.lexically_relative(root)), p});
  std::sort(ordered.begin(), ordered.end(),
            [](const std::pair<std::string, fs::path>& a, const std::pair<std::string, fs::path>& b) {
              return a.first < b.first;
            });

  RawData raw;
  raw.files.reserve(files.size());
  size_t done = 0;
  for (const auto& entry : ordered) {
    const fs::path& p = entry.second;
    std::string bytes;
    if (!read_file_bytes(p, bytes)) continue;
    SrcFile sf;
    sf.path = entry.first.empty() ? path_to_u8(p) : entry.first;
    Decoded d = decode_to_utf8(bytes, opt.codepage);
    sf.encoding = d.encoding;
    sf.hash = fnv1a(bytes);
    sf.lines = 1;
    for (char c : d.utf8)
      if (c == '\n') ++sf.lines;
    int fi = (int)raw.files.size();
    raw.files.push_back(sf);
    bool is_rc = rc_exts().count(lower(path_to_u8(p.extension()))) > 0;
    std::vector<Token> toks = lex(d.utf8, is_rc);
    size_t dropped = 0;
    std::vector<Token> active = filter_conditionals(toks, &dropped);
    raw.files[fi].skipped_tokens = dropped;
    if (is_rc) extract_rc(active, fi, raw);
    else extract_cpp(active, fi, raw);
    ++done;
    if (opt.verbose && done % 500 == 0) std::cerr << "  " << done << "/" << files.size() << " files\n";
  }

  g = Graph();
  g.root = path_to_u8(root);
  g.codepage = opt.codepage;
  g.created = now_string();
  resolve(raw, g);
  return true;
}

// ---------------- persistence ----------------
// Plain text, one record per line, tab separated, escaped. Easy to audit and diff.

bool save_graph(const Graph& g, const std::string& path, std::string& err) {
  fs::path p = u8_to_path(path);
  std::error_code ec;
  fs::create_directories(p.parent_path(), ec);
  std::ostringstream o;
  o << "MFCGRAPH\t1\t" << esc(g.root) << "\t" << g.codepage << "\t" << esc(g.created) << "\n";
  for (const SrcFile& f : g.files)
    o << "F\t" << esc(f.path) << "\t" << esc(f.encoding) << "\t" << hex64(f.hash) << "\t" << f.lines << "\t"
      << (f.brace_error ? 1 : 0) << "\t" << f.skipped_tokens << "\n";
  for (const Node& n : g.nodes)
    o << "N\t" << n.id << "\t" << esc(n.kind) << "\t" << esc(n.name) << "\t" << esc(n.qname) << "\t" << n.file << "\t"
      << n.line << "\t" << n.end << "\t" << n.owner << "\t" << esc(n.flags) << "\t" << esc(n.sig) << "\t"
      << esc(n.extra) << "\n";
  for (const Edge& e : g.edges)
    o << "E\t" << e.src << "\t" << e.dst << "\t" << esc(e.kind) << "\t" << e.file << "\t" << e.line << "\t"
      << esc(e.conf) << "\t" << esc(e.extra) << "\n";
  for (auto& kv : g.stats) o << "S\t" << esc(kv.first) << "\t" << esc(kv.second) << "\n";
  if (!write_file_bytes(p, o.str())) {
    err = "cannot write " + path;
    return false;
  }
  return true;
}

bool load_graph(const std::string& path, Graph& g, std::string& err) {
  std::string data;
  if (!read_file_bytes(u8_to_path(path), data)) {
    err = "cannot read index " + path + " (run: mfcgraph index <root>)";
    return false;
  }
  g = Graph();
  std::istringstream in(data);
  std::string line;
  bool header = false;
  while (std::getline(in, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    std::vector<std::string> f = split(line, '\t');
    for (auto& x : f) x = unesc(x);
    if (f[0] == "MFCGRAPH") {
      if (f.size() < 5 || f[1] != "1") {
        err = "unsupported index version";
        return false;
      }
      g.root = f[2];
      g.codepage = std::atoi(f[3].c_str());
      g.created = f[4];
      header = true;
    } else if (f[0] == "F" && f.size() >= 7) {
      SrcFile s;
      s.path = f[1];
      s.encoding = f[2];
      s.hash = std::strtoull(f[3].c_str(), nullptr, 16);
      s.lines = std::atoi(f[4].c_str());
      s.brace_error = f[5] == "1";
      s.skipped_tokens = (size_t)std::strtoull(f[6].c_str(), nullptr, 10);
      g.files.push_back(s);
    } else if (f[0] == "N" && f.size() >= 12) {
      Node n;
      n.id = std::atoi(f[1].c_str());
      n.kind = f[2];
      n.name = f[3];
      n.qname = f[4];
      n.file = std::atoi(f[5].c_str());
      n.line = std::atoi(f[6].c_str());
      n.end = std::atoi(f[7].c_str());
      n.owner = std::atoi(f[8].c_str());
      n.flags = f[9];
      n.sig = f[10];
      n.extra = f[11];
      g.nodes.push_back(n);
    } else if (f[0] == "E" && f.size() >= 8) {
      Edge e;
      e.src = std::atoi(f[1].c_str());
      e.dst = std::atoi(f[2].c_str());
      e.kind = f[3];
      e.file = std::atoi(f[4].c_str());
      e.line = std::atoi(f[5].c_str());
      e.conf = f[6];
      e.extra = f[7];
      g.edges.push_back(e);
    } else if (f[0] == "S" && f.size() >= 3) {
      g.stats[f[1]] = f[2];
    }
  }
  if (!header) {
    err = "not an mfcgraph index: " + path;
    return false;
  }
  for (size_t i = 0; i < g.nodes.size(); ++i)
    if (g.nodes[i].id != (int)i) {
      err = "corrupt index (node ids)";
      return false;
    }
  for (const Edge& e : g.edges)
    if (e.src < 0 || e.dst < 0 || e.src >= (int)g.nodes.size() || e.dst >= (int)g.nodes.size()) {
      err = "corrupt index (edges)";
      return false;
    }
  g.build_adjacency();
  return true;
}

std::string find_index_upwards(const std::string& start) {
  std::error_code ec;
  fs::path p = fs::absolute(u8_to_path(start), ec);
  while (!p.empty()) {
    fs::path cand = p / ".mfcgraph" / "index.mfg";
    if (fs::exists(cand, ec)) return path_to_u8(cand);
    fs::path parent = p.parent_path();
    if (parent == p) break;
    p = parent;
  }
  return "";
}

}  // namespace mg
