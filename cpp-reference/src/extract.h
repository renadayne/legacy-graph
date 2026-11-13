// extract.h: turns tokens of one file into raw facts.
#pragma once
#include <vector>

#include "lexer.h"
#include "model.h"

namespace mg {

// C/C++ source or header. Sets files[file_index].brace_error when braces do not balance.
void extract_cpp(const std::vector<Token>& toks, int file_index, RawData& out);

// Windows resource script (.rc / .rc2 / .dlg).
void extract_rc(const std::vector<Token>& toks, int file_index, RawData& out);

}  // namespace mg
