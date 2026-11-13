// index.h: scanning a source tree, and saving / loading the graph.
#pragma once
#include <string>
#include <vector>

#include "model.h"

namespace mg {

struct IndexOptions {
  std::string root;
  int codepage = 1258;                // ANSI code page for non-UTF-8 files
  std::vector<std::string> excludes;  // extra directory names to skip (case-insensitive)
  size_t max_file_bytes = 8u << 20;   // skip generated monsters
  bool verbose = false;
};

// Builds the graph. Returns false and sets err on failure.
bool build_index(const IndexOptions& opt, Graph& g, std::string& err);

std::string index_path_for_root(const std::string& root);
bool save_graph(const Graph& g, const std::string& path, std::string& err);
bool load_graph(const std::string& path, Graph& g, std::string& err);

// Finds <dir>/.mfcgraph/index.mfg starting at `start` and walking up.
std::string find_index_upwards(const std::string& start);

}  // namespace mg
