"""Budget allocation and text sections for mfc_explore (see docs/PLAN.md Appendix A).

Interface:
    default_budget(graph) -> int                    8000 (< 300 files), 12000 (< 3000), else 16000
    select_functions(graph, scores, sr, spine) -> list[(node, score)]   candidates, best first
    allocate(graph, chosen, sr, spine, src_budget, top_score) -> (plans, not_shown)
        plans: list[FilePlan] in output order; not_shown: [node] (scored but without code)
    render_source(graph, plans) -> str               "## Source" section
    flow_section(graph, spine, sr) / blast_section(graph, nodes) / not_shown_section(graph, nodes)
    did_you_mean_section(sr) -> str                  "" when nothing to say

Allocation (why):
  * Files are weighted by the summed score of their chosen functions; a file under MIN_FILE_FRAC (15%) of the top
    file gets no code, only names (a fragment is worse than a pointer). Pinned files and files with an exact
    function always get code.
  * Each code file gets a share of the source budget proportional to weight, at least MIN_FILE_CHARS (600),
    at most MAX_FILE_FRAC (70%) unless pinned; unused share flows to the next file.
  * Inside a file: exact functions first and in full (windows only if one alone exceeds the share), then by score:
    full body if it fits, else windows around focus lines (anchor, matched literal, refs, calls to other chosen
    functions), else signature. Low-score functions off the spine get full code only if it fits the remaining
    share (they are processed last), otherwise the signature only — never a window.
"""
from .explore_windows import windows_for, render, signature_only

MIN_FILE_FRAC = 0.15
MIN_FILE_CHARS = 600
MAX_FILE_FRAC = 0.70
LOW_FRAC = 0.12           # below this fraction of the top score (and not seed/spine): signature only
MIN_REL = 0.04            # candidates below this fraction of the top score are not considered at all
MAX_FUNCS = 16
WINDOW_STEPS = (60, 40, 25, 15, 8)
ELISION_COST = 90
SECTION_MAX_LINES = 10

FULL, WINDOW, SIG = "full", "window", "sig"


def default_budget(g):
    n = len(g.files)
    if n < 300:
        return 8000
    if n < 3000:
        return 12000
    return 16000


def flags_of(n):
    return [f for f in n.flags.split(",") if f in ("msg-handler", "update-ui-handler", "framework-entry", "virtual")]


def loc(g, n):
    if 0 <= n.file < len(g.files):
        return "%s:%d" % (g.files[n.file].path, n.line)
    return ""


def has_code(n):
    return n.kind == "function" and n.file >= 0 and n.end >= n.line and "decl" not in n.flags.split(",")


def select_functions(g, scores, sr, spine):
    on_spine = {n for p in spine for n in p}
    cands = [n for n in scores if has_code(g.nodes[n])]
    if not cands:
        return []
    top = max(scores[n] for n in cands) or 1.0
    must = {n for n in cands if n in sr.exact or n in on_spine}
    must |= {n for n in cands if g.nodes[n].file in sr.pinned_files and n in sr.seeds}
    rest = sorted((n for n in cands if n not in must and scores[n] >= MIN_REL * top), key=lambda n: (-scores[n], n))
    chosen = sorted(must, key=lambda n: (-scores[n], n)) + rest
    return [(n, scores[n]) for n in chosen[:max(MAX_FUNCS, len(must))]]


class FuncPlan:
    def __init__(self, node, score, mode, windows):
        self.node, self.score, self.mode, self.windows = node, score, mode, windows


class FilePlan:
    def __init__(self, fi, weight, pinned):
        self.fi, self.weight, self.pinned = fi, weight, pinned
        self.funcs = []
        self.extra_windows = []   # anchor ranges outside functions

    def windows(self):
        w = list(self.extra_windows)
        for fp in self.funcs:
            w.extend(fp.windows)
        out = []
        for s, e in sorted(w):
            if out and s <= out[-1][1] + 1:
                out[-1] = (out[-1][0], max(out[-1][1], e))
            else:
                out.append((s, e))
        return out


def _lines(g, fi):
    from .query import _read_lines  # shared cache of decoded files
    return _read_lines(g, fi)


def _sig_window(lines, n):
    k = signature_only(lines, (n.line, n.end)).count("\n") + 1
    return [(n.line, n.line + k - 1)]


def focus_lines(g, node, sr, chosen_set):
    f = set(sr.focus.get(node, ()))
    for ei in g.out[node]:
        e = g.edges[ei]
        if e.kind in ("calls", "sends", "runtime_class") and (e.dst in chosen_set or e.kind == "sends"):
            f.add(e.line)
    return f


def _cost(g, lines, fi, windows):
    return len(render(lines, windows, g.files[fi].path)) + ELISION_COST


