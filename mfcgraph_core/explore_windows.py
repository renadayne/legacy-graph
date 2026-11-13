"""Line windows inside a function body, and line-numbered rendering. Pure functions, no graph access.

Interface:
    windows_for(func_span, focus_lines, max_lines, radius=6) -> list[(start, end)]
        func_span = (first, last) 1-based inclusive lines of the function (signature .. closing brace).
        Takes +-radius lines around every focus line (clipped to the span), always keeps the signature line and
        the closing line, merges windows separated by <= MERGE_GAP lines. If the result exceeds max_lines the
        radius shrinks (6, 4, 2, 0); if still too long, later focus lines are dropped. No focus lines -> the head
        of the function (as many lines as fit) plus the closing line. Whole span if it fits and focus is empty.
    render(lines, windows, path="") -> str
        lines = file content as a list of strings (index 0 = line 1). Each shown line is "N<TAB>text".
        Between windows (and for gaps inside the function) an elision marker is inserted:
        "… lines a-b elided — mfc_explore "path:a-b" returns them"
    signature_only(lines, func_span, max_sig_lines=4) -> str
        The signature only (up to the line with "{", the brace itself removed), line-numbered.
"""

MERGE_GAP = 3
RADII = (6, 4, 2, 0)


def _merge(wins):
    out = []
    for s, e in sorted(wins):
        if out and s - out[-1][1] - 1 <= MERGE_GAP:
            if e > out[-1][1]:
                out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def _size(wins):
    return sum(e - s + 1 for s, e in wins)


def _build(first, last, focus, radius):
    wins = [(first, first), (last, last)]
    for f in focus:
        wins.append((max(first, f - radius), min(last, f + radius)))
    return _merge(wins)


def windows_for(func_span, focus_lines, max_lines, radius=6):
    first, last = func_span
    if last < first:
        last = first
    max_lines = max(2, max_lines)
    focus = sorted({f for f in focus_lines if first <= f <= last})
    if not focus:
        if last - first + 1 <= max_lines:
            return [(first, last)]
        return _merge([(first, first + max_lines - 2), (last, last)])
    for r in [radius] + [x for x in RADII if x < radius]:
        wins = _build(first, last, focus, r)
        if _size(wins) <= max_lines:
            return wins
    while len(focus) > 1:
        focus = focus[:-1]
        wins = _build(first, last, focus, 0)
        if _size(wins) <= max_lines:
            return wins
    return _build(first, last, focus, 0)


def elision(path, a, b):
    if a == b:
        return '… line %d elided — mfc_explore "%s:%d" returns it' % (a, path, a)
    return '… lines %d-%d elided — mfc_explore "%s:%d-%d" returns them' % (a, b, path, a, b)


def _line(lines, n):
    text = lines[n - 1] if 0 < n <= len(lines) else ""
    return "%d\t%s" % (n, text.rstrip("\r\n").rstrip())


def render(lines, windows, path=""):
    out = []
    prev = None
    for s, e in windows:
        if prev is not None and s > prev + 1:
            out.append(elision(path, prev + 1, s - 1))
        for n in range(s, e + 1):
            out.append(_line(lines, n))
        prev = e
    return "\n".join(out)


def signature_only(lines, func_span, max_sig_lines=4):
    first, last = func_span
    out = []
    for n in range(first, min(last, first + max_sig_lines - 1) + 1):
        text = lines[n - 1] if 0 < n <= len(lines) else ""
        brace = text.find("{")
        if brace >= 0:
            head = text[:brace].rstrip()
            if head.strip():
                out.append("%d\t%s" % (n, head))
            break
        out.append(_line(lines, n))
    return "\n".join(out)
