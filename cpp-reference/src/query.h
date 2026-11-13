// query.h: read-only queries over the graph. Every query returns compact text
// designed to be cheap for an AI agent to read (few tokens, precise locations).
#pragma once
#include <string>

#include "model.h"

namespace mg {

std::string q_search(const Graph& g, const std::string& query, int limit);
std::string q_node(const Graph& g, const std::string& symbol, bool with_code, int max_code_lines);
std::string q_callers(const Graph& g, const std::string& symbol, int depth);
std::string q_callees(const Graph& g, const std::string& symbol, int depth);
std::string q_impact(const Graph& g, const std::string& symbol, int depth);
std::string q_trace(const Graph& g, const std::string& query, int depth);
std::string q_msgmap(const Graph& g, const std::string& cls);
std::string q_context(const Graph& g, const std::string& symbol, int max_code_lines);
std::string q_diagnose(const Graph& g, bool show_names);
std::string q_status(const Graph& g, const std::string& index_path);

}  // namespace mg
