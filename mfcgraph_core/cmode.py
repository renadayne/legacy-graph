"""C mode for .c files: C++-only keywords are ordinary identifiers in C.

Interface:
    is_c_file(path) -> bool                    ".c" files (headers stay C++: they are shared with C++ code)
    protect(tokens) -> (tokens, count)         IDENT tokens spelled like a C++-only keyword get MARK appended,
                                               so the C++ extractor treats `struct node *new; int class;` as names
    restore(raw, mark_from)                    remove MARK from every name the extractor produced for that file
                                               (mark_from = RawData sizes taken before extraction, see snapshot())
    snapshot(raw) -> dict                      sizes of the RawData lists before extracting one file
Why a marker instead of a second keyword table: the extractor compares keyword spellings in many places; renaming
the tokens keeps it untouched and the marker is removed before anything is resolved or stored.
"""
from .lexer import IDENT

MARK = "__cmode__"
CPP_ONLY = frozenset("""
new delete this class template typename namespace operator virtual public private protected friend explicit
mutable using try catch throw typeid static_cast dynamic_cast reinterpret_cast const_cast nullptr override final
and or not noexcept constexpr decltype alignas alignof static_assert co_return co_await __super afx_msg
""".split())

_LISTS = ("funcs", "classes", "msgmaps", "includes", "defines", "dynamics")


def is_c_file(path):
    return path.lower().endswith(".c")


def protect(tokens):
    out = []
    n = 0
    for t in tokens:
        if t[0] == IDENT and t[1] in CPP_ONLY:
            out.append((t[0], t[1] + MARK, t[2]))
            n += 1
        else:
            out.append(t)
    return out, n


def snapshot(raw):
    return {k: len(getattr(raw, k)) for k in _LISTS}


def _clean(v):
    if isinstance(v, str):
        return v.replace(MARK, "") if MARK in v else v
    if isinstance(v, tuple):
        return tuple(_clean(x) for x in v)
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {_clean(k): _clean(x) for k, x in v.items()}
    return v


def _clean_obj(o):
    for name in getattr(o, "__slots__", ()) or ():
        setattr(o, name, _clean(getattr(o, name)))
    if hasattr(o, "__dict__"):
        for name, v in list(vars(o).items()):
            if name == "calls":
                for c in v:
                    _clean_obj(c)
            elif name == "entries":
                for e in v:
                    _clean_obj(e)
            else:
                setattr(o, name, _clean(v))


def restore(raw, mark_from):
    for k in _LISTS:
        lst = getattr(raw, k)
        for i in range(mark_from[k], len(lst)):
            if isinstance(lst[i], tuple):
                lst[i] = _clean(lst[i])
            else:
                _clean_obj(lst[i])
