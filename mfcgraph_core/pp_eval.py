"""Evaluate preprocessor conditions (#if / #ifdef / #ifndef / #elif) against user-declared macros.

Interface:
    PPConfig(defines=None, undefs=(), undef_unknown=False)
        defines: {name: value_str}; undefs: names forced undefined; undef_unknown: every macro not in defines is
        undefined (compiler semantics). Builtins (_WIN32, WIN32, _MSC_VER, and __cplusplus for C++ files) are added
        unless the user lists them in undefs or defines.
    PPConfig.for_file(is_c) -> FileMacros       per-file mutable macro table (#define / #undef inside the file update it)
    FileMacros.ifdef(name) -> True | False | None          None = unknown (caller guesses)
    FileMacros.eval_if(expr_text) -> True | False | None
    parse_defines("A;B=1") -> {"A": "1", "B": "1"}; parse_names("C;D") -> {"C", "D"}
Three-valued: an unknown identifier (not declared, not undefined) is UNK unless undef_unknown is set (then 0);
UNK propagates through arithmetic, but `0 && UNK` is 0 and `1 || UNK` is 1. Function-like macro calls are UNK.
"""
import re

BUILTINS = {"_WIN32": "1", "WIN32": "1", "_MSC_VER": "1900", "_WINDOWS": "1"}
_TOK = re.compile(r"\s*(?:(0[xX][0-9a-fA-F]+|\d+)[uUlL]*|([A-Za-z_]\w*)|(&&|\|\||==|!=|<=|>=|<<|>>|[!~()<>+\-*/%&|^?:,]))")


class Unknown(Exception):
    pass


UNK = None  # three-valued logic: an unknown macro value propagates unless && / || decide the result


def parse_defines(text):
    out = {}
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, val = part.partition("=")
        out[name.strip()] = val.strip() or "1"
    return out


def parse_names(text):
    return {p.strip() for p in (text or "").split(";") if p.strip()}


class PPConfig:
    def __init__(self, defines=None, undefs=(), undef_unknown=False):
        self.defines = dict(defines or {})
        self.undefs = set(undefs)
        self.undef_unknown = undef_unknown

    def active(self):
        return bool(self.defines or self.undefs or self.undef_unknown)

    def for_file(self, is_c):
        table = {}
        for k, v in BUILTINS.items():
            table[k] = v
        if not is_c:
            table["__cplusplus"] = "199711"
        table.update(self.defines)
        for u in self.undefs:
            table.pop(u, None)
        return FileMacros(table, set(self.undefs), self.undef_unknown)


class FileMacros:
    def __init__(self, table, undefs, undef_unknown):
        self.table = table
        self.undefs = undefs
        self.undef_unknown = undef_unknown

    def define(self, name, value):
        self.table[name] = value.strip() or "1"
        self.undefs.discard(name)

    def undef(self, name):
        self.table.pop(name, None)
        self.undefs.add(name)

    def ifdef(self, name):
        if name in self.table:
            return True
        if name in self.undefs or self.undef_unknown:
            return False
        return None

    def eval_if(self, text):
        try:
            v = _Parser(_tokens(_strip_comments(text)), self).parse()
        except (Unknown, ValueError, ZeroDivisionError, IndexError, RecursionError):
            return None
        return None if v is UNK else v != 0

    def value(self, name, depth=0):
        if name in self.table:
            if depth > 8:
                return UNK
            try:
                return _Parser(_tokens(self.table[name]), self, depth + 1).parse()
            except (Unknown, ValueError, IndexError):
                return UNK
        if name in self.undefs or self.undef_unknown:
            return 0
        return UNK


def _strip_comments(s):
    return re.sub(r"/\*.*?\*/|//.*", " ", s)


def _tokens(text):
    out = []
    pos = 0
    text = text.strip()
    while pos < len(text):
        m = _TOK.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError("bad token")
        if m.group(1):
            out.append(("num", int(m.group(1), 0)))
        elif m.group(2):
            out.append(("id", m.group(2)))
        else:
            out.append(("op", m.group(3)))
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return out


