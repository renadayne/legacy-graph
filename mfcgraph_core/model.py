"""Raw facts produced by the extractors, and the resolved graph used by queries."""


class RawCall:
    __slots__ = ("qual", "recv", "recv_type", "recv_call", "name", "line", "member")

    def __init__(self, name, line):
        self.qual = ""       # "X" for X::f(), "::" for ::f()
        self.recv = ""       # obj.f() / p->f(); "this"
        self.recv_type = ""  # ((T*)p)->f() -> T
        self.recv_call = ""  # GetDocument()->f() -> GetDocument
        self.name = name
        self.line = line
        self.member = False


class RawFunc:
    def __init__(self):
        self.file = -1
        self.cls = ""      # owner class or out-of-line qualifier
        self.ns = ""
        self.name = ""
        self.line = 0
        self.end = 0
        self.sig = ""
        self.is_def = False
        self.is_virtual = False
        self.calls = []
        self.runtime = []  # (class, line)
        self.sends = []    # (api, [CAPS...], line)
        self.ddx = []      # (macro, id, member, line)
        self.locals = {}   # variable -> type
        self.strings = []  # (line, text) string literals in the body (see extract_cpp.scan_strings)
        self.refs = []     # (name, recv, line, mode) member/global variable refs, mode 'r'|'w' (scan_refs)


class RawClass:
    def __init__(self):
        self.file = -1
        self.name = ""
        self.ns = ""
        self.bases = []
        self.line = 0
        self.end = 0
        self.fields = {}
        self.idd = ""


class RawMsgEntry:
    __slots__ = ("macro", "kind", "id", "id2", "handler", "line")

    def __init__(self, macro, line):
        self.macro = macro
        self.kind = ""
        self.id = ""
        self.id2 = ""
        self.handler = ""
        self.line = line


class RawMsgMap:
    def __init__(self, file, line):
        self.file = file
        self.cls = ""
        self.base = ""
        self.line = line
        self.entries = []


class SrcFile:
    __slots__ = ("path", "encoding", "hash", "lines", "brace_error", "skipped_tokens", "mtime", "size")

    def __init__(self, path="", encoding="", hash_="", lines=0, brace_error=False, skipped=0, mtime=0, size=-1):
        self.path = path
        self.encoding = encoding
        self.hash = hash_
        self.lines = lines
        self.brace_error = brace_error
        self.skipped_tokens = skipped
        self.mtime = mtime   # int seconds at index time (0 = unknown, e.g. v1 index)
        self.size = size     # bytes at index time (-1 = unknown)


class RawData:
    def __init__(self):
        self.files = []
        self.funcs = []
        self.classes = []
        self.msgmaps = []
        self.includes = []   # (file, target, line)
        self.defines = []    # (file, name, value, line)
        self.dynamics = []   # (file, macro, cls, base, line)
        self.dialogs = []    # dict(file, id, caption, line, controls=[(type, text, id, line)])
        self.uiitems = []    # dict(file, kind, owner, label, id, line)
        self.strings = []    # (file, id, text, line)
        self.unknown_macros = {}


class Node:
    __slots__ = ("id", "kind", "name", "qname", "file", "line", "end", "owner", "flags", "sig", "extra")

    def __init__(self, kind="", name="", qname=""):
        self.id = 0
        self.kind = kind    # file | class | function | id | dialog | ui | external
        self.name = name
        self.qname = qname
        self.file = -1
        self.line = 0
        self.end = 0
        self.owner = -1
        self.flags = ""
        self.sig = ""
        self.extra = ""


class Edge:
    __slots__ = ("src", "dst", "kind", "file", "line", "conf", "extra")

    def __init__(self, src, dst, kind, file=-1, line=0, conf="", extra=""):
        self.src = src
        self.dst = dst
        self.kind = kind
        self.file = file
        self.line = line
        self.conf = conf
        self.extra = extra


class Graph:
    def __init__(self):
        self.root = ""
        self.codepage = 1252
        self.created = ""
        self.files = []
        self.nodes = []
        self.edges = []
        self.stats = {}
        self.texts = []   # (func_node, line, text): string literals in function bodies (index v2)
        self.refs = []    # (func_node, line, "Class::field" | "g_name" | "ID_X", mode 'r'|'w'); DDX counts as 'w'
        self.out = []
        self.inn = []

    def build_adjacency(self):
        self.out = [[] for _ in self.nodes]
        self.inn = [[] for _ in self.nodes]
        for i, e in enumerate(self.edges):
            self.out[e.src].append(i)
            self.inn[e.dst].append(i)
