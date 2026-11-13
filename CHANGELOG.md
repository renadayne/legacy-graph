# Changelog

## 0.3.0 — 2026-11-13
### Added
- Win32 API support for codebases that mix MFC, Win32 and C:
  - `switch`/`case` window and dialog procedures: menu / button / accelerator → `case ID:` → the code in that case
    (`handled_by` with the case line, `case_calls` to functions called there), `HANDLE_MSG` crackers; flag `win32-proc`.
  - Wiring: `DialogBox*`/`CreateDialog*(IDD, Proc)` links the dialog (captions, controls) to its procedure; function
    names passed as values (`lpfnWndProc`, `SetTimer`, `CreateThread`, `SetWindowLongPtr`…) become callback edges.
- C mode for `.c` files: `new`, `class`, `this`, `delete`, `template`… are ordinary identifiers.
- `index --define "A;B=1" --undef "C" --undef-unknown`: evaluate `#if/#ifdef/#elif` instead of always keeping the first
  branch (3-valued: undecidable conditions keep the old behaviour and are counted as "guessed").
- `diagnose`: C file count, `#if conditions: evaluated / guessed`, Win32 procedures / dispatch entries / wiring links.
- Sample `samples/Win32App` (26 files, Shift-JIS, mixed) + 13 scenarios; `tests/eval_explore.py --win32` (recall 1.0).

### Changed
- Index format v3 (`D` records keep the --define/--undef configuration); v1/v2 still load.
- explore: Flow/Blast UI entries limited to the ids the query reached; generic ids (IDOK…) down-weighted in ranking;
  leftover budget may show files between 5% and 15% relevance; functions called just before a matched error message
  (literal or STRINGTABLE id) are seeded; CJK menu mnemonics `(&S)` ignored when matching captions.

### Performance (20,022 files)
- Index 15 s, peak RAM ~470 MB, explore 0.4–1.3 s.

## 0.2.0 — 2026-11-13
### Added
- `explore <query>` / MCP tool `mfc_explore`: one call returns line-numbered source of the most relevant functions,
  the call flow between them (including MFC hops: menu/accelerator → command ID → handler, PostMessage → ON_MESSAGE),
  blast radius, names not shown and "did you mean" suggestions, always within a character budget
  (default 8,000 / 12,000 / 16,000 by project size; `--budget`, `--scope`).
  Query forms: bug description (EN/VI), names, `Class::Method`, `File.cpp:120[-140]`, directory, caption, ID, error text.
- `refs <Class::m_field>`: where a member variable is written (incl. DDX) and read.
- `search` also finds string literals (case-insensitive, Vietnamese compared after NFC).
- Warning banner when files changed after the last index (their code is not shown).
- `diagnose`: string literal count, variable-reference resolution rate.
- Sample project `samples/BigApp` (47 files) and 14 evaluation scenarios (`tests/eval_explore.py`: recall 1.0).
- `tests/run_all.py`, golden CLI tests, `tests/tools/make_big_tree.py` benchmark, `tools/package.py`.
- `docs/copilot-instructions.md`; MCP config examples for Visual Studio and VS Code in README.

### Changed
- MCP exposes only `mfc_explore` by default; `MFCGRAPH_MCP_TOOLS=explore,trace,...|all` enables the others.
- Index format v2 (`MFCGRAPH\t2`): `F` records carry mtime/size, new `T` (string literal) and `R` (variable / id
  reference) records. v1 indexes still load (re-index to use the new features).

### Performance (20,022 files)
- Index 13 s, peak RAM ~440 MB, explore 0.3–1.3 s.

## 0.1.0
- Python edition (stdlib only): index, search, node, callers, callees, impact, trace, msgmap, context, diagnose,
  status, serve (MCP, 9 tools). C++ edition frozen in `cpp-reference/`.
