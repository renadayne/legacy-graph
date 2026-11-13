# What we take from CodeGraph (colbymchenry/codegraph)

Studied 2026-11-13 at commit f72c9d2 (public, MIT). Read so you do not have to re-research.
If you need detail, the relevant upstream files are: `src/mcp/server-instructions.ts` (agent playbook),
`src/mcp/tools.ts` (`handleExplore`, `getExploreOutputBudget`, `EXPLORE_ALLOCATION`),
`src/mcp/explore-dedup.ts`, `src/graph/traversal.ts`, `src/search/query-*.ts`. Clone read-only if needed;
do not copy code (different language anyway), copy ideas.

## 1. One primary tool
- Default MCP surface is ONE tool, `codegraph_explore`. Other tools (node, search, callers, callees, impact,
  files, status) exist but are hidden unless an env var enables them. Their rationale: measured agent behaviour —
  one strong tool causes fewer wrong tool picks than a menu of narrow tools, and saves tool-list tokens.
- For us: Copilot is the consumer (weaker model, credit-limited) → even stronger reason for one tool.

## 2. What one explore call returns
- Input: a natural-language question OR a bag of symbol names / file paths / `file:line` anchors.
- Output (capped): verbatim, line-numbered source of the relevant symbols grouped by file ("treat as already
  Read"), the call paths among the named symbols (including synthesized dynamic-dispatch hops, tagged
  heuristic), a blast-radius summary, and a short "not shown — call explore again with these names" list.
- Empty/missed names → lexical-match report + "did you mean" candidates. Never silently substitutes a
  mistyped name as a flow endpoint.

## 3. How context is chosen (the important part)
- Seeding: every symbol the query names is resolved to its substantive definition and injected as a seed,
  even if full-text ranking would drop it. `Class::method` and `file:line` are EXACT targets: always first,
  never reduced to a signature. File paths in the query are PINNED (guaranteed admission, ranked first).
- Graph glue: pull in callers/callees of seeds, but only inside files already surfaced (bridging methods
  the search would miss), with an importance boost.
- Flow spine: when several names are given, the path between them is the answer; spine files are boosted
  and exempt from pruning.
- Budget: total output chars scaled by project size (~13K–24K), kept under the host's inline tool-result cap
  (above it the host spills the result to a file and the agent Reads it back — defeating the purpose).
- Allocation: each file gets a share of the budget proportional to its relevance weight, decided up front.
  Files below ~15% of the top file's weight get NO source (path + symbol names only, still listed so the agent
  can ask). Minimum useful slice ~700 chars (a fragment is worse than a pointer). Single file ≤70% unless named.
- Inside a file: windows ("clusters") around relevant symbols; large bodies elided with explicit
  "lines a–b elided — ask explore for file:a-b" markers. Off-spine near-identical siblings (≥3 implementations
  of one interface) are shown as signatures only.

## 4. Agent playbook (server instructions) — the behaviour they steer
- Call explore FIRST for any question, bug, or before an edit; one call usually answers.
- Treat returned source as already read; do not re-verify with grep; do not hand-reconstruct flows — name the
  endpoints and let the tool find the path.
- Need more → call explore again with more specific names. Keep instructions short (read every session).

## 5. Things they handle that matter for C++/MFC
- Synthesized edges for dynamic dispatch are tagged `provenance: heuristic` with the wiring site.
  Our equivalent: message maps, PostMessage/SendMessage → ON_MESSAGE, RUNTIME_CLASS, DDX.
- They have C/C++ specific resolvers: function pointers, macro renames, `#ifdef` feature variants, includers.
- Freshness: a banner lists files edited after the last index (we do not have a watcher; v0.2 should at
  least detect stale files by size/mtime/hash at query time and say so).

## 6. Caveats of their benchmarks
- Self-reported, small samples (one question per repo, 4 runs), no answer-accuracy metric. So our own
  evaluation (PLAN step S9) must check that the needed code is actually in the output, not just token counts.
