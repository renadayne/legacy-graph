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

## S9 — evaluation + tuning
- `tests/eval_explore.py` (in run_all): recall = must_include functions with body lines in Source; fails if mean < 0.9 or over budget.
- Result on BigApp @8000: recall 1.000 (start 0.940), 14/14 within budget; @6000 1.000, @4000 0.905, @3000 0.833.
- Tuning (each a general rule): low-score functions get full code when it fits the remaining share (unused budget = waste);
  words also match segments of handled id names (IDC_LIST_LINES); Vietnamese symptom phrases ("thông báo", "bấm nút"…) dropped.
- Tried capping code files to src/(2·600): worse at 3000 → reverted.

## S10 — changed-file warning
- explore compares size/mtime of files it would print with the index (`explore_render.changed_files`); changed files: banner
  `⚠ Changed since last index: …; re-run index (code of these files not shown)` and their functions go to Not shown. v1 index: no check.

## S11 — diagnose additions
- `diagnose` adds "string literals indexed: N" and "variable references: T  resolved …%; stored: writes W, reads R" (counts only).

## S13 — performance on a large tree
- `tests/tools/make_big_tree.py <out> [--files 20000] [--bench]`: clones BigApp (classes renamed per copy), benchmarks index/explore.
- 20,022 files: index 13.2 s, load 1.4 s, index 26 MB, peak RAM 437 MB (< 1.5 GB: no SQLite needed for v0.2).
- explore was up to 2.5 s → fixed: cached segment→node word index, word weight spread over > 40 hits, PPR on top 120 seeds with
  precomputed transitions. Now 0.3–1.3 s per query (first call includes cache build). BigApp recall unchanged (1.000).

## S12 — documentation (doc-writer, reviewed)
- README (VI) for v0.2: explore (real output), refs, text search, MCP default tool + `MFCGRAPH_MCP_TOOLS`, `.mcp.json` for VS/VS Code,
  fallback `explore … > ctx.md` + `#file:ctx.md`, stdlib audit list (no tempfile in core; + difflib, collections), ~4,800 lines.
- New `docs/copilot-instructions.md` (EN) to copy into `.github/copilot-instructions.md`.

## S14 — packaging
- `tools/package.py [--out DIR]` → `dist/mfcgraph-py-0.2.zip` (zipfile; excludes __pycache__, .mfcgraph, cpp-reference, .git, .claude).
- `CHANGELOG.md`; VERSION = 0.2.0. v0.2 plan complete (S0–S14).

## v0.3 plan
- `docs/PLAN-v0.3.md`: mixed MFC + Win32 + C (user's diagnose: Win32 switch dispatch, CALLBACK=300, #else=329, Shift-JIS).
- Steps S15 (Win32App sample) … S21. Open questions in §4 (which #ifdef macros; HANDLE_MSG usage). Next: S15.

## S16 — C mode for .c files
- New `mfcgraph_core/cmode.py`: in `.c` files, C++-only keywords (`new class this delete template operator …`) are marked before
  extraction and unmarked after (`protect`, `snapshot`, `restore`), so C names like `void delete(...)`, `struct x *new` parse.
- `index.build_index` applies it to `.c` only (headers stay C++). Tests in `tests/test_extract.py`. (Committed before S15: sample still in progress.)

## S15 — Win32App sample + scenarios
- `samples/Win32App/` (26 files, sample-writer, reviewed): WndProc/DlgProc switch dispatch, HANDLE_MSG, DialogBox(Param), lpfnWndProc,
  SetWindowLongPtr subclass, CreateThread + PostMessage(WM_APP_SAVE_DONE), SetTimer callback, .c files (new/class names, static
  ParseLine twice), #ifdef USE_INI_FILE stub / #else real code, small MFC part. CP932: MainWnd.cpp, OptionsDlg.cpp, ExportDlg.cpp.
- `tests/scenarios_win32.json` (13). Baseline (codepage 932, before S17–S19): recall 0.808; misses: menu/ID → case dispatch (2, 5, 1).

## S17 — #if evaluation (--define / --undef / --undef-unknown)
- New `mfcgraph_core/pp_eval.py`: `PPConfig(defines, undefs, undef_unknown).for_file(is_c) -> FileMacros` (ifdef / eval_if, 3-valued:
  unknown → first branch kept, counted "guessed"); builtins _WIN32 WIN32 _MSC_VER, __cplusplus for non-.c. In-file #define/#undef tracked.
- `lexer.filter_conditionals(tokens, macros=None, stats=None)` (None = v0.2 behaviour). `build_index(..., pp=PPConfig)`; CLI index options.
- Index v3: `D` records keep the config; diagnose "#if conditions: evaluated N, guessed M". Tests: `tests/test_pp.py` (27).

## S18 — Win32 dispatch
- New `mfcgraph_core/win32.py`: `scan_switches` (RawFunc.cases [(label, line, end, parent)], crackers from HANDLE_MSG) and
  `make_dispatch`: id --handled_by--> proc ("case@line"), id --case_calls--> callees inside the case, HANDLE_MSG edges, flag win32-proc.
- explore: seeds get the case line as focus; Flow/Blast UI entries limited to the ids the query reached (SeedResult.ids).
- Ranking: ids handled by > 2 functions (IDOK…) scaled down (GENERIC_ID_FANOUT); leftover budget goes to files between 5% and 15%.
- diagnose "win32: procedures N, dispatch entries M". Win32App recall 0.808 → 0.885; BigApp 1.000. Tests: `tests/test_win32.py` (16).

## S19 — Win32 wiring
- `win32.scan_wiring` / `make_wiring`: DialogBox*/CreateDialog*(IDD, Proc) → Proc --uses_dialog--> dialog + caller --callback--> Proc;
  identifiers used as values that resolve to functions (lpfnWndProc, SetTimer, CreateThread, SetWindowLongPtr…) → callback edge
  (class names, ctors, already-linked calls skipped); callbacks inside `case ID:` → id --case_calls--> proc.
- explore: entry path prefers the queried ids; shared IDOK shown only for this proc's dialogs; calls ≤3 lines before a matched
  message literal seeded (W_NEAR_CALL 0.6). Win32App 0.885, BigApp 1.000. 20k files: index 15.3 s, 470 MB. Tests: test_win32 (27).

## S20 — Win32 evaluation + tuning
- `tests/eval_explore.py --win32` (Win32App, codepage 932, --undef-unknown) added to run_all; `--codepage`, `--undef-unknown` options.
- Tuning (general rules): CJK menu mnemonics "(&S)" stripped from captions; CJK chars count 2 for the min caption length;
  calls just before a STRINGTABLE message use (IDS_/IDP_) are seeded like literal messages.
- Recall @8000: Win32App 1.000 (13/13 in budget), BigApp 1.000. @4000: 0.936 / 0.905; @3000: 0.897 / 0.869.
