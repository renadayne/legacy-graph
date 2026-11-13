"""Checks for explore ranking / rendering / end-to-end (explore_rank, explore_render, explore).

Run:  python3 tests/test_explore.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.index import build_index  # noqa: E402
from mfcgraph_core.explore_query import parse_query  # noqa: E402
from mfcgraph_core.explore_seed import seed  # noqa: E402
from mfcgraph_core.explore_rank import rank  # noqa: E402

passed = 0
failed = 0
_graphs = {}


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + str(detail) if detail else ""))


def graph(name):
    if name not in _graphs:
        _graphs[name] = build_index(os.path.join(ROOT, "samples", name))
    return _graphs[name]


def ranked(g, q):
    r = seed(g, parse_query(q), (), q)
    return rank(g, r.seeds, r.scope_dirs)


def names(g, path):
    return [g.nodes[n].qname for n in path]


def test_rank():
    g = graph("LegacyApp")
    scores, spine = ranked(g, "Export failed WriteTextFile")
    want = ["CMainFrame::OnFileExport", "CLegacyDoc::ExportTo", "CLegacyDoc::ExportCsv", "util::WriteTextFile"]
    want2 = want[:2] + ["CLegacyDoc::ExportXml"] + want[3:]
    check(any(names(g, p) in (want, want2) for p in spine), "S6: spine OnFileExport -> ... -> WriteTextFile",
          [names(g, p) for p in spine])
    top = sorted(scores, key=lambda n: -scores[n])[:3]
    check("CMainFrame::OnFileExport" in names(g, top), "S6: handler ranked top 3", names(g, top))
    scores, spine = ranked(g, "ID_TOOLS_RECALC")
    check(any(names(g, p)[-1] == "CLegacyDoc::OnToolsRecalc" and g.nodes[p[0]].kind == "ui" for p in spine),
          "S6: lone seed -> spine from UI entry", [names(g, p) for p in spine])
    b = graph("BigApp")
    scores, _ = ranked(b, "chart is blank in monthly report view")
    ctor = [n for n in scores if b.nodes[n].qname == "CReportView::CReportView"]
    od = [n for n in scores if b.nodes[n].qname == "CReportView::OnDraw"]
    check(od and (not ctor or scores[od[0]] > scores[ctor[0]]), "S6: ctor not above OnDraw for words")
    scores, _ = ranked(b, "Billing/ discount")
    out = [n for n in scores if b.nodes[n].kind == "function" and b.files[b.nodes[n].file].path.startswith("Report/")]
    best = max(scores.values())
    check(all(scores[n] < best * 0.5 for n in out), "S6: out-of-scope nodes damped")
    check(rank(b, {}, ()) == ({}, []), "S6: no seeds -> empty")


def main():
    test_rank()
    for t in [globals().get(n) for n in sorted(globals()) if n.startswith("test_") and n != "test_rank"]:
        t()
    print("explore: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
