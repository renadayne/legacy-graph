// mcp.h: Model Context Protocol server over stdio (newline-delimited JSON-RPC 2.0).
// No sockets, no network: the IDE starts this process and talks through stdin/stdout.
#pragma once
#include <string>

namespace mg {

int run_mcp_server(const std::string& index_path);

}  // namespace mg
