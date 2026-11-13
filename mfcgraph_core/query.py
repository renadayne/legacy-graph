"""Read-only queries over the graph. Each returns compact text designed to be
cheap for an AI agent to read (few tokens, precise locations)."""
import os
import unicodedata

from .encoding import decode_with_label

K_FORWARD = frozenset(["calls", "runtime_class", "sends", "handled_by"])
K_REVERSE = frozenset(["calls", "handled_by", "triggers", "sends"])


def _loc(g, n):
    if n.file < 0 or n.file >= len(g.files):
        return ""
    return "%s:%d" % (g.files[n.file].path, n.line)


def _label(g, n):
    if n.kind == "external":
        return n.qname + " [external]"
    if n.kind in ("function", "class"):
        lc = _loc(g, n)
        return n.qname + ("  " + lc if lc else "")
    if n.kind == "dialog":
        return "Dialog " + n.name + ("" if not n.extra else " " + n.extra)
    return n.name


def _has_flag(n, f):
    return f in n.flags.split(",")


def _last_eq(a, b):
    p = a.rfind("::")
    return (a if p < 0 else a[p + 2:]) == b


def _find_symbols(g, q, include_classes=True):
    q = q.strip()
    ok = (lambda n: n.kind == "function" or (include_classes and n.kind == "class"))
    r = [n.id for n in g.nodes if ok(n) and n.qname == q]
    if r:
        return r
    if "::" in q:
        r = [n.id for n in g.nodes if ok(n) and n.qname.endswith("::" + q)]
        if r:
            return r
    r = [n.id for n in g.nodes if ok(n) and n.name == q]
    if r:
        return r
    ql = q.lower()
    return [n.id for n in g.nodes if ok(n) and (n.name.lower() == ql or n.qname.lower() == ql)]


def _ambiguity(g, q, m):
    if not m:
        return "No symbol matches '%s'. Try: search %s\n" % (q, q)
    lines = ["%d symbols match '%s'. Use a qualified name:" % (len(m), q)]
    for x in m[:20]:
        lines.append("  " + _label(g, g.nodes[x]))
    return "\n".join(lines) + "\n"


def _one_symbol(g, q, include_classes=True):
    """Returns (node_id, None) or (None, message)."""
    m = _find_symbols(g, q, include_classes)
    if len(m) == 1:
        return m[0], None
    defs = [x for x in m if not _has_flag(g.nodes[x], "decl")]
    if len(defs) == 1:
        return defs[0], None
    return None, _ambiguity(g, q, m)


_line_cache = {}


def _read_lines(g, file):
    if file < 0 or file >= len(g.files):
        return []
    key = (g.root, file)
    if key in _line_cache:
        return _line_cache[key]
    p = os.path.join(g.root, *g.files[file].path.split("/"))
    try:
        with open(p, "rb") as fh:
            data = fh.read()
    except OSError:
        return []
    text = decode_with_label(data, g.files[file].encoding, g.codepage)
    lines = [ln[:-1] if ln.endswith("\r") else ln for ln in text.split("\n")]
    if len(_line_cache) > 64:
        _line_cache.clear()
    _line_cache[key] = lines
    return lines


def _snippet(g, n, max_lines):
    lines = _read_lines(g, n.file)
    if not lines:
        return "  (source not readable from %s)\n" % g.root
    b = max(1, n.line)
    e = min(max(n.end, n.line), len(lines))
    out = []
    shown = 0
    for i in range(b, e + 1):
        if shown >= max_lines:
            out.append("  ... (%d more lines, %s:%d-%d)" % (e - i + 1, g.files[n.file].path, i, e))
            break
        out.append("%d | %s" % (i, lines[i - 1]))
        shown += 1
    return "\n".join(out) + "\n"


