"""Tolerant tokenizer for C/C++ and Windows .rc files.

Never fails: unknown characters become punctuation tokens, unterminated
strings/comments end at the line / file end.

A token is a tuple (kind, text, line). For strings/chars, text is the content
without prefix and quotes; for preprocessor lines, the directive without '#'.
"""
import re

IDENT, NUMBER, STRING, CHAR, PUNCT, PP = range(6)

_P3 = ["<<=", ">>=", "->*", "..."]
_P2 = ["::", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "+=",
       "-=", "*=", "/=", "%=", "&=", "|=", "^=", ".*", "##"]
_PUNCT = "|".join(re.escape(p) for p in _P3 + _P2) + r"|[\s\S]"


def _master(rc_mode):
    parts = [
        r"(?P<nl>\n)",
        r"(?P<ws>[ \t\r\f\v]+)",
        r"(?P<splice>\\\r?\n)",
        r"(?P<lc>//[^\n]*)",
        r"(?P<bc>/\*[\s\S]*?(?:\*/|\Z))",
    ]
    if rc_mode:
        parts.append(r'(?P<str>"(?:""|[^"\n])*"?)')
    else:
        parts.append(r'(?P<raw>(?:u8|[uUL])?R"(?P<delim>[^()\\\s]{0,16})\((?P<rawbody>[\s\S]*?)\)(?P=delim)")')
        parts.append(r'(?P<str>(?:u8|[uUL])?"(?:\\[\s\S]|[^"\\\n])*"?)')
        parts.append(r"(?P<chr>(?:u8|[uUL])?'(?:\\.|[^'\\\n])*'?)")
    parts += [
        r"(?P<num>\.?\d(?:[eEpP][+-]|[\w.]|'(?=[0-9A-Za-z]))*)",
        r"(?P<id>[A-Za-z_$\u0080-￿][\w$\u0080-￿]*)",
        r"(?P<p>" + _PUNCT + r")",
    ]
    return re.compile("|".join(parts))


_RE_C = _master(False)
_RE_RC = _master(True)
_PPBODY = re.compile(r"(?:\\\r?\n|/\*[\s\S]*?\*/|//[^\n]*|[^\n])*")
_PP_SPLICE = re.compile(r"\\\r?\n")
_PP_BLOCK = re.compile(r"/\*[\s\S]*?\*/")
_PP_LINE = re.compile(r"//.*")


def _strip_literal(lit, quote):
    i = lit.find(quote)
    body = lit[i + 1:]
    if body.endswith(quote) and len(body) >= 1:
        body = body[:-1]
    return body


def lex(src, rc_mode):
    rx = _RE_RC if rc_mode else _RE_C
    out = []
    append = out.append
    pos, n, line = 0, len(src), 1
    line_start = True
    match = rx.match
    while pos < n:
        m = match(src, pos)
        kind = m.lastgroup
        end = m.end()
        if kind == "nl":
            line += 1
            line_start = True
        elif kind == "ws":
            pass
        elif kind == "splice":
            line += 1
        elif kind == "lc":
            pass
        elif kind == "bc":
            line += src.count("\n", pos, end)
        elif kind == "p" and line_start and src[pos] == "#":
            body = _PPBODY.match(src, pos + 1)
            text = body.group(0)
            start_line = line
            line += text.count("\n")
            text = _PP_SPLICE.sub(" ", text)
            text = _PP_BLOCK.sub(" ", text)
            text = _PP_LINE.sub("", text)
            append((PP, text.strip(), start_line))
            end = body.end()
        else:
            line_start = False
            if kind == "id":
                append((IDENT, m.group(0), line))
            elif kind == "p":
                append((PUNCT, m.group(0), line))
            elif kind == "num":
                append((NUMBER, m.group(0), line))
            elif kind == "str":
                lit = m.group(0)
                body = _strip_literal(lit, '"')
                if rc_mode:
                    body = body.replace('""', '"')
                append((STRING, body, line))
                line += lit.count("\n")
            elif kind == "chr":
                append((CHAR, _strip_literal(m.group(0), "'"), line))
            elif kind == "raw":
                append((STRING, m.group("rawbody"), line))
                line += m.group(0).count("\n")
        pos = end
    return out


def _is_false_cond(rest):
    r = rest.strip()
    return r in ("0", "(0)", "FALSE")


def filter_conditionals(tokens):
    """Keep the first active branch of each #if/#ifdef/#elif/#else chain
    ("#if 0" is false). Returns (tokens, dropped_count)."""
    st = []  # [parent_active, active, taken]
    out = []
    dropped = 0
    for t in tokens:
        if t[0] == PP:
            d = t[1]
            sp = 0
            while sp < len(d) and not d[sp].isspace():
                sp += 1
            word, rest = d[:sp], d[sp:]
            if word in ("if", "ifdef", "ifndef"):
                parent = (not st) or st[-1][1]
                cond = not (word == "if" and _is_false_cond(rest))
                st.append([parent, parent and cond, cond])
                continue
            if word == "elif" and st:
                f = st[-1]
                if f[2]:
                    f[1] = False
                else:
                    cond = not _is_false_cond(rest)
                    f[1] = f[0] and cond
                    f[2] = cond
                continue
            if word == "else" and st:
                f = st[-1]
                f[1] = f[0] and not f[2]
                f[2] = True
                continue
            if word == "endif":
                if st:
                    st.pop()
                continue
        if (not st) or st[-1][1]:
            out.append(t)
        else:
            dropped += 1
    return out, dropped
