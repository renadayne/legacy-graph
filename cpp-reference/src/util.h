// mfcgraph - offline code graph for legacy C++/MFC codebases
// util.h: small string / file helpers. No third-party dependencies.
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <filesystem>

namespace mg {

namespace fs = std::filesystem;

std::string lower(const std::string& s);
bool icontains(const std::string& hay, const std::string& needle);
bool iequals(const std::string& a, const std::string& b);
bool starts_with(const std::string& s, const std::string& p);
bool ends_with(const std::string& s, const std::string& p);
std::string trim(const std::string& s);
std::vector<std::string> split(const std::string& s, char sep);
std::string join(const std::vector<std::string>& v, const std::string& sep);
std::string replace_all(std::string s, const std::string& from, const std::string& to);

// [A-Z0-9_]+ with at least one letter and length >= 2 (typical macro spelling)
bool is_all_caps_ident(const std::string& s);

bool read_file_bytes(const fs::path& p, std::string& out);
bool write_file_bytes(const fs::path& p, const std::string& data);

uint64_t fnv1a(const std::string& data);
std::string hex64(uint64_t v);

// Escape for the tab-separated index format: \t \n \r and backslash.
std::string esc(const std::string& s);
std::string unesc(const std::string& s);

fs::path u8_to_path(const std::string& u8);
std::string path_to_u8(const fs::path& p);

}  // namespace mg
