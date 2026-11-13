"""Make a large synthetic tree by cloning samples/BigApp, then (optionally) benchmark index + explore.

Each copy goes to <out>/ModNNN/ and every class name declared in BigApp (class CXxx) is renamed CXxx_NNN so the
copies do not collapse into a few hugely ambiguous names. Encodings are preserved (byte-level for ANSI files,
decode/encode for UTF-16 .rc files).

Run:  python3 tests/tools/make_big_tree.py <out_dir> [--files 20000] [--bench]
--bench: index the tree (time, peak RAM) and time a few explore queries. Writes only to <out_dir>.
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "samples", "BigApp")
sys.path.insert(0, ROOT)


def sample_files():
    out = []
    for dp, dn, fn in os.walk(SRC):
        dn[:] = sorted(d for d in dn if d != ".mfcgraph")
        for f in sorted(fn):
            out.append(os.path.join(dp, f))
    return out


def class_names(files):
    names = set()
    for p in files:
        with open(p, "rb") as fh:
            data = fh.read()
        names.update(m.decode("ascii") for m in re.findall(rb"\bclass\s+(C[A-Za-z0-9_]+)", data))
    return sorted(names, key=len, reverse=True)


def clone(files, names, out, i):
    rx = re.compile(r"\b(%s)\b" % "|".join(names))
    suffix = "_%03d" % i
    for p in files:
        rel = os.path.relpath(p, SRC)
        dst = os.path.join(out, "Mod%03d" % i, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(p, "rb") as fh:
            data = fh.read()
        if data.startswith(b"\xff\xfe"):
            text = data[2:].decode("utf-16-le")
            data = b"\xff\xfe" + rx.sub(lambda m: m.group(1) + suffix, text).encode("utf-16-le")
        else:
            text = data.decode("latin-1")  # byte-preserving; class names are ASCII
            data = rx.sub(lambda m: m.group(1) + suffix, text).encode("latin-1")
        with open(dst, "wb") as fh:
            fh.write(data)


def peak_rss_mb():
    try:
        import resource
    except ImportError:  # Windows
        return -1.0
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return kb / 1024.0 if sys.platform != "darwin" else kb / (1024.0 * 1024.0)


def bench(out):
    from mfcgraph_core.index import build_index, save_graph, load_graph, index_path_for_root
    from mfcgraph_core.explore import explore
    t0 = time.time()
    g = build_index(out)
    t_index = time.time() - t0
    path = index_path_for_root(g.root)
    save_graph(g, path)
    t0 = time.time()
    g = load_graph(path)
    t_load = time.time() - t0
    print("files %d, nodes %d, edges %d, index file %.1f MB" % (len(g.files), len(g.nodes), len(g.edges),
                                                                os.path.getsize(path) / 1e6))
    print("index %.1f s, load %.1f s, peak RAM %.0f MB" % (t_index, t_load, peak_rss_mb()))
    queries = ["Mod007/Billing/InvoiceDlg.cpp:68", "CInvoiceDoc_042::RecalcTotal", "ID_BILLING_OPTIONS",
               "\"Không thể lưu hóa đơn\"", "selecting an invoice line in the list does not update the amount",
               "FormatMoney prints wrong decimals"]
    for q in queries:
        t0 = time.time()
        res = explore(g, q)
        print("explore %-70s %.2f s  %d chars" % (q[:70], time.time() - t0, len(res)))
    print("peak RAM after explore %.0f MB" % peak_rss_mb())


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    out = argv[0]
    target = 20000
    if "--files" in argv:
        target = int(argv[argv.index("--files") + 1])
    files = sample_files()
    names = class_names(files)
    copies = max(1, (target + len(files) - 1) // len(files))
    t0 = time.time()
    for i in range(copies):
        clone(files, names, out, i)
    print("made %d copies x %d files = %d files in %.1f s" % (copies, len(files), copies * len(files),
                                                              time.time() - t0))
    if "--bench" in argv:
        bench(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
