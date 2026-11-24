"""Command-line interface."""
import os
import sys
import time

from . import VERSION
from .index import build_index, save_graph, load_graph, index_path_for_root, find_index_upwards
from .query import (q_search, q_node, q_callers, q_callees, q_impact, q_trace, q_msgmap, q_context,
                    q_diagnose, q_status, q_refs)

USAGE = """mfcgraph %s - offline code graph for C++/MFC (no network, no telemetry)

Usage:
  python mfcgraph.py index <root>                     re-index with the settings saved by the last index
  python mfcgraph.py index <root> [--codepage 1258] [--exclude dir1;dir2] [-v]
                     [--define "A;B=1"] [--undef "C;D"] [--undef-unknown]   pick #ifdef/#else branches by macros
                     [--vcxproj "a.vcxproj;b.sln"] [--config "Release|Win32"] [--vcxproj-scope listed|folders]
                                                      defines + file list from Visual Studio projects
  python mfcgraph.py explore  <question | names | File.cpp:120 | ID | "error text"> [--budget N] [--scope DIR]
                                                      one call: relevant source + flow + impact (start here)
  python mfcgraph.py search   <text>                 classes, functions, IDs, menu/dialog captions
  python mfcgraph.py node     <symbol> [--no-code]   location, signature, flags, source
  python mfcgraph.py callers  <symbol> [--depth 5]   incl. message map -> menu/accelerator/toolbar
  python mfcgraph.py callees  <symbol> [--depth 2]
  python mfcgraph.py impact   <symbol> [--depth 5]   what is affected if this changes
  python mfcgraph.py trace    <menu text | ID_xxx | IDD_xxx> [--depth 2]
  python mfcgraph.py msgmap   <Class>
  python mfcgraph.py refs     <Class::m_field | m_field>   where a member variable is written / read
  python mfcgraph.py context  <symbol> [--lines 80]  Markdown context pack for an AI agent
  python mfcgraph.py diagnose [--show-names]         counts only, safe to share outside
  python mfcgraph.py status
  python mfcgraph.py serve                           MCP server on stdin/stdout (optional)
  python mfcgraph.py gui [--root R]                  optional window: guide, pick .vcxproj/.sln, index, MCP config
  python mfcgraph.py mcp-config [--root R] [--name mfcgraph] [--tools explore] [--write FILE]
                                                      print the MCP server entry; --write adds/updates it in FILE
                                                      (.mcp.json / .vscode/mcp.json), other servers kept, FILE.bak saved

Common options:
  --root <dir>    project root that contains .mfcgraph/ (default: search upward from cwd)
  --index <file>  explicit index file
""" % VERSION


def _parse(argv):
    a = {"pos": [], "root": "", "index": "", "exclude": "", "codepage": 1258, "depth": -1, "lines": 80,
         "no_code": False, "show_names": False, "verbose": False, "budget": 0, "scope": "", "define": "", "undef": "", "undef_unknown": False,
         "vcxproj": "", "config": "", "vcxproj_scope": "", "given": set(),
         "name": "", "write": "", "tools": ""}
    i = 0
    while i < len(argv):
        s = argv[i]
        if s.startswith("--"):
            a["given"].add(s)
        nxt = argv[i + 1] if i + 1 < len(argv) else ""
        if s in ("--root", "--index", "--exclude", "--scope", "--define", "--undef", "--vcxproj", "--config",
                 "--vcxproj-scope", "--name", "--write", "--tools"):
            a[s[2:].replace("-", "_")] = nxt
            i += 2
            continue
        if s in ("--codepage", "--depth", "--lines", "--budget"):
            try:
                a[s[2:]] = int(nxt)
            except ValueError:
                pass
            i += 2
            continue
        if s == "--no-code":
            a["no_code"] = True
        elif s == "--show-names":
            a["show_names"] = True
        elif s == "--undef-unknown":
            a["undef_unknown"] = True
        elif s in ("-v", "--verbose"):
            a["verbose"] = True
        else:
            a["pos"].append(s)
        i += 1
    return a


def _setup_stdout():
    # Make Vietnamese text print correctly on Windows consoles and when redirected.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _build(root, a, excludes):
    from .pp_eval import PPConfig, parse_defines, parse_names
    defines, undefs = parse_defines(a["define"]), parse_names(a["undef"])
    if not a["vcxproj"]:
        pp = PPConfig(defines, undefs, a["undef_unknown"])
        return build_index(root, a["codepage"], excludes, verbose=a["verbose"], pp=pp)
    from .vcxproj import expand_inputs, plan_index
    inputs = [x.strip() for x in a["vcxproj"].split(";") if x.strip()]
    projects = expand_inputs(inputs, a["config"] or None)
    if not projects:
        raise ValueError("no .vcxproj found in: " + a["vcxproj"])
    # A project build undefines every macro it does not declare: compiler semantics by default.
    plan = plan_index(root, projects, a["vcxproj_scope"] or "listed", defines, undefs, True, excludes)
    for line in plan.lines:
        print("  " + line)
    if not plan.files:
        raise ValueError("the projects list no source file under " + os.path.abspath(root))
    return build_index(root, a["codepage"], excludes, verbose=a["verbose"], pp=plan.pp, files=plan.files,
                       pp_by_file=plan.pp_by_file)


