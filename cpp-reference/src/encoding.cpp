#include "encoding.h"

#include <cstdint>
#include <cstdlib>
#include <string>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <iconv.h>
#endif

namespace mg {

namespace {

void append_utf8(std::string& out, uint32_t cp) {
  if (cp < 0x80) {
    out += (char)cp;
  } else if (cp < 0x800) {
    out += (char)(0xC0 | (cp >> 6));
    out += (char)(0x80 | (cp & 0x3F));
  } else if (cp < 0x10000) {
    out += (char)(0xE0 | (cp >> 12));
    out += (char)(0x80 | ((cp >> 6) & 0x3F));
    out += (char)(0x80 | (cp & 0x3F));
  } else {
    out += (char)(0xF0 | (cp >> 18));
    out += (char)(0x80 | ((cp >> 12) & 0x3F));
    out += (char)(0x80 | ((cp >> 6) & 0x3F));
    out += (char)(0x80 | (cp & 0x3F));
  }
}

std::string utf16_to_utf8(const std::string& b, size_t start, bool little) {
  std::string out;
  out.reserve(b.size() / 2);
  size_t n = (b.size() - start) / 2;
  auto unit = [&](size_t i) -> uint32_t {
    unsigned char x = (unsigned char)b[start + 2 * i], y = (unsigned char)b[start + 2 * i + 1];
    return little ? (uint32_t)(x | (y << 8)) : (uint32_t)((x << 8) | y);
  };
  for (size_t i = 0; i < n; ++i) {
    uint32_t u = unit(i);
    if (u >= 0xD800 && u <= 0xDBFF && i + 1 < n) {
      uint32_t v = unit(i + 1);
      if (v >= 0xDC00 && v <= 0xDFFF) {
        append_utf8(out, 0x10000 + ((u - 0xD800) << 10) + (v - 0xDC00));
        ++i;
        continue;
      }
    }
    append_utf8(out, u);
  }
  return out;
}

bool valid_utf8(const std::string& s, bool& all_ascii) {
  all_ascii = true;
  size_t i = 0, n = s.size();
  while (i < n) {
    unsigned char c = (unsigned char)s[i];
    if (c < 0x80) {
      ++i;
      continue;
    }
    all_ascii = false;
    int len = (c >= 0xF0 && c <= 0xF4) ? 4 : (c >= 0xE0) ? 3 : (c >= 0xC2 && c <= 0xDF) ? 2 : 0;
    if (len == 0 || i + len > n) return false;
    for (int k = 1; k < len; ++k)
      if (((unsigned char)s[i + k] & 0xC0) != 0x80) return false;
    i += len;
  }
  return true;
}

// Heuristic for BOM-less UTF-16 LE (some old .rc files): many zero bytes at odd offsets.
bool looks_utf16le(const std::string& b) {
  if (b.size() < 8) return false;
  size_t sample = b.size() < 4096 ? b.size() : 4096;
  size_t zeros_odd = 0, zeros_even = 0;
  for (size_t i = 0; i + 1 < sample; i += 2) {
    if (b[i] == 0) ++zeros_even;
    if (b[i + 1] == 0) ++zeros_odd;
  }
  return zeros_odd > sample / 4 && zeros_even < sample / 50;
}

std::string latin1_to_utf8(const std::string& b) {
  std::string out;
  for (unsigned char c : b) append_utf8(out, c);
  return out;
}

std::string ansi_to_utf8(const std::string& b, int cp, bool& ok) {
  ok = false;
  if (b.empty()) {
    ok = true;
    return {};
  }
#ifdef _WIN32
  int wlen = MultiByteToWideChar((UINT)cp, 0, b.data(), (int)b.size(), nullptr, 0);
  if (wlen <= 0) return latin1_to_utf8(b);
  std::wstring w((size_t)wlen, L'\0');
  MultiByteToWideChar((UINT)cp, 0, b.data(), (int)b.size(), &w[0], wlen);
  // CP1258 stores Vietnamese tone marks as combining characters: compose them (like NFC)
  // so that searching for "nhập" matches regardless of how the file was saved.
  int clen = FoldStringW(MAP_PRECOMPOSED, w.data(), wlen, nullptr, 0);
  if (clen > 0) {
    std::wstring c((size_t)clen, L'\0');
    if (FoldStringW(MAP_PRECOMPOSED, w.data(), wlen, &c[0], clen) > 0) {
      w.swap(c);
      wlen = clen;
    }
  }
  int ulen = WideCharToMultiByte(CP_UTF8, 0, w.data(), wlen, nullptr, 0, nullptr, nullptr);
  std::string out((size_t)ulen, '\0');
  WideCharToMultiByte(CP_UTF8, 0, w.data(), wlen, &out[0], ulen, nullptr, nullptr);
  ok = true;
  return out;
#else
  std::string name = "CP" + std::to_string(cp);
  iconv_t cd = iconv_open("UTF-8", name.c_str());
  if (cd == (iconv_t)-1) return latin1_to_utf8(b);
  std::string out;
  out.resize(b.size() * 4 + 16);
  char* in = const_cast<char*>(b.data());
  size_t inleft = b.size();
  char* o = &out[0];
  size_t oleft = out.size();
  while (inleft > 0) {
    size_t r = iconv(cd, &in, &inleft, &o, &oleft);
    if (r == (size_t)-1) {
      // skip one undecodable byte, emit '?'
      if (oleft > 0) {
        *o++ = '?';
        --oleft;
      }
      ++in;
      --inleft;
    }
  }
  iconv_close(cd);
  out.resize(out.size() - oleft);
  ok = true;
  return out;
#endif
}

}  // namespace

Decoded decode_to_utf8(const std::string& bytes, int ansi_codepage) {
  Decoded d;
  const unsigned char* u = (const unsigned char*)bytes.data();
  size_t n = bytes.size();
  if (n >= 3 && u[0] == 0xEF && u[1] == 0xBB && u[2] == 0xBF) {
    d.utf8 = bytes.substr(3);
    d.encoding = "utf8-bom";
    return d;
  }
  if (n >= 2 && u[0] == 0xFF && u[1] == 0xFE) {
    d.utf8 = utf16_to_utf8(bytes, 2, true);
    d.encoding = "utf16le";
    return d;
  }
  if (n >= 2 && u[0] == 0xFE && u[1] == 0xFF) {
    d.utf8 = utf16_to_utf8(bytes, 2, false);
    d.encoding = "utf16be";
    return d;
  }
  if (looks_utf16le(bytes)) {
    d.utf8 = utf16_to_utf8(bytes, 0, true);
    d.encoding = "utf16le";
    return d;
  }
  bool ascii = true;
  if (valid_utf8(bytes, ascii)) {
    d.utf8 = bytes;
    d.encoding = ascii ? "ascii" : "utf8";
    return d;
  }
  bool ok = false;
  d.utf8 = ansi_to_utf8(bytes, ansi_codepage, ok);
  d.encoding = "ansi:" + std::to_string(ansi_codepage);
  return d;
}

std::string decode_with_label(const std::string& bytes, const std::string& label, int fallback_cp) {
  if (label.compare(0, 5, "ansi:") == 0) {
    int cp = std::atoi(label.c_str() + 5);
    bool ok = false;
    return ansi_to_utf8(bytes, cp ? cp : fallback_cp, ok);
  }
  return decode_to_utf8(bytes, fallback_cp).utf8;
}

}  // namespace mg
