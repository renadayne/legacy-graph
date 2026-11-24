"""Remembered index settings (<root>/.mfcgraph/settings.json).

Run:  python3 tests/test_settings.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core import cli, settings  # noqa: E402
from mfcgraph_core.index import load_graph, index_path_for_root  # noqa: E402

BIGAPP = os.path.join(ROOT, "samples", "BigApp")
passed = 0
failed = 0


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + str(detail) if detail else ""))


def run_cli(args):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


def graph_summary(root):
    g = load_graph(index_path_for_root(root))
    return len(g.files), g.codepage, sorted(g.pp_defines), g.pp_undef_unknown


def test_roundtrip(tmp):
    root = os.path.join(tmp, "BigApp")
    shutil.copytree(BIGAPP, root, ignore=shutil.ignore_patterns(".mfcgraph"))
    code, out, err = run_cli(["index", root, "--vcxproj", os.path.join(root, "BigApp.sln"), "--codepage", "932",
                              "--define", "EXTRA=2", "--config", "Release|Win32"])
    check(code == 0, "first index ok", err)
    with io.open(settings.settings_path(root), encoding="utf-8") as f:
        data = json.load(f)
    check(data["vcxproj"] == ["BigApp.sln"] and data["codepage"] == 932 and data["define"] == "EXTRA=2"
          and data["config"] == "Release|Win32" and data["format"] == 1, "settings saved (paths relative)", data)
    first = graph_summary(root)

    code, out, err = run_cli(["index", root, "-v"])
    check(code == 0 and out.startswith("Using saved settings: codepage 932, projects BigApp.sln"),
          "index without options reuses settings (-v is not a setting)", out + err)
    check(graph_summary(root) == first, "same index as the first run", (graph_summary(root), first))

    moved = os.path.join(tmp, "moved")
    shutil.move(root, moved)
    code, out, err = run_cli(["index", moved])
    check(code == 0 and graph_summary(moved)[0] == first[0], "relative project paths survive moving the folder",
          out + err)

    code, out, err = run_cli(["index", moved, "--codepage", "1258"])
    check(code == 0 and "Using saved" not in out, "any setting option -> fresh settings", out)
    s = settings.load(moved)
    check(s["vcxproj"] == [] and s["codepage"] == 1258 and s["define"] == "", "no hidden merge with old settings", s)
    check("project BigApp" not in out and graph_summary(moved)[2] == [], "projects not used any more", out)


def test_broken_and_types(tmp):
    root = os.path.join(tmp, "Legacy")
    shutil.copytree(os.path.join(ROOT, "samples", "LegacyApp"), root, ignore=shutil.ignore_patterns(".mfcgraph"))
    os.makedirs(os.path.join(root, ".mfcgraph"))
    with io.open(settings.settings_path(root), "w", encoding="utf-8") as f:
        f.write("{not json")
    code, out, err = run_cli(["index", root])
    check(code == 0 and "Using saved" not in out, "broken settings.json ignored", out + err)
    check(settings.load(root) is not None, "settings rewritten after index")
    with io.open(settings.settings_path(root), "w", encoding="utf-8") as f:
        f.write('{"codepage": true, "define": 5, "vcxproj": ["a.vcxproj", 3], "undef_unknown": true}')
    s = settings.load(root)
    check(s["codepage"] == 1258 and s["define"] == "" and s["vcxproj"] == ["a.vcxproj"] and s["undef_unknown"],
          "wrong types fall back to defaults", s)
    check(settings.describe(dict(settings.DEFAULTS, define="A;B", undef_unknown=True))
          == "codepage 1258, define A;B, undef-unknown", "describe line")


def main():
    tmp = tempfile.mkdtemp(prefix="mfcgraph_set_")
    try:
        test_roundtrip(tmp)
        test_broken_and_types(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("settings: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
