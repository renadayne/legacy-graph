// json.h: minimal JSON reader/writer, just enough for MCP JSON-RPC over stdio.
#pragma once
#include <string>
#include <utility>
#include <vector>

namespace mg {

struct JVal {
  enum T { Null, Bool, Num, Str, Arr, Obj } t = Null;
  bool b = false;
  double n = 0;
  std::string s;
  std::vector<JVal> a;
  std::vector<std::pair<std::string, JVal>> o;

  const JVal* get(const std::string& k) const;
  std::string str(const std::string& k, const std::string& def = "") const;
  int integer(const std::string& k, int def) const;
  bool boolean(const std::string& k, bool def) const;
};

bool json_parse(const std::string& in, JVal& out, std::string& err);
std::string json_quote(const std::string& s);  // returns "..." with escapes
std::string json_dump(const JVal& v);

}  // namespace mg
