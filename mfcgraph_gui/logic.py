"""GUI logic without tkinter (unit-tested): form <-> settings, index run, MCP config preview/write.

Interface:
    Form(root="", projects=None, config="", scope="listed", codepage=1258, define="", undef="", exclude="")
    form_from_settings(root) -> Form          prefilled from <root>/.mfcgraph/settings.json when present
    solution_projects(sln_path) -> [(name, path)]
    project_configs(paths) -> [str]           union of the projects' configurations (sorted; unreadable ones skipped)
    common_root(paths) -> str                 deepest folder containing all given files
    index_argv(form) -> [str]                 the `index` command line the form stands for (shown in the log too)
    run_index(form, write) -> int             runs `cli.main(index_argv)`; every output line goes to write(text)
    mcp_preview(root, target, name) -> (text, action)   ValueError when the target is not plain JSON
    mcp_write(root, target, name) -> str      one-line result message (action + backup path)
    mcp_snippet(root, name) -> str
"""
import contextlib
import io
import os

from mfcgraph_core import cli, mcp_config, settings, vcxproj
from mfcgraph_core.index import index_path_for_root

CODEPAGES = ("1258", "932", "1252", "936", "949", "950", "65001")


class Form(object):
    def __init__(self, root="", projects=None, config="", scope="listed", codepage=1258, define="", undef="",
                 exclude=""):
        self.root = root
        self.projects = list(projects or [])
        self.config = config
        self.scope = scope
        self.codepage = codepage
        self.define = define
        self.undef = undef
        self.exclude = exclude


def form_from_settings(root):
    f = Form(root=root)
    s = settings.load(root) if root and os.path.isdir(root) else None
    if s is None:
        return f
    a = {}
    settings.apply(s, a, root)
    f.projects = [p for p in a["vcxproj"].split(";") if p]
    f.config = s["config"]
    f.scope = s["vcxproj_scope"] or "listed"
    f.codepage = s["codepage"]
    f.define, f.undef, f.exclude = s["define"], s["undef"], s["exclude"]
    return f


def solution_projects(sln_path):
    return vcxproj.read_solution(sln_path)


def project_configs(paths):
    out = set()
    for p in paths:
        try:
            out.update(vcxproj.read_project(p, lenient=True).configs)
        except ValueError:
            continue
    return sorted(out, key=lambda c: (not c.lower().startswith("release"), c.lower()))


def common_root(paths):
    dirs = [os.path.dirname(os.path.abspath(p)) for p in paths]
    if not dirs:
        return ""
    try:
        return os.path.commonpath(dirs)
    except ValueError:  # different drives
        return dirs[0]


def index_argv(form):
    if not form.root:
        raise ValueError("Chưa chọn thư mục gốc (root).")
    argv = ["index", form.root, "--codepage", str(form.codepage)]
    if form.projects:
        argv += ["--vcxproj", ";".join(form.projects)]
        if form.config:
            argv += ["--config", form.config]
        if form.scope and form.scope != "listed":
            argv += ["--vcxproj-scope", form.scope]
    for opt, val in (("--define", form.define), ("--undef", form.undef), ("--exclude", form.exclude)):
        if val.strip():
            argv += [opt, val.strip()]
    return argv


class _LineWriter(io.TextIOBase):
    def __init__(self, write):
        self._write = write

    def write(self, s):
        if s:
            self._write(s)
        return len(s)


def run_index(form, write):
    try:
        argv = index_argv(form)
    except ValueError as ex:
        write("error: %s\n" % ex)
        return 2
    write("> mfcgraph %s\n" % " ".join('"%s"' % x if (" " in x or ";" in x or "|" in x) else x for x in argv))
    stream = _LineWriter(write)
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            return cli.main(argv)
    except Exception as ex:  # the GUI must report, never die
        write("error: %s: %s\n" % (type(ex).__name__, ex))
        return 2


def has_index(root):
    return bool(root) and os.path.isfile(index_path_for_root(root))


def mcp_preview(root, target, name):
    old = None
    if os.path.exists(target):
        with io.open(target, encoding="utf-8-sig") as f:
            old = f.read()
    return mcp_config.merge(old, name or mcp_config.DEFAULT_NAME, mcp_config.server_entry(root))


def mcp_write(root, target, name):
    name = name or mcp_config.DEFAULT_NAME
    action, backup = mcp_config.write(target, name, mcp_config.server_entry(root))
    msg = "%s: '%s' trong %s" % ({"added": "Đã thêm", "updated": "Đã cập nhật", "unchanged": "Không đổi"}[action],
                                 name, target)
    if backup:
        msg += "\nBản cũ lưu tại: " + backup
    if action != "unchanged":
        msg += "\nKhởi động lại MCP server trong IDE (hoặc mở lại solution) để dùng."
    return msg


def mcp_snippet(root, name):
    return mcp_config.snippet(name or mcp_config.DEFAULT_NAME, mcp_config.server_entry(root))
