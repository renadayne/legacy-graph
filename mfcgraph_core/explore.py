"""mfc_explore: one call -> the code, flow and impact needed to investigate a question, within a char budget.

Interface:
    explore(graph, query, budget=None, scope=None) -> str
      query   free text: bug description, Name, Class::Method, File.cpp:120, directory, menu caption, ID_xxx,
              or an error message (quoted or not)
      budget  max characters of the result (default: explore_render.default_budget(graph)); never exceeded
      scope   optional directory (or list) to focus on, same effect as naming the directory in the query
Pipeline: explore_query.parse_query -> explore_seed.seed -> explore_rank.rank -> explore_render (allocation).
Section order (PLAN Appendix A): header, Flow, Source, Blast radius, Not shown, Did you mean.
"""
from .explore_query import parse_query
from .explore_seed import seed
from .explore_rank import rank
from . import explore_render as R

HEADER_RESERVE = 160
MAX_SHRINK_ROUNDS = 60
GROW_ROUNDS = 4
GROW_MIN = 300


def _header(nf, nfiles, budget, used, scope):
    return "mfc_explore: %d function%s in %d file%s (budget %d, used %d). Scope: %s\n" % (
        nf, "" if nf == 1 else "s", nfiles, "" if nfiles == 1 else "s", budget, used,
        ", ".join(scope) if scope else "(all)")


def _assemble(budget, scope, flow, plans_text, nfuncs, nfiles, blast, notshown, dym, extra=""):
    body = "\n\n".join(x.rstrip("\n") for x in (extra, flow, plans_text, blast, notshown, dym) if x) + "\n"
    used = 0
    for _ in range(3):  # header contains its own length
        head = _header(nfuncs, nfiles, budget, used, scope)
        total = len(head) + 1 + len(body)
        if total == used:
            break
        used = total
    return head + "\n" + body


def _shrink_once(g, plans, not_shown, sr):
    """Downgrade the lowest-priority function: full -> window -> signature -> dropped. False if nothing left."""
    best = None
    for fp in plans:
        for f in fp.funcs:
            key = (f.node in sr.exact, f.score, f.node)  # lowest priority first; exact functions last
            if best is None or key < best[0]:
                best = (key, fp, f)
    if best is None:
        return False
    _, fp, f = best
    n = g.nodes[f.node]
    lines = R._lines(g, fp.fi)
    if f.mode == R.FULL:
        size = sum(e - s + 1 for s, e in f.windows)
        f.windows = R.windows_for((n.line, n.end), R.focus_lines(g, f.node, sr, set()),
                                  max(8, size // 2))
        f.mode = R.WINDOW
    elif f.mode == R.WINDOW:
        size = sum(e - s + 1 for s, e in f.windows)
        if size > 10:
            f.windows = R.windows_for((n.line, n.end), R.focus_lines(g, f.node, sr, set()),
                                      max(4, size // 2))
        else:
            f.windows = R._sig_window(lines, n)
            f.mode = R.SIG
    else:
        fp.funcs.remove(f)
        not_shown.insert(0, f.node)
        if not fp.funcs and not fp.extra_windows:
            plans.remove(fp)
    return True


def explore(g, query, budget=None, scope=None):
    budget = int(budget or R.default_budget(g))
    scope_dirs = [scope] if isinstance(scope, str) else list(scope or [])
    terms = parse_query(query)
    sr = seed(g, terms, scope_dirs, query)
    scores, spine = rank(g, sr.seeds, sr.scope_dirs, sr.ids)
    dym = R.did_you_mean_section(sr)
    if not scores:
        msg = ("No code matched '%s'. Name a function, class, ID, file or quote the exact message text.\n"
               % query.strip())
        return _fit(_assemble(budget, sr.scope_dirs, "", "", 0, 0, "", "", dym, msg), budget)

    chosen = R.select_functions(g, scores, sr, spine)
    top_score = max([s for _, s in chosen] or [1.0])
    top_func = chosen[0][0] if chosen else None
    flow = R.flow_section(g, spine, sr, top_func)
    blast_nodes = [n for n, _ in chosen if n in sr.exact or n in sr.seeds][:3] or [n for n, _ in chosen[:1]]
    blast = R.blast_section(g, blast_nodes, sr.ids)
    files = {g.nodes[n].file for n, _ in chosen} | set(sr.file_focus)
    changed = R.changed_files(g, files)
    banner = R.changed_banner(g, changed)
    fixed = HEADER_RESERVE + len(flow) + len(blast) + len(dym) + len(banner)
    src_budget = max(R.MIN_FILE_CHARS, budget - fixed - 4 * 70)
    best = None
    for _ in range(GROW_ROUNDS):  # grow the source share while the whole result still has room
        out, plans, not_shown = _build(g, sr, spine, chosen, top_score, src_budget, budget, flow, blast, dym,
                                       changed, banner)
        if len(out) <= budget and (best is None or len(out) > len(best)):
            best = out
        room = budget - len(out)
        if room < GROW_MIN or src_budget >= budget:
            break
        src_budget += room
    if best is None:  # still over budget: degrade the lowest-priority functions one step at a time
        for _ in range(MAX_SHRINK_ROUNDS):
            if len(out) <= budget or not _shrink_once(g, plans, not_shown, sr):
                break
            out = _render_all(g, sr, plans, not_shown, budget, flow, blast, dym, banner)
        best = out
    return _fit(best, budget)


def _render_all(g, sr, plans, not_shown, budget, flow, blast, dym, banner=""):
    nfuncs = sum(len(fp.funcs) for fp in plans)
    return _assemble(budget, sr.scope_dirs, flow, R.render_source(g, plans), nfuncs, len(plans), blast,
                     R.not_shown_section(g, not_shown), dym, banner)


def _build(g, sr, spine, chosen, top_score, src_budget, budget, flow, blast, dym, changed=(), banner=""):
    plans, not_shown = R.allocate(g, chosen, sr, spine, src_budget, top_score, changed)
    shown = {f.node for fp in plans for f in fp.funcs}
    score = dict(chosen)
    not_shown = sorted({n for n, _ in chosen if n not in shown} | set(not_shown),
                       key=lambda n: (-score.get(n, 0.0), n))
    return _render_all(g, sr, plans, not_shown, budget, flow, blast, dym, banner), plans, not_shown


def _fit(text, budget):
    """Last-resort hard cap at a line boundary (only hit with absurdly small budgets)."""
    if len(text) <= budget:
        return text
    cut = text.rfind("\n", 0, max(0, budget - 40))
    return text[:max(0, cut)] + "\n… output truncated to budget\n"
