"""Build dist/mfcgraph-py-<version>.zip (standard library zipfile only).

Includes the launcher, mfcgraph_core/, tests/, samples/, docs/, README.md, CHANGELOG.md, CLAUDE.md.
Excludes __pycache__, *.pyc, .mfcgraph/ (index files contain code structure), cpp-reference/, dist/, .git/, .claude/.

Run:  python3 tools/package.py [--out DIR]
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core import VERSION  # noqa: E402

INCLUDE = ["mfcgraph.py", "README.md", "CHANGELOG.md", "CLAUDE.md", "mfcgraph_core", "tests", "samples", "docs",
           "tools"]
EXCLUDE_DIRS = {"__pycache__", ".mfcgraph", "cpp-reference", "dist", ".git", ".claude"}
EXCLUDE_EXT = {".pyc", ".pyo"}


def files_to_pack(root=ROOT):
    out = []
    for item in INCLUDE:
        p = os.path.join(root, item)
        if os.path.isfile(p):
            out.append(item)
            continue
        for dp, dn, fn in os.walk(p):
            dn[:] = sorted(d for d in dn if d not in EXCLUDE_DIRS)
            for f in sorted(fn):
                if os.path.splitext(f)[1].lower() in EXCLUDE_EXT:
                    continue
                out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return out


def build(out_dir=None):
    out_dir = out_dir or os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    base = "mfcgraph-py-%s" % ".".join(VERSION.split(".")[:2])
    path = os.path.join(out_dir, base + ".zip")
    names = files_to_pack()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in names:
            z.write(os.path.join(ROOT, *rel.split("/")), base + "/" + rel)
    return path, names


def main(argv):
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    path, names = build(out)
    print("wrote %s (%d files)" % (path, len(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
