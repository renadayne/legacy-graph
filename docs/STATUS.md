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

## S3b — resolve variable references
- `Graph.refs = [(func_node, line, target, mode)]`, target `Class::field` (class that declares it, via bases) or bare `g_x`/`s_x`.
  Receiver typed like call resolution (`this`, locals, fields). DDX member = 'w'. Index record `R\tfunc\tline\ttarget\tmode`.
- `Resolver.field_owner(cls, name)`, `make_refs`. New stats: refs.total, refs.resolved, refs.writes, texts (not printed yet).

## S3c — `refs` command
- `refs <Class::m_x | m_x>`: per field "N write(s), M read(s)", then writes, reads (`Func  file:line`, DDX tagged).
- `query.q_refs(g, q)`, `query.match_ref_targets(g, q)` (exact, `::suffix`, bare name). Golden cases refs_strpath, refs_values_bare.

## S4 — explore query parser
- New `mfcgraph_core/explore_query.py`: `parse_query(text) -> [Term(kind, value, extra)]`, kinds anchor/path/qualified/id/quoted/ident/word
  (anchor extra=(start,end); path extra="file"|"dir"; words lower-case NFC minus EN/VI stopwords incl. generic bug words).
- Tests: `tests/test_explore_query.py` (24 cases, incl. Vietnamese, NFD input).

## S7a — code window utilities
- New `mfcgraph_core/explore_windows.py`: `windows_for(span, focus, max_lines, radius=6)`, `render(lines, windows, path)`,
  `signature_only(lines, span)`, `elision(path, a, b)`. Signature + closing line always kept; merge gap <= 3; radius 6→4→2→0.
- Tests: `tests/test_explore_windows.py` (13).

## S1 — second sample project + bug scenarios
- `samples/BigApp/` (47 files, MDI, modules Billing/ Report/ Common/; written by sample-writer, reviewed): LOG_ERROR macro, STRINGTABLE ids,
  m_dDiscount written 4x (one via DDX), static RoundTo in 2 files, FormatMoney overload, property sheet, ON_NOTIFY, worker thread PostMessage.
- Encodings: BigApp.rc UTF-16LE, Billing/InvoiceDlg.cpp CP1258, Report/ExportPdf.cpp CP932 (decoded as cp1258 with default codepage: expected).
- `tests/scenarios.json`: 14 scenarios {id, query, must_include ("Name@path" for duplicates), max_chars 8000}.

## S5 — seeding
- New `mfcgraph_core/explore_seed.py`: `seed(graph, terms, scope_dirs=(), query_text="") -> SeedResult(seeds{node:(w,reason)}, exact,
  pinned_files, scope_dirs, focus{node:lines}, file_focus, unmatched, suggestions, texts)`. Weights at top of file (docstring explains).
- Extras: word == directory name -> scope; captions found verbatim in free query text count as quoted; duplicates prefer pinned/scope files.
- Extractor/resolver: resource/message ids used in bodies become refs (target "IDS_X"), so `AfxMessageBox(IDS_X)` is findable.
- Tests: `tests/test_explore_seed.py` (19, LegacyApp + BigApp).

## S6 — ranking + spine
- New `mfcgraph_core/explore_rank.py`: `rank(graph, seeds, scope_dirs) -> (scores{node:float}, spine[[node]])`. PPR (restart 0.3, 20 it.)
  on radius-3 subgraph, conf-weighted edges, class<->method edge 0.3, externals never entered; out-of-scope x0.2; spine x2.
- Spine: forward shortest paths (<=6) between top-4 function seeds; lone seed -> path from nearest UI/msg-handler entry.
- Seed tweak: ctor/dtor no longer get word matches (name = class name). Tests: `tests/test_explore.py` (6).

## S7b — budget allocation + assembly
- New `mfcgraph_core/explore.py`: `explore(graph, query, budget=None, scope=None) -> str` (parse → seed → rank → render).
- New `mfcgraph_core/explore_render.py`: default_budget (8k/12k/16k), select_functions, allocate (file weight, 15% cut, min 600, max 70%,
  exact full first, windows, signatures), Flow / Source / Blast radius / Not shown / Did you mean sections (≤10 lines each).
- Budget is hard: source share grows while room remains, then lowest-priority functions degrade (full→window→sig→dropped).

## S8 — CLI + MCP
- CLI: `explore <query> [--budget N] [--scope DIR]` (golden: explore_export, explore_anchor, explore_typo).
- MCP: default tool list = `mfc_explore` only; `MFCGRAPH_MCP_TOOLS=explore,refs,trace,...|all` enables more (disabled calls refused).
  New tools mfc_explore, mfc_refs; INSTRUCTIONS rewritten (explore first, treat source as read, MFC-called flags).
- `mcp.enabled_tools(env)`, `mcp.tool_list(env)`, `run_mcp_server(path, stdin=None, stdout=None)` (testable in-process).
