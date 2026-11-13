// lexer.h: tolerant tokenizer for C/C++ and Windows .rc files.
// It never fails: unknown bytes become punctuation tokens, unterminated
// strings/comments end at the line / file end.
#pragma once
#include <string>
#include <vector>

namespace mg {

enum class TK { Ident, Number, String, Char, Punct, PP };

struct Token {
  TK k;
  std::string s;  // identifier / punctuation text, string content, or directive text (without '#')
  int line;
};

// rc_mode: "" inside a string is an escaped quote (resource-compiler syntax)
std::vector<Token> lex(const std::string& src, bool rc_mode);

// Keeps the first active branch of each #if/#ifdef/#elif/#else chain
// ("#if 0" is treated as false). Returns the number of dropped tokens.
std::vector<Token> filter_conditionals(const std::vector<Token>& in, size_t* dropped);

}  // namespace mg