class _Parser:
    """Recursive descent over C preprocessor expression precedence."""
    LEVELS = [("||",), ("&&",), ("|",), ("^",), ("&",), ("==", "!="), ("<", ">", "<=", ">="), ("<<", ">>"),
              ("+", "-"), ("*", "/", "%")]

    def __init__(self, toks, macros, depth=0):
        self.t = toks
        self.i = 0
        self.m = macros
        self.depth = depth

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else ("end", None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        v = self.ternary()
        if self.i != len(self.t):
            raise ValueError("trailing tokens")
        return v

    def ternary(self):
        c = self.binary(0)
        if self.peek() == ("op", "?"):
            self.take()
            a = self.ternary()
            if self.take() != ("op", ":"):
                raise ValueError(":")
            b = self.ternary()
            if c is UNK:
                return a if a == b else UNK
            return a if c else b
        return c

    def binary(self, level):
        if level == len(self.LEVELS):
            return self.unary()
        v = self.binary(level + 1)
        while self.peek()[0] == "op" and self.peek()[1] in self.LEVELS[level]:
            op = self.take()[1]
            if op == "||":
                r = self.binary(level + 1)
                if v == 1 or r == 1 or (v not in (UNK, 0)) or (r not in (UNK, 0)):
                    v = 1
                else:
                    v = UNK if (v is UNK or r is UNK) else 0
                continue
            if op == "&&":
                r = self.binary(level + 1)
                if (v is not UNK and v == 0) or (r is not UNK and r == 0):
                    v = 0
                else:
                    v = UNK if (v is UNK or r is UNK) else 1
                continue
            r = self.binary(level + 1)
            v = _apply(op, v, r)
        return v

    def unary(self):
        k, s = self.peek()
        if k == "op" and s in ("!", "-", "+", "~"):
            self.take()
            v = self.unary()
            if v is UNK:
                return UNK
            return {"!": lambda x: 0 if x else 1, "-": lambda x: -x, "+": lambda x: x, "~": lambda x: ~x}[s](v)
        return self.primary()

    def primary(self):
        k, s = self.take()
        if k == "num":
            return s
        if k == "op" and s == "(":
            v = self.ternary()
            if self.take() != ("op", ")"):
                raise ValueError(")")
            return v
        if k == "id":
            if s == "defined":
                paren = self.peek() == ("op", "(")
                if paren:
                    self.take()
                k2, name = self.take()
                if k2 != "id":
                    raise ValueError("defined")
                if paren and self.take() != ("op", ")"):
                    raise ValueError(")")
                r = self.m.ifdef(name)
                if r is None:
                    return UNK
                return 1 if r else 0
            if self.peek() == ("op", "("):  # function-like macro: skip its arguments, value unknown
                depth = 0
                while True:
                    k2, s2 = self.take()
                    if k2 == "end":
                        raise ValueError("unbalanced")
                    if (k2, s2) == ("op", "("):
                        depth += 1
                    elif (k2, s2) == ("op", ")"):
                        depth -= 1
                        if depth == 0:
                            return UNK
            if s in ("true",):
                return 1
            if s in ("false",):
                return 0
            return self.m.value(s, self.depth)
        raise ValueError("unexpected")


def _apply(op, a, b):
    if a is UNK or b is UNK:
        return UNK
    if op == "|":
        return a | b
    if op == "^":
        return a ^ b
    if op == "&":
        return a & b
    if op == "==":
        return 1 if a == b else 0
    if op == "!=":
        return 1 if a != b else 0
    if op == "<":
        return 1 if a < b else 0
    if op == ">":
        return 1 if a > b else 0
    if op == "<=":
        return 1 if a <= b else 0
    if op == ">=":
        return 1 if a >= b else 0
    if op == "<<":
        return a << b
    if op == ">>":
        return a >> b
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return int(a / b)
    if op == "%":
        return a % b
    raise ValueError(op)
