# STATUS (each step appends ≤6 lines; newest last)

## v0.1 baseline (2026-11-13)
- Python edition at repo root (stdlib only, 3.7+); 38 tests pass: `python3 tests/test_mfcgraph.py`.
- C++ edition frozen in `cpp-reference/` (41 tests; identical index output to Python on ~4k real headers).
- Commands: index, search, node, callers, callees, impact, trace, msgmap, context, diagnose, status, serve (MCP, 9 tools).
- Index format v1: records MFCGRAPH/F/N/E/S (see mfcgraph_core/index.py).
- Next: docs/PLAN.md step S0. After each step: tests → STATUS.md → commit "S<id>: …" → git push (see CLAUDE.md).

## S0 — golden test harness
- New `tests/golden_test.py` (+ `tests/golden/*.txt`, 9 CLI cases): runs `cli.main` in-process on a temp index of samples/LegacyApp.
- `python3 tests/golden_test.py` compares; `--update` rewrites. Reusable: `run_cases(cases, samples, update)`.
- Tests: 38 passed + golden 9 passed.

## S2a — string literals in function bodies
- `RawFunc.strings = [(line, text)]`, filled by `CppWalker.scan_strings` (adjacent literals joined, whitespace collapsed).
- `extract_cpp.clean_literal(text)`: "" if < 3 letters after removing escapes/printf specs; cut at 200 chars.
- New `tests/test_extract.py` (extractor unit checks). Note: "Export failed" is MainFrm.cpp:69 (PLAN said 68).

## S2b — index format v2
- Header `MFCGRAPH\t2`; `F` gets trailing `mtime size`; new `T\tfunc\tline\ttext`. `load_graph` reads v1 and v2.
- `Graph.texts = [(func_node, line, text)]` (filled in `Resolver.make_calls`); `SrcFile.mtime/size` (v1: 0 / -1).
- Tests: `tests/test_index.py` (+ `tests/data/legacy_v1.mfg` made with v1 code). `tests/run_all.py` runs every suite.

## S2c — search by string literal
- `q_search` also lists `[text] "<literal>"  Func  file:line` (exact text 50, substring 35; below symbol hits).
- `query.norm_text(s)` (NFC + casefold) and `query.text_hits(g, q) -> [(score, func_node, line, text)]` reusable by explore.
- Golden `search_recalc` updated (+1 text hit). Tests in `tests/test_index.py`.

## S3a — member/global variable references (extractor)
- `RawFunc.refs = [(name, recv, line, mode)]` from `CppWalker.scan_refs`: ids after `.`/`->` (recv = previous ident or "?"),
  or starting `m_ g_ s_`; not before `(` or `::`. mode 'w' for assignment ops/++/-- (also `m_a[i] = v`), else 'r'.
- Tests in `tests/test_extract.py` (3 writes of m_nZoom in CLegacyView::OnViewZoom).
