# Changelog

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
