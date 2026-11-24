"""Optional GUI: logic (no display needed), CLI isolation, missing tkinter, and a window smoke test if possible.

Run:  python3 tests/test_gui.py
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

from mfcgraph_core import cli  # noqa: E402
from mfcgraph_gui import logic  # noqa: E402

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


def test_logic(tmp):
    root = os.path.join(tmp, "BigApp")
    shutil.copytree(BIGAPP, root, ignore=shutil.ignore_patterns(".mfcgraph"))
    sln = os.path.join(root, "BigApp.sln")
    entries = logic.solution_projects(sln)
    projects = [p for _, p in entries]
    check([n for n, _ in entries] == ["BigApp", "Billing"], "solution projects", entries)
    check(logic.project_configs(projects) == ["Release|Win32", "Release|x64", "Debug|Win32"],
          "configs union, Release first", logic.project_configs(projects))
    check(logic.common_root(projects) == root, "common root of projects", logic.common_root(projects))

    try:
        logic.index_argv(logic.Form())
        check(False, "empty root refused")
    except ValueError:
        check(True, "")
    form = logic.Form(root=root, projects=projects, config="Debug|Win32", scope="folders", codepage=932,
                      define=" EXTRA=1 ", undef="", exclude="")
    argv = logic.index_argv(form)
    check(argv == ["index", root, "--codepage", "932", "--vcxproj", ";".join(projects), "--config", "Debug|Win32",
                   "--vcxproj-scope", "folders", "--define", "EXTRA=1"], "index argv from form", argv)

    lines = []
    code = logic.run_index(form, lines.append)
    text = "".join(lines)
    check(code == 0 and logic.has_index(root), "run_index builds the index", text)
    check(text.startswith("> mfcgraph index") and "project BigApp [Debug|Win32]" in text and "Indexed 47 files" in text,
          "run_index streams the log", text)
    back = logic.form_from_settings(root)
    check(back.projects == projects and back.config == "Debug|Win32" and back.scope == "folders"
          and back.codepage == 932 and back.define == "EXTRA=1", "form prefilled from settings.json", vars(back))
    check(logic.form_from_settings(os.path.join(tmp, "none")).projects == [], "no settings -> empty form")
    lines = []
    check(logic.run_index(logic.Form(), lines.append) == 2 and "error" in "".join(lines), "run_index reports errors")

    target = os.path.join(root, ".vscode", "mcp.json")
    text, action = logic.mcp_preview(root, target, "")
    check(action == "added" and json.loads(text)["servers"]["mfcgraph"]["args"][-1] == root, "mcp preview", text)
    check(not os.path.exists(target), "preview writes nothing")
    msg = logic.mcp_write(root, target, "mfcgraph-billing")
    check(msg.startswith("Đã thêm: 'mfcgraph-billing'") and os.path.isfile(target), "mcp write", msg)
    msg = logic.mcp_write(root, target, "mfcgraph")
    check("Bản cũ lưu tại" in msg and len(json.loads(open(target).read())["servers"]) == 2, "second server + backup", msg)
    check(json.loads(logic.mcp_snippet(root, "x"))["servers"]["x"]["command"], "snippet")


def test_cli_without_tk():
    saved = sys.modules.get("tkinter", "missing")
    sys.modules["tkinter"] = None  # makes `import tkinter` raise ImportError
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            code = cli.main(["gui"])
    finally:
        if saved == "missing":
            del sys.modules["tkinter"]
        else:
            sys.modules["tkinter"] = saved
    check(code == 2 and "tcl/tk" in err.getvalue() and "works without it" in err.getvalue(),
          "gui without tkinter: clear message, exit 2", err.getvalue())


def test_isolation():
    code = ("import sys, io, contextlib; sys.path.insert(0, %r); from mfcgraph_core import cli, mcp, query, explore\n"
            "with contextlib.redirect_stdout(io.StringIO()): cli.main(['--help'])\n"
            "print(sorted(m for m in ('tkinter', 'mfcgraph_gui') if m in sys.modules))" % ROOT)
    out = subprocess.check_output([sys.executable, "-c", code]).decode().strip()
    check(out == "[]", "CLI/MCP never load tkinter or mfcgraph_gui", out)


def test_window(tmp):
    try:
        import tkinter as tk
        from mfcgraph_gui.app import App
        master = tk.Tk()
    except Exception as ex:  # no tkinter / no display: logic tests above still ran
        print("note: window smoke test skipped (%s)" % ex)
        return
    try:
        master.withdraw()
        root = os.path.join(tmp, "BigApp")
        app = App(master, root)
        master.update()
        check(app.root_var.get() == root and len(app.proj_list.get(0, "end")) == 2, "window loads saved form")
        check(app.config_var.get() == "Debug|Win32" and "Release|x64" in app.config_box["values"], "configs listed")
        check(app.target_var.get() == os.path.join(root, ".mcp.json"), "default MCP target = Visual Studio file")
        form = app.read_form()
        check(form.codepage == 932 and form.scope == "folders", "read_form", vars(form))
        app.copy_mcp()
        check('"servers"' in master.clipboard_get(), "copy puts the snippet on the clipboard")
        import time
        app.start_index()
        check(str(app.run_btn["state"]) == "disabled", "run button disabled while indexing")
        deadline = time.time() + 60
        while (app.worker is not None or not app.queue.empty()) and time.time() < deadline:
            master.update()
            time.sleep(0.02)
        master.update()
        log = app.log.get("1.0", "end")
        check("Indexed 47 files" in log and app.status_var.get() == "Xong.", "Run index from the window", log)
        check(str(app.run_btn["state"]) == "normal", "run button enabled again")
    finally:
        master.destroy()


def main():
    tmp = tempfile.mkdtemp(prefix="mfcgraph_gui_")
    try:
        test_logic(tmp)
        test_cli_without_tk()
        test_isolation()
        test_window(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("gui: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
