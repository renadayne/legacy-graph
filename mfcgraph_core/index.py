"""Scanning a source tree, and saving / loading the graph.

The index is plain text (one record per line, tab separated, escaped), so it is easy to audit and diff.
v1 is the format of the frozen C++ edition; v2 (Python, v0.2) adds:
  F record: two trailing columns mtime (int seconds) and size (bytes) of the source file at index time.
  T<TAB>func_node<TAB>line<TAB>text   string literal found in the body of function node func_node.
load_graph reads v1 and v2 (v1: texts empty, mtime 0, size -1).
"""
import hashlib
import os
import sys
import time

from .encoding import decode_bytes
from .extract_cpp import extract_cpp
from .extract_rc import extract_rc
from .lexer import lex, filter_conditionals
from .model import RawData, SrcFile, Graph, Node, Edge
from .resolve import resolve

CPP_EXTS = frozenset([".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inl", ".ipp"])
RC_EXTS = frozenset([".rc", ".rc2", ".dlg"])
DEFAULT_SKIP = frozenset([".git", ".svn", ".hg", ".vs", ".vscode", ".mfcgraph", "debug", "release", "x64",
                          "win32", "ipch", "obj", "bin", "node_modules", "packages", "unicode debug",
                          "unicode release", "__pycache__"])


# Index format: v1 = MFCGRAPH/F/N/E/S. v2 adds F columns mtime,size and T records (func, line, text).
INDEX_VERSION = 2
SUPPORTED_VERSIONS = ("1", "2")


def index_path_for_root(root):
    return os.path.join(root, ".mfcgraph", "index.mfg")


def build_index(root, codepage=1258, excludes=(), max_file_bytes=8 << 20, verbose=False):
    if not os.path.isdir(root):
        raise ValueError("not a directory: " + root)
    root = os.path.abspath(root)
    skip = set(DEFAULT_SKIP) | {x.lower() for x in excludes}
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d.lower() not in skip)
        for fn in sorted(filenames):
            ext = os.path.splitext(fn)[1].lower()
            if ext not in CPP_EXTS and ext not in RC_EXTS:
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > max_file_bytes:
                    continue
            except OSError:
                continue
            paths.append(p)
    # Deterministic order (same as the C++ edition): sort by relative path.
    paths.sort(key=lambda p: os.path.relpath(p, root).replace(os.sep, "/"))

    raw = RawData()
    for done, p in enumerate(paths, 1):
        try:
            with open(p, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        text, enc = decode_bytes(data, codepage)
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        fi = len(raw.files)
        try:
            mtime = int(os.path.getmtime(p))
        except OSError:
            mtime = 0
        raw.files.append(SrcFile(rel, enc, hashlib.blake2b(data, digest_size=8).hexdigest(), text.count("\n") + 1,
                                 mtime=mtime, size=len(data)))
        is_rc = os.path.splitext(p)[1].lower() in RC_EXTS
        active, dropped = filter_conditionals(lex(text, is_rc))
        raw.files[fi].skipped_tokens = dropped
        if is_rc:
            extract_rc(active, fi, raw)
        else:
            extract_cpp(active, fi, raw)
        if verbose and done % 500 == 0:
            sys.stderr.write("  %d/%d files\n" % (done, len(paths)))

    g = Graph()
    g.root = root
    g.codepage = codepage
    g.created = time.strftime("%Y-%m-%d %H:%M:%S")
    resolve(raw, g)
    return g


def _esc(s):
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _unesc(s):
    if "\\" not in s:
        return s
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            i += 1
            c2 = s[i]
            out.append({"t": "\t", "n": "\n", "r": "\r"}.get(c2, c2))
        else:
            out.append(c)
        i += 1
    return "".join(out)


def save_graph(g, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines = ["MFCGRAPH\t%d\t%s\t%d\t%s" % (INDEX_VERSION, _esc(g.root), g.codepage, _esc(g.created))]
    for f in g.files:
        lines.append("F\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d" % (_esc(f.path), _esc(f.encoding), f.hash, f.lines,
                                                            1 if f.brace_error else 0, f.skipped_tokens,
                                                            f.mtime, f.size))
    for n in g.nodes:
        lines.append("N\t%d\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%s\t%s\t%s" % (
            n.id, _esc(n.kind), _esc(n.name), _esc(n.qname), n.file, n.line, n.end, n.owner, _esc(n.flags),
            _esc(n.sig), _esc(n.extra)))
    for e in g.edges:
        lines.append("E\t%d\t%d\t%s\t%d\t%d\t%s\t%s" % (e.src, e.dst, _esc(e.kind), e.file, e.line, _esc(e.conf),
                                                        _esc(e.extra)))
    for (fn, line, text) in g.texts:
        lines.append("T\t%d\t%d\t%s" % (fn, line, _esc(text)))
    for k in sorted(g.stats):
        lines.append("S\t%s\t%s" % (_esc(k), _esc(g.stats[k])))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def load_graph(path):
    try:
        with open(path, "r", encoding="utf-8", newline="\n") as fh:
            data = fh.read()
    except OSError:
        raise ValueError("cannot read index %s (run: mfcgraph index <root>)" % path)
    g = Graph()
    header = False
    for line in data.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if not line:
            continue
        f = [_unesc(x) for x in line.split("\t")]
        tag = f[0]
        if tag == "N" and len(f) >= 12:
            n = Node(f[2], f[3], f[4])
            n.id = int(f[1])
            n.file, n.line, n.end, n.owner = int(f[5]), int(f[6]), int(f[7]), int(f[8])
            n.flags, n.sig, n.extra = f[9], f[10], f[11]
            g.nodes.append(n)
        elif tag == "E" and len(f) >= 8:
            g.edges.append(Edge(int(f[1]), int(f[2]), f[3], int(f[4]), int(f[5]), f[6], f[7]))
        elif tag == "F" and len(f) >= 7:
            sf = SrcFile(f[1], f[2], f[3], int(f[4]), f[5] == "1", int(f[6]))
            if len(f) >= 9:
                sf.mtime, sf.size = int(f[7]), int(f[8])
            g.files.append(sf)
        elif tag == "T" and len(f) >= 4:
            g.texts.append((int(f[1]), int(f[2]), f[3]))
        elif tag == "S" and len(f) >= 3:
            g.stats[f[1]] = f[2]
        elif tag == "MFCGRAPH":
            if len(f) < 5 or f[1] not in SUPPORTED_VERSIONS:
                raise ValueError("unsupported index version")
            g.root, g.codepage, g.created = f[2], int(f[3]), f[4]
            header = True
    if not header:
        raise ValueError("not an mfcgraph index: " + path)
    for i, n in enumerate(g.nodes):
        if n.id != i:
            raise ValueError("corrupt index (node ids)")
    nn = len(g.nodes)
    for e in g.edges:
        if not (0 <= e.src < nn and 0 <= e.dst < nn):
            raise ValueError("corrupt index (edges)")
    for t in g.texts:
        if not 0 <= t[0] < nn:
            raise ValueError("corrupt index (texts)")
    g.build_adjacency()
    return g


def find_index_upwards(start):
    p = os.path.abspath(start)
    while True:
        cand = os.path.join(p, ".mfcgraph", "index.mfg")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(p)
        if parent == p:
            return ""
        p = parent
