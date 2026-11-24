"""MCP config file writer (`mcp-config`, mcp_config.py).

Run:  python3 tests/test_mcp_config.py
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core import cli, mcp_config  # noqa: E402

LEGACY = os.path.join(ROOT, "samples", "LegacyApp")
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


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def test_entry(tmp):
    e = mcp_config.server_entry(LEGACY, launcher="x/mfcgraph.py", python="py.exe", tools="explore,refs")
    check(e["type"] == "stdio" and e["command"] == "py.exe", "entry type/command", e)
    check(e["args"][1:3] == ["serve", "--root"] and e["args"][3] == os.path.abspath(LEGACY)
          and os.path.isabs(e["args"][0]), "entry args: absolute launcher + serve --root", e["args"])
    check(e["env"] == {"MFCGRAPH_MCP_TOOLS": "explore,refs"}, "entry env", e["env"])
    d = mcp_config.server_entry(LEGACY)
    check(os.path.basename(d["args"][0]) == "mfcgraph.py" and os.path.isfile(d["args"][0]), "default launcher exists")
    for name in ("pythonw.exe", "python.exe"):
        with open(os.path.join(tmp, name), "w") as f:
            f.write("")
    check(mcp_config.console_python(os.path.join(tmp, "pythonw.exe")) == os.path.join(tmp, "python.exe"),
          "pythonw -> python")
    check(mcp_config.console_python(os.path.join(tmp, "python.exe")) == os.path.join(tmp, "python.exe"),
          "python stays")


def test_merge():
    e = {"type": "stdio", "command": "py", "args": ["a"]}
    text, act = mcp_config.merge("", "mfcgraph", e)
    check(act == "added" and json.loads(text) == {"servers": {"mfcgraph": e}}, "empty -> added", text)
    other = '{"inputs": [{"id": "tok"}], "servers": {"github": {"type": "http", "url": "u"}}}'
    text, act = mcp_config.merge(other, "mfcgraph", e)
    data = json.loads(text)
    check(act == "added" and data["servers"]["github"] == {"type": "http", "url": "u"}
          and data["inputs"] == [{"id": "tok"}] and list(data["servers"]) == ["github", "mfcgraph"],
          "other servers and keys kept", text)
    same, act = mcp_config.merge(text, "mfcgraph", e)
    check(act == "unchanged" and same == text, "same entry -> unchanged, text untouched")
    _, act = mcp_config.merge(text, "mfcgraph", dict(e, args=["b"]))
    check(act == "updated", "changed entry -> updated")
    _, act = mcp_config.merge('{"other": 1}', "mfcgraph", e)
    check(act == "added", "no servers key -> added")
    for bad in ('{ // comment\n "servers": {} }', "[1, 2]", '{"servers": [1]}', '{"servers": {},}'):
        try:
            mcp_config.merge(bad, "mfcgraph", e)
            check(False, "refuse " + bad)
        except ValueError:
            check(True, "")


def test_write(tmp):
    path = os.path.join(tmp, "ws", ".vscode", "mcp.json")
    e = mcp_config.server_entry(LEGACY, python="py")
    act, bak = mcp_config.write(path, "mfcgraph", e)
    check(act == "added" and bak is None and os.path.isfile(path), "new file in new folder, no backup", (act, bak))
    act, bak = mcp_config.write(path, "mfcgraph", e)
    check(act == "unchanged" and bak is None and not os.path.exists(path + ".bak"), "unchanged: no write, no .bak")
    before = read(path)
    act, bak = mcp_config.write(path, "mfcgraph", dict(e, command="py2"))
    check(act == "updated" and bak == path + ".bak" and read(bak) == before, "update keeps .bak of old content")
    check(not os.path.exists(path + ".mfcgraph-tmp"), "no temp file left")
    bom = os.path.join(tmp, "bom.json")
    with io.open(bom, "w", encoding="utf-8-sig") as f:
        f.write('{"servers": {"x": {"type": "stdio"}}}')
    act, _ = mcp_config.write(bom, "mfcgraph", e)
    check(act == "added" and "x" in json.loads(read(bom))["servers"], "UTF-8 BOM file merged")
    broken = os.path.join(tmp, "broken.json")
    with io.open(broken, "w", encoding="utf-8") as f:
        f.write('{"servers": { /* c */ }}')
    try:
        mcp_config.write(broken, "mfcgraph", e)
        check(False, "broken file refused")
    except ValueError:
        check(read(broken) == '{"servers": { /* c */ }}' and not os.path.exists(broken + ".bak"),
              "broken file left untouched")


def test_cli(tmp):
    code, out, err = run_cli(["mcp-config", "--root", LEGACY, "--name", "legacy"])
    data = json.loads(out)
    check(code == 0 and data["servers"]["legacy"]["args"][-1] == os.path.abspath(LEGACY), "prints a JSON snippet", out)
    check(".mcp.json" in err and "mcp.json" in err, "suggests target files on stderr", err)
    target = os.path.join(tmp, "cli", ".mcp.json")
    code, out, err = run_cli(["mcp-config", "--root", LEGACY, "--write", target, "--tools", "all"])
    check(code == 0 and out.startswith("added server 'mfcgraph'"), "--write adds", out + err)
    check(json.loads(read(target))["servers"]["mfcgraph"]["env"]["MFCGRAPH_MCP_TOOLS"] == "all", "--tools used")
    with io.open(target, "w", encoding="utf-8") as f:
        f.write("not json")
    code, out, err = run_cli(["mcp-config", "--root", LEGACY, "--write", target])
    check(code == 2 and "not plain JSON" in err, "broken target -> exit 2", (code, err))
    code, out, err = run_cli(["mcp-config", "--root", os.path.join(tmp, "nope")])
    check(code == 2, "missing root -> exit 2")


def test_isolation():
    code = ("import sys; sys.path.insert(0, %r); from mfcgraph_core import cli, mcp, query, explore; "
            "print('mfcgraph_core.mcp_config' in sys.modules)" % ROOT)
    out = subprocess.check_output([sys.executable, "-c", code]).decode().strip()
    check(out == "False", "serve/query modules do not load mcp_config", out)


def main():
    tmp = tempfile.mkdtemp(prefix="mfcgraph_mcpcfg_")
    try:
        test_entry(tmp)
        test_merge()
        test_write(tmp)
        test_cli(tmp)
        test_isolation()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("mcp_config: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
