// encoding.h: detect source-file encoding and convert to UTF-8.
// Handles UTF-8 (with/without BOM), UTF-16 LE/BE (typical for .rc files),
// and legacy ANSI code pages such as 1258 (Vietnamese) or 932 (Japanese).
#pragma once
#include <string>

namespace mg {

struct Decoded {
  std::string utf8;      // converted text
  std::string encoding;  // "ascii", "utf8", "utf8-bom", "utf16le", "utf16be", "ansi:1258", ...
};

// ansi_codepage is used only when the bytes are not valid UTF-8.
Decoded decode_to_utf8(const std::string& bytes, int ansi_codepage);

// Re-decode using a previously detected encoding label (for code snippets).
std::string decode_with_label(const std::string& bytes, const std::string& label, int fallback_cp);

}  // namespace mg
