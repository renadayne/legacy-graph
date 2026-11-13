# mfcgraph — project rules for Claude Code

Offline code-graph tool for a ~30-year-old C++14/MFC codebase. It feeds GitHub Copilot (the only AI
allowed to see the company source) with small, precise context so bug investigation uses fewer tokens.
Work plan: `docs/PLAN.md` (do ONE step at a time). Background: `docs/research-codegraph.md`.

## Hard constraints (never break)
- Python 3.7+ standard library ONLY. No pip packages, no vendored third-party code.
- No network code of any kind (socket/urllib/http/requests/…); no subprocess/os.system/ctypes/pickle/eval/exec
  in `mfcgraph_core/`. The tool only reads source files and writes `<root>/.mfcgraph/`.
- MCP is stdio only and only loaded by the `serve` command.
- This repo must never contain company code. Test data is synthetic (`samples/`). Never ask the user for real source;
  feedback from the company arrives only as `diagnose` counts or hand-written repros with fake names.
- Deterministic output (sorted iteration, no timestamps in query output) so golden tests are stable.

## Layout
- `mfcgraph.py` launcher → `mfcgraph_core/` (lexer, extract_cpp, extract_rc, resolve, index, query, mcp, cli).
- `tests/test_mfcgraph.py` golden checks on `samples/LegacyApp`. Run: `python3 tests/test_mfcgraph.py`.
- `cpp-reference/` = frozen C++ edition (v0.1). Do NOT update it unless a step says so.

## Conventions
- Tool output (CLI/MCP text) in English; user docs (README) in Vietnamese.
- Keep functions small; keep each module < ~800 lines (split instead).
- Index format is versioned (`MFCGRAPH\t<ver>`); bump the version and keep loading older versions.
- Every behaviour change needs a test in `tests/`; all tests must pass before a step is done.

## Finishing a step (always, automatically)
1. All tests pass (`python3 tests/test_mfcgraph.py` + any step-specific tests).
2. Append ≤6 lines to `docs/STATUS.md`.
3. Commit ONLY that step's files: `git add <files>` (never `git add -A` blindly; never add `.mfcgraph/`),
   message `S<id>: <short summary>` + a body listing changed files and the test result line.
4. `git push` to the current branch. If push fails (no remote, auth, conflict): do NOT force-push, do NOT retry
   in a loop — report the error and leave the commit local.
5. Never commit with failing tests; if a step must stop half-way, leave changes uncommitted and report.

## Working with subagents (cost control)
- Delegate a task to `implementer` (Sonnet) or `doc-writer` (Haiku) ONLY when it fits the brief template in
  `docs/PLAN.md §2`: ≤3 files to touch, exact files to read listed, verifiable by tests. Otherwise do it yourself.
- Give the subagent the brief only — never "explore the repo". Review its diff and run the tests yourself.
