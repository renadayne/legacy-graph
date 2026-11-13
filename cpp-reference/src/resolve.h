// resolve.h: turns raw facts into a graph with typed, confidence-tagged edges.
#pragma once
#include "model.h"

namespace mg {

void resolve(const RawData& raw, Graph& g);

}  // namespace mg
