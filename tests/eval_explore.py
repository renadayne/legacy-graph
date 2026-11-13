"""Evaluate mfc_explore on tests/scenarios.json (samples/BigApp).

For each scenario: run explore(query, budget=max_chars) and check that every must_include function has CODE in the
"## Source" section — at least one body line (not only the signature, not only its name in a list).
"Name@path" means the definition of Name in that file. Prints a table and the totals.

Run:  python3 tests/eval_explore.py [--show ID] [--samples DIR] [--scenarios FILE]
Exit code 1 if mean recall < 0.9 or any result exceeds its budget.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core.index import build_index  # noqa: E402
from mfcgraph_core.explore import explore  # noqa: E402

RECALL_TARGET = 0.9
_LINE = re.compile(r"^(\d+)\t")


def source_lines(out):
    """{file path: set(line numbers)} shown in the Source section."""
    shown = {}
    if "## Source\n" not in out:
        return shown
    sec = out.split("## Source\n", 1)[1]
    sec = re.split(r"\n## ", sec, maxsplit=1)[0]
    cur = None
    for ln in sec.split("\n"):
        if ln.startswith("### "):
            cur = ln[4:].split(" — ", 1)[0]
            shown.setdefault(cur, set())
            continue
        m = _LINE.match(ln)
        if m and cur is not None:
            shown[cur].add(int(m.group(1)))
    return shown


def definitions(g, entry):
    name, _, path = entry.partition("@")
    out = []
    for n in g.nodes:
        if n.kind != "function" or "decl" in n.flags.split(",") or n.file < 0:
            continue
        if n.qname != name and not n.qname.endswith("::" + name) and n.name != name:
            continue
        if n.qname != name and "::" in name:
            continue
        if path and g.files[n.file].path != path:
            continue
        out.append(n)
    return out


def has_code(g, n, shown):
    lines = shown.get(g.files[n.file].path, set())
    body = set(range(n.line + 1, n.end))
    if not body:
        return n.line in lines
    sig_end = n.line
    return bool(lines & set(range(sig_end + 1, n.end + 1))) and n.line in lines


def evaluate(g, scenarios):
    rows = []
    for s in scenarios:
        out = explore(g, s["query"], s.get("max_chars"))
        shown = source_lines(out)
        missing = []
        for entry in s["must_include"]:
            defs = definitions(g, entry)
            if not any(has_code(g, n, shown) for n in defs):
                missing.append(entry + ("" if defs else " (not in index!)"))
        k = len(s["must_include"])
        rows.append({"id": s["id"], "recall": (k - len(missing)) / float(k) if k else 1.0, "chars": len(out),
                     "budget": s.get("max_chars"), "missing": missing, "out": out, "query": s["query"]})
    return rows


def main(argv):
    samples = os.path.join(ROOT, "samples", "BigApp")
    scen = os.path.join(HERE, "scenarios.json")
    show = None
    i = 0
    while i < len(argv):
        if argv[i] == "--show" and i + 1 < len(argv):
            show = argv[i + 1]
            i += 1
        elif argv[i] == "--samples" and i + 1 < len(argv):
            samples = argv[i + 1]
            i += 1
        elif argv[i] == "--scenarios" and i + 1 < len(argv):
            scen = argv[i + 1]
            i += 1
        i += 1
    with io.open(scen, encoding="utf-8") as fh:
        scenarios = json.load(fh)
    g = build_index(samples)
    rows = evaluate(g, scenarios)
    print("%-4s %-7s %-12s %s" % ("id", "recall", "chars", "missing"))
    for r in rows:
        print("%-4s %-7.2f %-12s %s" % (r["id"], r["recall"], "%d/%s" % (r["chars"], r["budget"]),
                                      ", ".join(r["missing"]) or "-"))
        if show is not None and str(r["id"]) == str(show):
            print("---- query: %s\n%s----" % (r["query"], r["out"]))
    mean = sum(r["recall"] for r in rows) / max(1, len(rows))
    over = [r["id"] for r in rows if r["budget"] and r["chars"] > r["budget"]]
    print("mean recall %.3f (target %.2f); within budget %d/%d" % (mean, RECALL_TARGET, len(rows) - len(over),
                                                                 len(rows)))
    return 0 if mean >= RECALL_TARGET and not over else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
