// mfcgraph: offline code graph for legacy C++/MFC codebases.
// No network code, no telemetry, no auto-update. See README.md.
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include "index.h"
#include "mcp.h"
#include "query.h"
#include "util.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

using namespace mg;

namespace {

const char* kVersion = "0.1.0";

void usage() {
  std::cout <<
      R"(mfcgraph )" << kVersion << R"( - offline code graph for C++/MFC (no network, no telemetry)

Usage:
  mfcgraph index <root> [--codepage 1258] [--exclude dir1;dir2] [-v]
  mfcgraph search   <text>                 classes, functions, IDs, menu/dialog captions
  mfcgraph node     <symbol> [--no-code]   location, signature, flags, source
  mfcgraph callers  <symbol> [--depth 5]   incl. message map -> menu/accelerator/toolbar
  mfcgraph callees  <symbol> [--depth 2]
  mfcgraph impact   <symbol> [--depth 5]   what is affected if this changes
  mfcgraph trace    <menu text | ID_xxx | IDD_xxx> [--depth 2]
  mfcgraph msgmap   <Class>
  mfcgraph context  <symbol> [--lines 80]  Markdown context pack for an AI agent
  mfcgraph diagnose [--show-names]         counts only, safe to share outside
  mfcgraph status
  mfcgraph serve                           MCP server on stdin/stdout (for Copilot)

Common options:
  --root <dir>    project root that contains .mfcgraph/ (default: search upward from cwd)
  --index <file>  explicit index file
)";
}

struct Args {
  std::vector<std::string> pos;
  std::string root, index, exclude;
  int codepage = 1258, depth = -1, lines = 80;
  bool no_code = false, show_names = false, verbose = false;
};

Args parse(int argc, char** argv) {
  Args a;
  for (int i = 2; i < argc; ++i) {
    std::string s = argv[i];
    auto next = [&](std::string& out) {
      if (i + 1 < argc) out = argv[++i];
    };
    std::string v;
    if (s == "--root") next(a.root);
    else if (s == "--index") next(a.index);
    else if (s == "--exclude") next(a.exclude);
    else if (s == "--codepage") {
      next(v);
      a.codepage = std::atoi(v.c_str());
    } else if (s == "--depth") {
      next(v);
      a.depth = std::atoi(v.c_str());
    } else if (s == "--lines") {
      next(v);
      a.lines = std::atoi(v.c_str());
    } else if (s == "--no-code") a.no_code = true;
    else if (s == "--show-names") a.show_names = true;
    else if (s == "-v" || s == "--verbose") a.verbose = true;
    else a.pos.push_back(s);
  }
  return a;
}

std::string locate_index(const Args& a) {
  if (!a.index.empty()) return a.index;
  if (!a.root.empty()) return index_path_for_root(a.root);
  std::error_code ec;
  return find_index_upwards(path_to_u8(fs::current_path(ec)));
}

std::string rest(const Args& a) { return join(a.pos, " "); }

}  // namespace

int main(int argc, char** argv) {
#ifdef _WIN32
  SetConsoleOutputCP(CP_UTF8);
#endif
  if (argc < 2) {
    usage();
    return 1;
  }
  std::string cmd = argv[1];
  if (cmd == "-h" || cmd == "--help" || cmd == "help") {
    usage();
    return 0;
  }
  if (cmd == "version" || cmd == "--version") {
    std::cout << "mfcgraph " << kVersion << "\n";
    return 0;
  }
  Args a = parse(argc, argv);

  if (cmd == "index") {
    IndexOptions opt;
    opt.root = a.pos.empty() ? (a.root.empty() ? "." : a.root) : a.pos[0];
    opt.codepage = a.codepage;
    opt.verbose = a.verbose;
    if (!a.exclude.empty())
      for (auto& x : split(a.exclude, ';'))
        if (!trim(x).empty()) opt.excludes.push_back(trim(x));
    auto t0 = std::chrono::steady_clock::now();
    Graph g;
    std::string err;
    if (!build_index(opt, g, err)) {
      std::cerr << "error: " << err << "\n";
      return 2;
    }
    std::string path = index_path_for_root(g.root);
    if (!save_graph(g, path, err)) {
      std::cerr << "error: " << err << "\n";
      return 2;
    }
    double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::cout << "Indexed " << g.stats["files.total"] << " files in " << sec << " s -> " << path << "\n";
    std::cout << "  classes " << g.stats["classes"] << ", functions " << g.stats["functions.defined"]
              << ", message-map entries " << g.stats["msgmap.entries"] << ", dialogs " << g.stats["rc.dialogs"]
              << ", menu items " << g.stats["rc.menu_items"] << "\n";
    std::cout << "Run 'mfcgraph diagnose' for quality numbers.\n";
    return 0;
  }

  std::string ipath = locate_index(a);
  if (ipath.empty()) {
    std::cerr << "error: no .mfcgraph/index.mfg found. Run 'mfcgraph index <root>' or pass --root.\n";
    return 2;
  }
  if (cmd == "serve") return run_mcp_server(ipath);

  Graph g;
  std::string err;
  if (!load_graph(ipath, g, err)) {
    std::cerr << "error: " << err << "\n";
    return 2;
  }
  auto need_arg = [&]() {
    if (a.pos.empty()) {
      std::cerr << "error: missing argument for '" << cmd << "'\n";
      return false;
    }
    return true;
  };
  std::string out;
  if (cmd == "search") {
    if (!need_arg()) return 1;
    out = q_search(g, rest(a), 40);
  } else if (cmd == "node") {
    if (!need_arg()) return 1;
    out = q_node(g, rest(a), !a.no_code, a.lines);
  } else if (cmd == "callers") {
    if (!need_arg()) return 1;
    out = q_callers(g, rest(a), a.depth > 0 ? a.depth : 5);
  } else if (cmd == "callees") {
    if (!need_arg()) return 1;
    out = q_callees(g, rest(a), a.depth > 0 ? a.depth : 2);
  } else if (cmd == "impact") {
    if (!need_arg()) return 1;
    out = q_impact(g, rest(a), a.depth > 0 ? a.depth : 5);
  } else if (cmd == "trace") {
    if (!need_arg()) return 1;
    out = q_trace(g, rest(a), a.depth > 0 ? a.depth : 2);
  } else if (cmd == "msgmap") {
    if (!need_arg()) return 1;
    out = q_msgmap(g, rest(a));
  } else if (cmd == "context") {
    if (!need_arg()) return 1;
    out = q_context(g, rest(a), a.lines);
  } else if (cmd == "diagnose") {
    out = q_diagnose(g, a.show_names);
  } else if (cmd == "status") {
    out = q_status(g, ipath);
  } else {
    std::cerr << "unknown command: " << cmd << "\n";
    usage();
    return 1;
  }
  std::cout << out;
  return 0;
}
