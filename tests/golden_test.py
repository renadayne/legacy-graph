"""Golden tests for CLI output on samples/LegacyApp.

Runs a fixed list of commands through cli.main() in-process, captures stdout and compares it with
tests/golden/<name>.txt. Index is written to a temp dir (never into samples/).

Run:     python3 tests/golden_test.py
Update:  python3 tests/golden_test.py --update
"""
import difflib
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core import cli  # noqa: E402
from mfcgraph_core.index import build_index, save_graph  # noqa: E402

GOLDEN_DIR = os.path.join(HERE, "golden")

CASES = [
    ("trace_export", ["trace", "Export"]),
    ("trace_idd_export", ["trace", "IDD_EXPORT"]),
    ("callers_recalculate", ["callers", "CLegacyDoc::Recalculate"]),
    ("callees_refreshany", ["callees", "RefreshAny"]),
    ("impact_exportcsv", ["impact", "CLegacyDoc::ExportCsv"]),
    ("context_exportdlg_onok", ["context", "CExportDlg::OnOK"]),
    ("msgmap_legacyapp", ["msgmap", "CLegacyApp"]),
    ("search_recalc", ["search", "recalc"]),
    ("diagnose", ["diagnose"]),
    ("refs_strpath", ["refs", "CExportDlg::m_strPath"]),
    ("refs_values_bare", ["refs", "m_values"]),
    ("explore_export", ["explore", "Export failed WriteTextFile"]),
    ("explore_anchor", ["explore", "MainFrm.cpp:69", "--budget", "3000"]),
    ("explore_typo", ["explore", "WriteTextFle"]),
]


def build_sample_index(samples, tmpdir):
    g = build_index(samples, 1258)
    path = os.path.join(tmpdir, "index.mfg")
    save_graph(g, path)
    return path


def run_cli(args, ipath):
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main(list(args) + ["--index", ipath])
    return buf.getvalue()


def run_cases(cases, samples, update=False):
    """Return (passed, failed). With update=True rewrite golden files instead of comparing."""
    tmpdir = tempfile.mkdtemp(prefix="mfcgraph_golden_")
    passed = failed = 0
    try:
        ipath = build_sample_index(samples, tmpdir)
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        for name, args in cases:
            out = run_cli(args, ipath)
            gpath = os.path.join(GOLDEN_DIR, name + ".txt")
            if update:
                with io.open(gpath, "w", encoding="utf-8", newline="\n") as f:
                    f.write(out)
                print("updated " + os.path.relpath(gpath, ROOT))
                passed += 1
                continue
            try:
                with io.open(gpath, encoding="utf-8", newline="") as f:
                    want = f.read()
            except IOError:
                want = None
            if want == out:
                passed += 1
                continue
            failed += 1
            print("FAIL golden: %s  (%s)" % (name, " ".join(args)))
            if want is None:
                print("  missing %s; run with --update" % gpath)
            else:
                diff = difflib.unified_diff(want.splitlines(True), out.splitlines(True),
                                            "golden/" + name + ".txt", "actual")
                sys.stdout.write("".join(diff))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return passed, failed


def main(argv):
    update = "--update" in argv
    samples = os.path.join(ROOT, "samples", "LegacyApp")
    passed, failed = run_cases(CASES, samples, update)
    print("golden: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