def plan_function(g, lines, fi, node, score, avail, exact, low, sr, chosen_set):
    """Pick the richest mode that fits avail chars. Returns (FuncPlan or None, cost)."""
    n = g.nodes[node]
    span = (n.line, n.end)
    full = [span]
    full_cost = _cost(g, lines, fi, full)
    if full_cost <= avail:  # low-score functions too: spare budget is better spent on code than left unused
        return FuncPlan(node, score, FULL, full), full_cost
    if not low:
        focus = focus_lines(g, node, sr, chosen_set)
        for ml in WINDOW_STEPS:
            w = windows_for(span, focus, ml)
            c = _cost(g, lines, fi, w)
            if c <= avail:
                return FuncPlan(node, score, WINDOW, w), c
    w = _sig_window(lines, n)
    c = _cost(g, lines, fi, w)
    if c <= avail or exact:
        return FuncPlan(node, score, SIG, w), c
    return None, 0


def allocate(g, chosen, sr, spine, src_budget, top_score):
    on_spine = {n for p in spine for n in p}
    chosen_set = {n for n, _ in chosen}
    by_file = {}
    for n, s in chosen:
        by_file.setdefault(g.nodes[n].file, []).append((n, s))
    weight = {fi: sum(s for _, s in lst) for fi, lst in by_file.items()}
    for fi in sr.file_focus:
        weight.setdefault(fi, 0.0)
        by_file.setdefault(fi, [])
    top_w = max(weight.values() or [1.0]) or 1.0
    for fi in weight:
        if fi in sr.pinned_files:
            weight[fi] = max(weight[fi], top_w)
    order = sorted(weight, key=lambda fi: (-weight[fi], fi))
    keep = [fi for fi in order if weight[fi] >= MIN_FILE_FRAC * top_w or fi in sr.pinned_files
            or any(n in sr.exact for n, _ in by_file[fi])]
    not_shown = [n for fi in order if fi not in keep for n, _ in by_file[fi]]
    while len(keep) > 1 and len(keep) * MIN_FILE_CHARS > src_budget:
        fi = keep.pop()
        not_shown.extend(n for n, _ in by_file[fi])
    total_w = sum(weight[fi] for fi in keep) or 1.0
    plans = []
    carry = 0
    for idx, fi in enumerate(keep):
        pinned = fi in sr.pinned_files
        share = max(MIN_FILE_CHARS, src_budget * weight[fi] / total_w)
        if not pinned:
            share = min(share, MAX_FILE_FRAC * src_budget)
        avail = share + carry
        lines = _lines(g, fi)
        fp = FilePlan(fi, weight[fi], pinned)
        used = len(g.files[fi].path) + 60   # file header line
        for (a, b) in sr.file_focus.get(fi, ()):
            w = (max(1, a - 6), min(len(lines), b + 6))
            fp.extra_windows.append(w)
            used += _cost(g, lines, fi, [w])
        funcs = sorted(by_file[fi], key=lambda x: (0 if x[0] in sr.exact else 1, -x[1], x[0]))
        for n, s in funcs:
            exact = n in sr.exact
            low = (not exact and n not in on_spine and n not in sr.seeds and s < LOW_FRAC * top_score)
            plan, c = plan_function(g, lines, fi, n, s, avail - used, exact, low, sr, chosen_set)
            if plan is None:
                not_shown.append(n)
                continue
            fp.funcs.append(plan)
            used += c
        if fp.funcs or fp.extra_windows:
            plans.append(fp)
        carry = max(0, avail - used)
    return plans, not_shown


def file_header(g, fp):
    full, sig = [], []
    for f in sorted(fp.funcs, key=lambda f: g.nodes[f.node].line):
        n = g.nodes[f.node]
        name = n.qname
        fl = flags_of(n)
        if fl:
            name += " (" + ", ".join(fl) + ")"
        (sig if f.mode == SIG else full).append(name)
    s = "### %s — %s" % (g.files[fp.fi].path, ", ".join(full) if full else "")
    if sig:
        s += ("; " if full else "") + ", ".join(sig) + " (signature only)"
    return s


def render_file(g, fp):
    lines = _lines(g, fp.fi)
    return file_header(g, fp) + "\n" + render(lines, fp.windows(), g.files[fp.fi].path)


def render_source(g, plans):
    if not plans:
        return ""
    return "## Source\n" + "\n".join(render_file(g, fp) for fp in plans) + "\n"


# ---- other sections ----
def _cap(lines):
    if len(lines) > SECTION_MAX_LINES:
        lines = lines[:SECTION_MAX_LINES - 1] + ["  … %d more" % (len(lines) - SECTION_MAX_LINES + 1)]
    return lines


def node_text(g, n):
    node = g.nodes[n]
    if node.kind == "function":
        return node.qname + "  " + loc(g, node)
    if node.kind == "ui":
        return node.name
    return node.name