def _tree(g, node, depth, max_depth, reverse, indent, visited, out, budget):
    """budget is a 1-element list (mutable counter)."""
    if depth >= max_depth or budget[0] <= 0:
        return
    lst = g.inn[node] if reverse else g.out[node]
    kinds = K_REVERSE if reverse else K_FORWARD
    externals = []
    shown = set()
    arrow = "<- " if reverse else "-> "
    for ei in lst:
        e = g.edges[ei]
        if e.kind not in kinds:
            continue
        if not reverse and e.kind == "handled_by" and g.nodes[node].kind != "id":
            continue
        other = e.src if reverse else e.dst
        if other in shown:
            continue
        shown.add(other)
        on = g.nodes[other]
        if on.kind == "external":
            externals.append(on.qname + (" (RUNTIME_CLASS)" if e.kind == "runtime_class" else ""))
            continue
        budget[0] -= 1
        if budget[0] < 0:
            out.append(indent + "... (truncated)")
            return
        if e.kind == "handled_by":
            tag = " [" + e.extra.split("@")[0] + "]"
        elif e.kind == "sends":
            tag = " [" + e.extra + " heuristic]"
        elif e.kind == "triggers":
            tag = ""
        elif e.kind == "runtime_class":
            tag = " [RUNTIME_CLASS]"
        elif e.conf != "exact":
            tag = " [" + e.conf + "]"
        else:
            tag = ""
        call_loc = ""
        if e.kind == "calls" and e.file >= 0:
            call_loc = "  (call at %s:%d)" % (g.files[e.file].path, e.line)
        if other in visited:
            out.append(indent + arrow + _label(g, on) + tag + "  (see above)")
            continue
        out.append(indent + arrow + _label(g, on) + tag + (call_loc if reverse else ""))
        visited.add(other)
        _tree(g, other, depth + 1, max_depth, reverse, indent + "   ", visited, out, budget)
    if externals:
        ex = sorted(set(externals))
        line = indent + arrow + "external: " + ", ".join(ex[:15])
        if len(ex) > 15:
            line += ", +%d more" % (len(ex) - 15)
        out.append(line)


def _ui_entries(g, fn):
    r = []
    for ei in g.inn[fn]:
        e = g.edges[ei]
        if e.kind != "handled_by":
            continue
        idn = g.nodes[e.src]
        macro = e.extra.split("@")[0]
        ui = []
        for ej in g.inn[idn.id]:
            t = g.edges[ej]
            if t.kind == "triggers":
                ui.append(g.nodes[t.src].name)
            elif t.kind == "contains":
                ui.append(g.nodes[t.src].name + " control " + t.extra)
        s = idn.name + " via " + macro
        if ui:
            s += "  <- " + " | ".join(ui)
        r.append(s)
    return r


def _stat(g, k):
    return g.stats.get(k, "0")


def _pct(a, b):
    try:
        x, y = float(a), float(b)
    except ValueError:
        return "-"
    if y <= 0:
        return "-"
    return "%.1f%%" % (100.0 * x / y)


# ---------------------------------------------------------------- queries

def norm_text(s):
    """Case-insensitive, NFC-normalised form used to match string literals (Vietnamese safe)."""
    return unicodedata.normalize("NFC", s).casefold()


def text_hits(g, query):
    """String literals containing query: list of (score, func_node, line, text); exact match scores higher."""
    q = norm_text(query.strip().strip('"\''))
    out = []
    if not q:
        return out
    for (fn, line, text) in g.texts:
        t = norm_text(text)
        if q in t:
            out.append((50 if t == q else 35, fn, line, text))
    return out


def q_search(g, query, limit=40):
    hits = []
    ql = query.lower()
    for n in g.nodes:
        if n.kind == "file":
            continue
        if n.name == query or n.qname == query:
            score = 100
        elif n.name.lower() == ql:
            score = 90
        elif ql in n.qname.lower():
            score = 60
        elif ql in n.extra.lower():
            score = 40
        else:
            continue
        if n.kind in ("function", "class"):
            score += 5
        if n.kind == "external":
            score -= 30
        hits.append((score, n.id))
    texts = text_hits(g, query)
    for i, th in enumerate(texts):
        hits.append((th[0], -1 - i))
    if not hits:
        return "No match for '%s'.\n" % query
    hits.sort(key=lambda h: -h[0])  # stable
    out = ["%d match(es) for '%s'%s:" % (len(hits), query, " (showing top)" if len(hits) > limit else "")]
    for _, nid in hits[:limit]:
        if nid < 0:
            _, fn, line, text = texts[-1 - nid]
            f = g.nodes[fn]
            path = g.files[f.file].path if 0 <= f.file < len(g.files) else "?"
            out.append('  [text] "%s"  %s  %s:%d' % (text, f.qname, path, line))
            continue
        n = g.nodes[nid]
        s = "  [%s] %s" % (n.kind, _label(g, n))
        if n.kind == "id" and n.extra:
            s += "  " + n.extra
        if n.kind == "id" and n.file >= 0:
            s += "  " + _loc(g, n)
        out.append(s)
    return "\n".join(out) + "\n"


