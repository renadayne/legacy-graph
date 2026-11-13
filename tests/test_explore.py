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


def test_render():
    from mfcgraph_core.explore import explore
    g = graph("LegacyApp")
    out = explore(g, "Export failed WriteTextFile")
    for sec in ("## Flow", "## Source", "## Blast radius"):
        check(sec in out, "S7b: section " + sec, out)
    check(out.index("## Flow") < out.index("## Source") < out.index("## Blast radius"), "S7b: section order")
    check("69\t\t\tAfxMessageBox(_T(\"Export failed\"));" in out, "S7b: line-numbered source", out)
    check("-> CLegacyDoc::ExportTo  LegacyDoc.cpp:45" in out, "S7b: flow lists the spine", out)
    out = explore(g, "MainFrm.cpp:69")
    check("57\tvoid CMainFrame::OnFileExport()" in out and "72\t}" in out, "S7b: anchored function in full", out)
    out = explore(g, "WriteTextFle")
    check("## Did you mean\nWriteTextFle → WriteTextFile" in out, "S7b: did you mean", out)
    check(explore(g, "zzzz qqqq").startswith("mfc_explore: 0 functions"), "S7b: nothing matched")
    over = []
    for b in (300, 800, 1500, 2500, 4000, 8000):
        for q in ("Export failed WriteTextFile", "MainFrm.cpp:69", "ID_FILE_EXPORT", "CExportDlg::m_strPath",
                  '"Xuất dữ liệu"', "Recalculate zoom", "zzz"):
            n = len(explore(g, q, budget=b))
            if n > b:
                over.append((q, b, n))
    check(not over, "S7b: never over budget", over)
    b = graph("BigApp")
    out = explore(b, "bấm Tính lại thì tổng tiền sai trong module Billing")
    check("Scope: Billing" in out.splitlines()[0], "S7b: scope shown in header", out.splitlines()[0])
    check(explore(b, "x", budget=None) is not None and len(explore(b, "RecalcTotal")) <= 8000, "S7b: default budget")


def test_mcp():
    import io
    import json
    import tempfile
    import shutil
    from mfcgraph_core import mcp
    from mfcgraph_core.index import save_graph
    check([t["name"] for t in mcp.tool_list({})] == ["mfc_explore"], "S8: only mfc_explore by default")
    names = [t["name"] for t in mcp.tool_list({"MFCGRAPH_MCP_TOOLS": "explore,trace, mfc_callers"})]
    check(names == ["mfc_explore", "mfc_callers", "mfc_trace"], "S8: env enables more tools", names)
    check(len(mcp.tool_list({"MFCGRAPH_MCP_TOOLS": "all"})) == len(mcp.TOOLS), "S8: all tools")
    desc = mcp.tool_list({})[0]["description"]
    check("File.cpp:120" in desc and "ID_FILE_EXPORT" in desc and "error message" in desc, "S8: query forms listed")
    tmp = tempfile.mkdtemp(prefix="mfcgraph_mcp_")
    try:
        path = os.path.join(tmp, "index.mfg")
        save_graph(graph("LegacyApp"), path)
        reqs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "mfc_explore", "arguments": {"query": "MainFrm.cpp:69", "budget": 3000}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                 "params": {"name": "mfc_trace", "arguments": {"query": "Export"}}}]
        inp = io.BytesIO(b"".join(json.dumps(r).encode() + b"\n" for r in reqs))
        out = io.BytesIO()
        old = os.environ.pop("MFCGRAPH_MCP_TOOLS", None)
        try:
            mcp.run_mcp_server(path, inp, out)
        finally:
            if old is not None:
                os.environ["MFCGRAPH_MCP_TOOLS"] = old
        res = [json.loads(x) for x in out.getvalue().decode("utf-8").splitlines()]
        check("mfc_explore FIRST" in res[0]["result"]["instructions"], "S8: instructions")
        check([t["name"] for t in res[1]["result"]["tools"]] == ["mfc_explore"], "S8: tools/list")
        text = res[2]["result"]["content"][0]["text"]
        check("CMainFrame::OnFileExport" in text and len(text) <= 3000, "S8: explore over MCP", text[:300])
        check(res[3]["result"]["isError"], "S8: disabled tool refused")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_rank()
    for t in [globals().get(n) for n in sorted(globals()) if n.startswith("test_") and n != "test_rank"]:
        t()
    print("explore: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