def ui_entries(g, fn):
    """['Menu ...', 'Accelerator ...'] reaching function fn through handled_by + triggers/contains."""
    out = []
    for ei in g.inn[fn]:
        e = g.edges[ei]
        if e.kind != "handled_by":
            continue
        for ej in g.inn[e.src]:
            t = g.edges[ej]
            if t.kind == "triggers":
                out.append(g.nodes[t.src].name)
            elif t.kind == "contains":
                out.append("%s control %s" % (g.nodes[t.src].name, t.extra))
    return sorted(set(out), key=out.index)


def _handled_macro(g, idn, fn):
    for ei in g.out[idn]:
        e = g.edges[ei]
        if e.dst == fn and e.kind == "handled_by":
            return e.extra.split("@")[0]
    return ""


def path_lines(g, path):
    out = []
    i = 0
    first = True
    while i < len(path):
        n = path[i]
        node = g.nodes[n]
        if node.kind == "id" and i + 1 < len(path) and g.nodes[path[i + 1]].kind == "function":
            nx = path[i + 1]
            macro = _handled_macro(g, n, nx)
            text = "%s%s -> %s" % (node.name, " [%s]" % macro if macro else "", node_text(g, nx))
            i += 2
        else:
            text = node_text(g, n)
            i += 1
        out.append(text if first else "  -> " + text)
        first = False
    return out


def flow_section(g, spine, sr, top_func=None):
    lines = []
    for p in spine[:3]:
        head = g.nodes[p[0]]
        if head.kind == "function":
            ui = ui_entries(g, p[0])
            if ui:
                pl = path_lines(g, p)
                lines.append(" / ".join(ui[:3]))
                lines.append("  -> " + pl[0])
                lines.extend(pl[1:])
                continue
        lines.extend(path_lines(g, p))
    if not spine and top_func is not None:
        ui = ui_entries(g, top_func)
        if ui:
            lines.append(" / ".join(ui[:3]))
            lines.append("  -> " + node_text(g, top_func))
    seen = set()
    for (fn, line, text) in sr.texts:
        if (fn, line) in seen or len(seen) >= 3:
            continue
        seen.add((fn, line))
        f = g.nodes[fn]
        path = g.files[f.file].path if 0 <= f.file < len(g.files) else "?"
        lines.append('Text "%s": %s:%d (in %s)' % (text[:80], path, line, f.qname))
    if not lines:
        return ""
    return "## Flow\n" + "\n".join(_cap(lines)) + "\n"


def blast_section(g, nodes):
    lines = []
    for n in nodes[:3]:
        callers = sorted({g.edges[ei].src for ei in g.inn[n] if g.edges[ei].kind == "calls"
                          and g.nodes[g.edges[ei].src].kind == "function"})
        via = ["%s [%s]" % (g.nodes[g.edges[ei].src].name, g.edges[ei].extra.split("@")[0])
               for ei in g.inn[n] if g.edges[ei].kind == "handled_by"]
        s = "%s ← %d caller%s" % (g.nodes[n].qname, len(callers), "" if len(callers) == 1 else "s")
        if via:
            s += ", called by MFC via " + ", ".join(via[:3])
        if callers:
            s += " (" + ", ".join(g.nodes[c].qname for c in callers[:4]) + (", …" if len(callers) > 4 else "") + ")"
        ui = ui_entries(g, n)
        for c in callers[:6]:
            ui.extend(x for x in ui_entries(g, c) if x not in ui)
        if ui:
            s += "; UI entries: " + ", ".join(ui[:4]) + (", …" if len(ui) > 4 else "")
        lines.append(s)
    if not lines:
        return ""
    return "## Blast radius\n" + "\n".join(_cap(lines)) + "\n"


def not_shown_section(g, nodes, limit=12, width=110):
    if not nodes:
        return ""
    items = ["%s  %s" % (g.nodes[n].qname, loc(g, g.nodes[n])) for n in nodes[:limit]]
    if len(nodes) > limit:
        items.append("… %d more" % (len(nodes) - limit))
    lines, cur = [], ""
    for it in items:
        if cur and len(cur) + 3 + len(it) > width:
            lines.append(cur)
            cur = it
        else:
            cur = it if not cur else cur + " · " + it
    if cur:
        lines.append(cur)
    return "## Not shown (ask mfc_explore with these names)\n" + "\n".join(_cap(lines)) + "\n"


def did_you_mean_section(sr):
    lines = []
    for t in sr.unmatched:
        sug = sr.suggestions.get(t.value)
        if sug:
            lines.append("%s → %s" % (t.value, ", ".join(sug)))
        else:
            lines.append("%s: no match (%s)" % (t.value, t.kind))
    if not lines:
        return ""
    return "## Did you mean\n" + "\n".join(_cap(lines)) + "\n"