def match_ref_targets(g, query):
    """Ref targets matching query: exact 'Class::field', '...::field' suffix, or bare field name."""
    q = query.strip()
    targets = sorted({r[2] for r in g.refs})
    for test in (lambda t: t == q, lambda t: t.endswith("::" + q), lambda t: t.lower().endswith(q.lower())
                 and (len(t) == len(q) or t[-len(q) - 1] == ":")):
        hit = [t for t in targets if test(t)]
        if hit:
            return hit
    return []


def q_refs(g, query, limit=40):
    targets = match_ref_targets(g, query)
    if not targets:
        return "No variable references match '%s'. Try: search %s\n" % (query, query)
    out = []
    for t in targets:
        rows = {"w": [], "r": []}
        for (fn, line, target, mode) in g.refs:
            if target != t:
                continue
            f = g.nodes[fn]
            path = g.files[f.file].path if 0 <= f.file < len(g.files) else "?"
            tag = " [DDX]" if mode == "w" and f.name == "DoDataExchange" else ""
            rows[mode].append((path, line, "  %s  %s:%d%s" % (f.qname, path, line, tag)))
        out.append("%s: %d write(s), %d read(s)" % (t, len(rows["w"]), len(rows["r"])))
        for mode, title in (("w", "writes"), ("r", "reads")):
            if not rows[mode]:
                continue
            out.append(title + ":")
            lst = sorted(rows[mode])
            out.extend(x[2] for x in lst[:limit])
            if len(lst) > limit:
                out.append("  ... %d more" % (len(lst) - limit))
    return "\n".join(out) + "\n"


def q_node(g, symbol, with_code=True, max_code_lines=80):
    nid, msg = _one_symbol(g, symbol)
    if nid is None:
        return msg
    n = g.nodes[nid]
    head = "[%s] %s  %s" % (n.kind, n.qname, _loc(g, n))
    if n.end > n.line:
        head += "-%d" % n.end
    out = [head]
    if n.sig:
        out.append("  sig: " + n.sig)
    if n.flags:
        out.append("  flags: " + n.flags)
    if n.extra:
        out.append("  " + n.extra)
    if n.kind == "class":
        methods = [m.name + ("(decl)" if _has_flag(m, "decl") else "")
                   for m in g.nodes if m.kind == "function" and m.owner == nid]
        derived = [g.nodes[g.edges[ei].src].qname for ei in g.inn[nid] if g.edges[ei].kind == "inherits"]
        out.append("  methods (%d): %s" % (len(methods), ", ".join(methods)))
        if derived:
            out.append("  derived: " + ", ".join(derived))
        for ei in g.out[nid]:
            if g.edges[ei].kind == "uses_dialog":
                out.append("  dialog: " + _label(g, g.nodes[g.edges[ei].dst]))
    if n.kind == "function":
        for s in _ui_entries(g, nid):
            out.append("  triggered by: " + s)
        callers = sum(1 for ei in g.inn[nid] if g.edges[ei].kind == "calls")
        callees = ext = 0
        for ei in g.out[nid]:
            e = g.edges[ei]
            if e.kind == "calls":
                if g.nodes[e.dst].kind == "external":
                    ext += 1
                else:
                    callees += 1
        for ei in g.out[nid]:
            if g.edges[ei].kind == "overrides":
                out.append("  overrides: " + g.nodes[g.edges[ei].dst].qname)
        out.append("  callers: %d, callees: %d in code + %d external" % (callers, callees, ext))
    text = "\n".join(out) + "\n"
    if with_code and n.kind in ("function", "class"):
        text += "---\n" + _snippet(g, n, max_code_lines)
    return text


def q_callers(g, symbol, depth=5):
    nid, msg = _one_symbol(g, symbol, False)
    if nid is None:
        return msg
    out = [_label(g, g.nodes[nid])]
    _tree(g, nid, 0, depth, True, "  ", {nid}, out, [150])
    if not g.inn[nid]:
        out.append("  (no callers found" + (
            "; called by the MFC framework)" if _has_flag(g.nodes[nid], "framework-entry") else ")"))
    return "\n".join(out) + "\n"


