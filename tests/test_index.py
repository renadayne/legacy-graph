"""Index format checks (v2 records, v1 compatibility).

Run:  python3 tests/test_index.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.index import build_index, save_graph, load_graph  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples", "LegacyApp")
passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + str(detail) if detail else ""))


def by_qname(g, q):
    for n in g.nodes:
        if n.qname == q and "decl" not in n.flags:
            return n.id
    return -1


def test_v2_roundtrip(g, tmp):
    path = os.path.join(tmp, "index.mfg")
    save_graph(g, path)
    with open(path, encoding="utf-8") as fh:
        check(fh.readline().startswith("MFCGRAPH\t2\t"), "S2b: header version 2")
    g2 = load_graph(path)
    check(g2.texts == g.texts and len(g.texts) > 0, "S2b: texts survive save/load", len(g.texts))
    check([(f.mtime, f.size) for f in g2.files] == [(f.mtime, f.size) for f in g.files], "S2b: mtime/size kept")
    check(all(f.size > 0 and f.mtime > 0 for f in g2.files), "S2b: mtime/size recorded")
    fe = by_qname(g2, "CMainFrame::OnFileExport")
    check((fe, 69, "Export failed") in g2.texts, "S2b: text attached to function node")


def test_v1_load():
    g = load_graph(os.path.join(HERE, "data", "legacy_v1.mfg"))
    check(len(g.nodes) > 100 and g.texts == [], "S2b: v1 index loads (texts empty)")
    check(all(f.mtime == 0 and f.size == -1 for f in g.files), "S2b: v1 has unknown mtime/size")


def main():
    tmp = tempfile.mkdtemp(prefix="mfcgraph_idx_")
    try:
        g = build_index(SAMPLES, 1258)
        test_v2_roundtrip(g, tmp)
        test_v1_load()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("index: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