def _mcp_config(a):
    from . import mcp_config
    root = a["pos"][0] if a["pos"] else a["root"]
    if not root:
        found = find_index_upwards(os.getcwd())
        root = os.path.dirname(os.path.dirname(found)) if found else ""
    if not root or not os.path.isdir(root):
        sys.stderr.write("error: give the indexed project folder: mcp-config --root <dir>\n")
        return 2
    if not os.path.isfile(index_path_for_root(root)):
        sys.stderr.write("note: %s has no index yet; run 'index' before starting the IDE\n" % os.path.abspath(root))
    name = a["name"] or mcp_config.DEFAULT_NAME
    entry = mcp_config.server_entry(root, tools=a["tools"] or "explore")
    if not a["write"]:
        sys.stdout.write(mcp_config.snippet(name, entry))
        for label, path in mcp_config.suggest_targets(root):
            sys.stderr.write("  %s: %s\n" % (label, path))
        return 0
    try:
        action, backup = mcp_config.write(a["write"], name, entry)
    except (ValueError, OSError) as ex:
        sys.stderr.write("error: %s\n" % ex)
        return 2
    print("%s server '%s' in %s" % (action, name, os.path.abspath(a["write"])))
    if backup:
        print("previous content saved as " + backup)
    if action != "unchanged":
        print("Restart the MCP server in your IDE (or reopen the solution) to use it.")
    return 0


GUI_NO_TK = ("error: the GUI needs tkinter, which this Python installation does not have.\n"
             "  Fix: run the Python installer again > Modify > tick 'tcl/tk and IDLE' (no pip needed).\n"
             "  Everything else (index, explore, serve, mcp-config ...) works without it.\n")


def _gui(a):
    """Optional GUI: tkinter and mfcgraph_gui are imported only here, so a missing GUI never breaks the CLI."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.stderr.write(GUI_NO_TK)
        return 2
    try:
        from mfcgraph_gui.app import run
    except ImportError as ex:
        sys.stderr.write("error: GUI files missing or broken (mfcgraph_gui/): %s\n" % ex)
        return 2
    root = a["pos"][0] if a["pos"] else a["root"]
    try:
        return run(root)
    except tkinter.TclError as ex:
        sys.stderr.write("error: cannot open a window (%s)\n" % ex)
        return 2


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    _setup_stdout()
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 1
    cmd = argv[0]
    if cmd in ("version", "--version"):
        print("mfcgraph " + VERSION)
        return 0
    a = _parse(argv[1:])

    if cmd == "index":
        root = a["pos"][0] if a["pos"] else (a["root"] or ".")
        from . import settings
        if os.path.isdir(root) and not (a["given"] & set(settings.CONFIG_OPTIONS)):
            saved = settings.load(root)
            if saved is not None:
                settings.apply(saved, a, root)
                print("Using saved settings: " + settings.describe(saved))
        excludes = [x.strip() for x in a["exclude"].split(";") if x.strip()]
        t0 = time.time()
        try:
            g = _build(root, a, excludes)
        except ValueError as ex:
            sys.stderr.write("error: %s\n" % ex)
            return 2
        path = index_path_for_root(g.root)
        save_graph(g, path)
        settings.save(g.root, settings.from_args(a, g.root))
        st = g.stats
        print("Indexed %s files in %.2f s -> %s" % (st["files.total"], time.time() - t0, path))
        print("  classes %s, functions %s, message-map entries %s, dialogs %s, menu items %s" % (
            st["classes"], st["functions.defined"], st["msgmap.entries"], st["rc.dialogs"], st["rc.menu_items"]))
        print("Run 'mfcgraph diagnose' for quality numbers.")
        return 0

    if cmd == "mcp-config":
        return _mcp_config(a)
    if cmd == "gui":
        return _gui(a)

    if a["index"]:
        ipath = a["index"]
    elif a["root"]:
        ipath = index_path_for_root(a["root"])
    else:
        ipath = find_index_upwards(os.getcwd())
    if not ipath:
        sys.stderr.write("error: no .mfcgraph/index.mfg found. Run 'index <root>' or pass --root.\n")
        return 2
    if cmd == "serve":
        from .mcp import run_mcp_server  # MCP code is only loaded for this command
        return run_mcp_server(ipath)

    try:
        g = load_graph(ipath)
    except ValueError as ex:
        sys.stderr.write("error: %s\n" % ex)
        return 2
    rest = " ".join(a["pos"])
    depth = a["depth"]
    needs_arg = cmd in ("search", "node", "callers", "callees", "impact", "trace", "msgmap", "context", "refs", "explore")
    if needs_arg and not rest:
        sys.stderr.write("error: missing argument for '%s'\n" % cmd)
        return 1
    if cmd == "explore":
        from .explore import explore
        out = explore(g, rest, a["budget"] or None, a["scope"] or None)
    elif cmd == "search":
        out = q_search(g, rest, 40)
    elif cmd == "node":
        out = q_node(g, rest, not a["no_code"], a["lines"])
    elif cmd == "callers":
        out = q_callers(g, rest, depth if depth > 0 else 5)
    elif cmd == "callees":
        out = q_callees(g, rest, depth if depth > 0 else 2)
    elif cmd == "impact":
        out = q_impact(g, rest, depth if depth > 0 else 5)
    elif cmd == "trace":
        out = q_trace(g, rest, depth if depth > 0 else 2)
    elif cmd == "msgmap":
        out = q_msgmap(g, rest)
    elif cmd == "refs":
        out = q_refs(g, rest)
    elif cmd == "context":
        out = q_context(g, rest, a["lines"])
    elif cmd == "diagnose":
        out = q_diagnose(g, a["show_names"])
    elif cmd == "status":
        out = q_status(g, ipath)
    else:
        sys.stderr.write("unknown command: %s\n" % cmd)
        print(USAGE)
        return 1
    sys.stdout.write(out)
    return 0