def q_callees(g, symbol, depth=2):
    nid, msg = _one_symbol(g, symbol, False)
    if nid is None:
        return msg
    out = [_label(g, g.nodes[nid])]
    _tree(g, nid, 0, depth, False, "  ", {nid}, out, [150])
    return "\n".join(out) + "\n"


def q_impact(g, symbol, depth=5):
    nid, msg = _one_symbol(g, symbol, False)
    if nid is None:
        return msg
    dist = {nid: 0}
    queue = [nid]
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        if dist[cur] >= depth:
            continue
        for ei in g.inn[cur]:
            e = g.edges[ei]
            if e.kind not in K_REVERSE and e.kind != "contains":
                continue
            if e.src in dist:
                continue
            dist[e.src] = dist[cur] + 1
            queue.append(e.src)
    fns, ui, files = [], [], set()
    for x in sorted(dist):
        if x == nid:
            continue
        n = g.nodes[x]
        if n.kind == "function":
            fns.append((dist[x], x))
            if n.file >= 0:
                files.add(g.files[n.file].path)
        elif n.kind == "ui":
            ui.append(n.name)
        elif n.kind == "dialog":
            ui.append(_label(g, n))
    fns.sort()
    out = ["Impact of changing %s  (reverse depth <= %d)" % (_label(g, g.nodes[nid]), depth),
           "functions affected (%d):" % len(fns)]
    for d, x in fns[:60]:
        out.append("  %d  %s" % (d, _label(g, g.nodes[x])))
    if len(fns) > 60:
        out.append("  ... +%d more" % (len(fns) - 60))
    out.append("UI entry points (%d):" % len(ui))
    for s in ui:
        out.append("  " + s)
    for ei in g.out[nid]:
        if g.edges[ei].kind == "overrides":
            out.append("note: overrides %s (also reached by virtual dispatch)" % g.nodes[g.edges[ei].dst].qname)
    if _has_flag(g.nodes[nid], "framework-entry"):
        out.append("note: called by the MFC framework")
    out.append("files (%d): %s" % (len(files), ", ".join(sorted(files))))
    return "\n".join(out) + "\n"


def q_trace(g, query, depth=2):
    ql = query.lower()
    ids, seen, dialogs = [], set(), []
    for n in g.nodes:
        if n.kind == "ui" and ql in n.name.lower():
            for ei in g.out[n.id]:
                e = g.edges[ei]
                if e.kind == "triggers" and e.dst not in seen:
                    seen.add(e.dst)
                    ids.append(e.dst)
    for n in g.nodes:
        if n.kind == "id" and n.name.lower() == ql and n.id not in seen:
            seen.add(n.id)
            ids.append(n.id)
        if n.kind == "dialog" and (n.name.lower() == ql or ql in n.extra.lower()):
            dialogs.append(n.id)
    if not ids and not dialogs:
        return "Nothing matches '%s' (menu caption, accelerator, command ID or dialog ID).\n" % query
    out = []
    for idn in ids:
        n = g.nodes[idn]
        is_dialog_id = any(g.nodes[d].name == n.name for d in dialogs)
        has_links = any(g.edges[ei].kind == "handled_by" for ei in g.out[idn])
        if is_dialog_id and not has_links:
            continue
        out.append("== " + n.name + ("  (%s)" % n.extra if n.extra else ""))
        for ei in g.inn[idn]:
            e = g.edges[ei]
            if e.kind == "triggers":
                out.append("  UI: %s  %s" % (g.nodes[e.src].name, _loc(g, g.nodes[e.src])))
            elif e.kind == "contains":
                out.append("  UI: %s control %s" % (g.nodes[e.src].name, e.extra))
            elif e.kind == "sends":
                out.append("  sent by: %s [%s heuristic]" % (_label(g, g.nodes[e.src]), e.extra))
        anyh = False
        for ei in g.out[idn]:
            e = g.edges[ei]
            if e.kind != "handled_by":
                continue
            anyh = True
            macro = e.extra.split("@")[0]
            out.append("  handler [%s]: %s" % (macro, _label(g, g.nodes[e.dst])))
            if g.nodes[e.dst].kind == "function" and "UPDATE_COMMAND_UI" not in macro:
                _tree(g, e.dst, 0, depth, False, "     ", {e.dst}, out, [60])
        if not anyh:
            out.append("  (no message-map handler found in indexed code; may be handled by MFC itself)")
    for dn in dialogs:
        d = g.nodes[dn]
        out.append("== %s  %s" % (_label(g, d), _loc(g, d)))
        cls = -1
        for ei in g.inn[dn]:
            if g.edges[ei].kind == "uses_dialog":
                cls = g.edges[ei].src
        if cls >= 0:
            out.append("  class: " + _label(g, g.nodes[cls]))
        ddx = {}
        if cls >= 0:
            for ei in g.out[cls]:
                e = g.edges[ei]
                if e.kind == "binds":
                    ddx[e.dst] = (ddx[e.dst] + ", " if e.dst in ddx else "") + e.extra
        out.append("  controls:")
        for ei in g.out[dn]:
            e = g.edges[ei]
            if e.kind != "contains":
                continue
            c = g.nodes[e.dst]
            s = "    %s  %s" % (c.name, e.extra)
            if c.id in ddx:
                s += "  <-> " + ddx[c.id]
            for ej in g.out[c.id]:
                h = g.edges[ej]
                if h.kind != "handled_by":
                    continue
                hn = g.nodes[h.dst]
                if cls >= 0 and hn.owner >= 0 and hn.owner != cls:
                    continue
                s += "  -> %s [%s]" % (hn.name, h.extra.split("@")[0])
            out.append(s)
        if cls >= 0:
            fw = [m.name for m in g.nodes if m.kind == "function" and m.owner == cls
                  and _has_flag(m, "framework-entry")]
            if fw:
                out.append("  framework entry points: " + ", ".join(fw))
    return "\n".join(out) + "\n"


