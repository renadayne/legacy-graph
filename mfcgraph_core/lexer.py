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


_MACRO_NAME = re.compile(r"[A-Za-z_]\w*")


def _is_false_cond(rest):
    r = rest.strip()
    return r in ("0", "(0)", "FALSE")


def filter_conditionals(tokens, macros=None, stats=None):
    """Keep the active branch of each #if/#ifdef/#elif/#else chain. Returns (tokens, dropped_count).

    macros=None: first branch wins ("#if 0" is false) — the v0.2 behaviour.
    macros=pp_eval.FileMacros: conditions are evaluated; #define/#undef in active code update the table; a condition
    that cannot be decided falls back to "first branch wins". stats (dict) gets "evaluated" / "guessed" counts.
    """
    st = []  # [parent_active, active, taken]
    out = []
    dropped = 0

    def decide(word, rest):
        if macros is None:
            false = word == "if" and _is_false_cond(rest)
            if stats is not None:
                key = "evaluated" if false else "guessed"
                stats[key] = stats.get(key, 0) + 1
            return not false
        m = _MACRO_NAME.search(rest)  # "#ifdef (FOO)", "#ifdef  FOO", or a malformed "#ifdef"
        name = m.group(0) if m else ""
        if not name and word in ("ifdef", "ifndef"):
            r = None
        elif word == "ifdef":
            r = macros.ifdef(name)
        elif word == "ifndef":
            r = macros.ifdef(name)
            r = None if r is None else not r
        else:
            r = macros.eval_if(rest)
        if stats is not None:
            key = "guessed" if r is None else "evaluated"
            stats[key] = stats.get(key, 0) + 1
        return True if r is None else r

    for t in tokens:
        if t[0] == PP:
            d = t[1]
            sp = 0
            while sp < len(d) and not d[sp].isspace():
                sp += 1
            word, rest = d[:sp], d[sp:]
            if word in ("if", "ifdef", "ifndef"):
                parent = (not st) or st[-1][1]
                cond = decide(word, rest) if parent else False
                st.append([parent, parent and cond, cond])
                continue
            if word == "elif" and st:
                f = st[-1]
                if f[2]:
                    f[1] = False
                else:
                    cond = decide("if", rest) if f[0] else False
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
            if macros is not None and ((not st) or st[-1][1]) and word in ("define", "undef"):
                parts = rest.split(None, 1)
                if parts:
                    name = parts[0].split("(")[0]
                    if word == "undef":
                        macros.undef(name)
                    elif "(" not in parts[0]:
                        macros.define(name, parts[1] if len(parts) > 1 else "1")
        if (not st) or st[-1][1]:
            out.append(t)
        else:
            dropped += 1
    return out, dropped
