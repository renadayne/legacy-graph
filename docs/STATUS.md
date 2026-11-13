# STATUS (each step appends ≤6 lines; newest last)

## v0.1 baseline (2026-11-13)
- Python edition at repo root (stdlib only, 3.7+); 38 tests pass: `python3 tests/test_mfcgraph.py`.
- C++ edition frozen in `cpp-reference/` (41 tests; identical index output to Python on ~4k real headers).
- Commands: index, search, node, callers, callees, impact, trace, msgmap, context, diagnose, status, serve (MCP, 9 tools).
- Index format v1: records MFCGRAPH/F/N/E/S (see mfcgraph_core/index.py).
- Next: docs/PLAN.md step S0. After each step: tests → STATUS.md → commit "S<id>: …" → git push (see CLAUDE.md).