def q_msgmap(g, cls):
    classes = [x for x in _find_symbols(g, cls, True) if g.nodes[x].kind == "class"]
    if len(classes) != 1:
        return ("No class '%s'.\n" % cls) if not classes else _ambiguity(g, cls, classes)
    c = g.nodes[classes[0]]
    out = ["Message map of " + c.qname]
    count = 0
    for e in g.edges:
        if e.kind != "handled_by":
            continue
        parts = e.extra.split("@")
        if len(parts) < 2 or not _last_eq(parts[1], c.name):
            continue
        h = g.nodes[e.dst]
        if h.kind != "external":
            where = "  " + _loc(g, h)
        elif h.extra == "framework-handler":
            where = "  [implemented by MFC base class]"
        else:
            where = "  [handler not found]"
        out.append("  %s(%s) -> %s%s" % (parts[0], g.nodes[e.src].name, h.qname, where))
        count += 1
    if not count:
        out.append("  (no message map entries)")
    return "\n".join(out) + "\n"


def q_context(g, symbol, max_code_lines=80):
    nid, msg = _one_symbol(g, symbol)
    if nid is None:
        return msg
    n = g.nodes[nid]
    out = ["# Context: " + n.qname, "",
           "## Definition (%s%s)" % (_loc(g, n), "-%d" % n.end if n.end > n.line else "")]
    if n.flags:
        out.append("flags: " + n.flags)
    out.append("```cpp\n" + _snippet(g, n, max_code_lines) + "```")
    if n.kind == "function":
        ui = _ui_entries(g, nid)
        if ui:
            out += ["", "## Triggered by"] + ["- " + s for s in ui]
        out += ["", "## Called by"]
        c = 0
        for ei in g.inn[nid]:
            e = g.edges[ei]
            if e.kind != "calls":
                continue
            out.append("- " + _label(g, g.nodes[e.src]) + ("" if e.conf == "exact" else " [%s]" % e.conf))
            c += 1
        if not c:
            out.append("- (none in indexed code%s)" % (
                "; MFC framework calls it" if _has_flag(n, "framework-entry") else ""))
        out += ["", "## Calls"]
        ext = []
        for ei in g.out[nid]:
            e = g.edges[ei]
            if e.kind not in ("calls", "sends", "runtime_class"):
                continue
            t = g.nodes[e.dst]
            if t.kind == "external":
                ext.append(t.qname)
                continue
            s = "- " + _label(g, t)
            if t.sig:
                s += "  `" + t.sig + "`"
            if e.kind == "sends":
                s += " [%s -> message handler, heuristic]" % e.extra
            elif e.conf != "exact":
                s += " [%s]" % e.conf
            out.append(s)
        if ext:
            out.append("- external: " + ", ".join(sorted(set(ext))))
        for ei in g.out[nid]:
            if g.edges[ei].kind == "overrides":
                out += ["", "Overrides " + g.nodes[g.edges[ei].dst].qname]
    return "\n".join(out) + "\n"


