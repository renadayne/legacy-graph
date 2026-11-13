"""Win32 (non-MFC) dispatch: switch/case window procedures, HANDLE_MSG crackers.

Interface:
    scan_switches(walker, f, b, e)   extractor side, called from CppWalker.scan_body for a function body [b, e):
        f.cases    += [(label, line, end_line, parent_label)]  every `case LABEL:` (single identifier) with the line
                      range of its section and the label of the enclosing case of an outer switch ("" if none)
        f.crackers += [(msg, handler, line)]                  HANDLE_MSG(hwnd, WM_X, Fn)
    make_dispatch(resolver)          resolver side, after make_calls():
        * label that is a known resource/message id (or WM_*) -> edge id --handled_by--> function, extra "case@<line>"
          (conf exact when the function looks like a window/dialog procedure or the case sits under WM_COMMAND /
          WM_NOTIFY / WM_SYSCOMMAND, else heuristic)
        * calls made inside that case section -> edge id --case_calls--> callee (heuristic), so the flow
          menu -> IDM_X -> WndProc -> DoX is visible and ranking reaches DoX
        * HANDLE_MSG -> WM_X --handled_by--> Fn (exact) and proc --calls--> Fn; Fn flagged msg-handler
        * functions whose signature has WPARAM and LPARAM get the flag "win32-proc" (called by Windows)
Why heuristics here: a window procedure is ordinary C code; the switch on msg / LOWORD(wParam) IS its message map.
"""
from .lexer import IDENT, PUNCT

COMMAND_PARENTS = frozenset(["WM_COMMAND", "WM_NOTIFY", "WM_SYSCOMMAND", "WM_MENUCOMMAND"])


# ---------------------------------------------------------------- extractor side
def _switch_ranges(w, b, e):
    """[(open_brace, close_brace)] of switch bodies inside [b, e)."""
    t, pm, bm = w.t, w.pm, w.bm
    out = []
    for x in range(b, e):
        if t[x][0] == IDENT and t[x][1] == "switch" and w.is_p(x + 1, "("):
            close = pm[x + 1]
            if close > 0 and close + 1 < e and w.is_p(close + 1, "{") and bm[close + 1] > close + 1:
                out.append((close + 1, bm[close + 1]))
    return out


def _innermost(ranges, x):
    best = None
    for r in ranges:
        if r[0] < x < r[1] and (best is None or r[0] > best[0]):
            best = r
    return best


def scan_switches(w, f, b, e):
    t = w.t
    ranges = _switch_ranges(w, b, e)
    if ranges:
        labels = {r: [] for r in ranges}   # switch -> [(token index, label or None for default)]
        for x in range(b, e):
            k, s, _ = t[x]
            if k != IDENT or s not in ("case", "default"):
                continue
            sw = _innermost(ranges, x)
            if sw is None:
                continue
            if s == "default":
                labels[sw].append((x, None))
                continue
            j = x + 1
            while j < e and not (t[j][0] == PUNCT and t[j][1] == ":"):
                j += 1
            if j == x + 2 and t[x + 1][0] == IDENT:
                labels[sw].append((x, t[x + 1][1]))
            else:
                labels[sw].append((x, ""))  # numeric / expression label: keeps section boundaries right
        sections = {}  # switch -> [(label, start_tok, end_tok)]
        for sw, lst in labels.items():
            secs = []
            for i, (x, lab) in enumerate(lst):
                end = lst[i + 1][0] if i + 1 < len(lst) else sw[1]
                secs.append((lab, x, end))
            sections[sw] = secs
        for sw in sorted(ranges):
            parent = ""
            outer = _innermost([r for r in ranges if r != sw], sw[0])
            if outer is not None:
                for lab, s0, s1 in sections[outer]:
                    if s0 < sw[0] < s1:
                        parent = lab or ""
            for lab, s0, s1 in sections[sw]:
                if lab:
                    end_line = t[s1][2] if t[s1][2] > t[s0][2] else t[s0][2]
                    if s1 < len(t) and s1 != sw[1] and t[s1][2] > t[s0][2]:
                        end_line = t[s1][2] - 1
                    f.cases.append((lab, t[s0][2], end_line, parent))
    for x in range(b, e):
        if t[x][0] == IDENT and t[x][1] == "HANDLE_MSG" and w.is_p(x + 1, "("):
            args = w.split_args(x + 1)
            if len(args) >= 3:
                f.crackers.append((w.arg_text(args[1]), w.arg_text(args[2]), t[x][2]))


# ---------------------------------------------------------------- resolver side
def _is_proc_sig(sig):
    return "WPARAM" in sig and "LPARAM" in sig


def _add_flag(n, flag):
    fl = [x for x in n.flags.split(",") if x]
    if flag not in fl:
        fl.append(flag)
        n.flags = ",".join(fl)


def _label_ok(r, label):
    if label.startswith(("WM_", "UWM_")):
        return True
    return label in r.ids


def _find_handler(r, src, name, file):
    """Function node for a cracker handler: same file first (static), else unique free function / method."""
    nodes = r.g.nodes
    cands = r.free_by_name.get(name, []) + r.method_by_name.get(name, [])
    defs = [c for c in cands if "decl" not in nodes[c].flags.split(",")]
    same = [c for c in defs if nodes[c].file == file]
    if same:
        return same[0]
    if len(defs) == 1:
        return defs[0]
    return None


def make_dispatch(r):
    g = r.g
    nodes = g.nodes
    out_calls = {}
    for e in g.edges:
        if e.kind == "calls" and nodes[e.dst].kind == "function":
            out_calls.setdefault(e.src, []).append(e)
    for fi, f in enumerate(r.r.funcs):
        if not f.is_def:
            continue
        src = r.func_node.get(fi)
        if src is None:
            continue
        proc = _is_proc_sig(f.sig)
        if proc:
            _add_flag(nodes[src], "win32-proc")
        for (label, line, end_line, parent) in f.cases:
            if not _label_ok(r, label):
                continue
            idn = r.id_node(label)
            conf = "exact" if (proc or parent in COMMAND_PARENTS) else "heuristic"
            r.add_edge(idn, src, "handled_by", f.file, line, conf, "case@%d%s" % (line, " in " + parent if parent else ""))
            r.dispatch_cases += 1
            for e in out_calls.get(src, ()):
                if line <= e.line <= end_line:
                    r.add_edge(idn, e.dst, "case_calls", f.file, e.line, "heuristic", "%s case@%d" % (nodes[src].name, line))
        for (msg, handler, line) in f.crackers:
            h = _find_handler(r, src, handler, f.file)
            if h is None or not _label_ok(r, msg):
                continue
            r.add_edge(r.id_node(msg), h, "handled_by", f.file, line, "exact", "HANDLE_MSG@" + nodes[src].name)
            r.add_edge(src, h, "calls", f.file, line, "exact")
            _add_flag(nodes[h], "msg-handler")
            r.dispatch_cases += 1