def q_diagnose(g, show_names=False):
    s = lambda k: _stat(g, k)  # noqa: E731
    total = s("calls.total")
    enc = "".join("  %s=%s" % (k[9:], v) for k, v in sorted(g.stats.items()) if k.startswith("encoding."))
    lines = [
        "mfcgraph diagnose (counts only; no names, no code)",
        "files: %s  (source %s of which C %s, header %s, resource %s)" % (
            s("files.total"), s("files.source"), s("files.c"), s("files.header"), s("files.resource")),
        "encodings:" + enc,
        "files with unbalanced braces: " + s("files.brace_error"),
        "files skipped because of an internal error: " + s("files.failed"),
        "tokens skipped in inactive #if branches: " + s("tokens.inactive_skipped"),
        "#if conditions: evaluated %s, guessed (first branch kept) %s%s" % (
            s("pp.evaluated"), s("pp.guessed"),
            "" if (g.pp_defines or g.pp_undefs or g.pp_undef_unknown) else "  (use index --define/--undef to decide them)"),
        "classes: " + s("classes"),
        "functions: defined %s, declared-only %s, framework entry points %s, message handlers %s" % (
            s("functions.defined"), s("functions.decl_only"), s("functions.framework_entry"),
            s("functions.msg_handler")),
        "call sites: %s  exact %s, likely %s, ambiguous %s, external %s" % (
            total, _pct(s("calls.exact"), total), _pct(s("calls.likely"), total),
            _pct(s("calls.ambiguous"), total), _pct(s("calls.external"), total)),
        "message-map entries: %s  handler found in code %s, handled by an MFC base class %s, NOT FOUND %s" % (
            s("msgmap.entries"), _pct(s("msgmap.resolved"), s("msgmap.entries")),
            _pct(s("msgmap.framework"), s("msgmap.entries")), _pct(s("msgmap.unresolved"), s("msgmap.entries"))),
        "win32: window/dialog procedures %s, switch-case / HANDLE_MSG dispatch entries linked %s, "
        "dialog/callback wiring links %s" % (s("win32.procs"), s("win32.dispatch"), s("win32.wiring")),
        "unrecognised ON_ macros: %s uses of %s kinds%s" % (
            s("msgmap.unknown_macros"), s("msgmap.unknown_macro_kinds"),
            ("  [%s]" % g.stats.get("msgmap.unknown_macro_names", "")) if show_names
            else "  (add --show-names to list them)"),
        "resources: dialogs %s, menu items %s, accelerators %s, toolbar buttons %s, strings %s" % (
            s("rc.dialogs"), s("rc.menu_items"), s("rc.accelerators"), s("rc.toolbar_buttons"), s("rc.strings")),
        "#include resolved inside the tree: %s of %s (system/MFC headers are expected to be unresolved)" % (
            _pct(s("includes.resolved"), s("includes.total")), s("includes.total")),
        "string literals indexed: %d" % len(g.texts),
        "variable references: %s  resolved to a field/global/id %s; stored: writes %d, reads %d" % (
            s("refs.total"), _pct(s("refs.resolved"), s("refs.total")),
            sum(1 for r in g.refs if r[3] == "w"), sum(1 for r in g.refs if r[3] != "w")),
        "graph: %s nodes, %s edges" % (s("nodes"), s("edges")),
    ]
    return "\n".join(lines) + "\n"


def q_status(g, index_path):
    s = lambda k: _stat(g, k)  # noqa: E731
    return ("index: %s\nroot: %s\ncreated: %s\ncodepage: %d\nfiles: %s, classes: %s, functions: %s, "
            "message-map entries: %s, dialogs: %s, menu items: %s\n") % (
        index_path, g.root, g.created, g.codepage, s("files.total"), s("classes"), s("functions.defined"),
        s("msgmap.entries"), s("rc.dialogs"), s("rc.menu_items"))
