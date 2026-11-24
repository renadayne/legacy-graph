"""Visual Studio project reading (.vcxproj / .props / .sln) and `index --vcxproj`.

Run:  python3 tests/test_vcxproj.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mfcgraph_core import cli  # noqa: E402
from mfcgraph_core.index import load_graph, index_path_for_root  # noqa: E402
from mfcgraph_core.vcxproj import read_project, read_solution, expand_inputs, plan_index  # noqa: E402

BIGAPP = os.path.join(ROOT, "samples", "BigApp")
passed = 0
failed = 0

NS = "http://schemas.microsoft.com/developer/msbuild/2003"


def check(ok, what, detail=""):
    global passed, failed
    if ok:
        passed += 1
        return
    failed += 1
    print("FAIL: " + what + ("\n  " + str(detail) if detail else ""))


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)


def vcxproj(defines, files, extra=""):
    items = "\n".join('    <ClCompile Include="%s" />' % f for f in files)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<Project xmlns="%s">\n'
            '  <ItemGroup Label="ProjectConfigurations">\n'
            '    <ProjectConfiguration Include="Release|Win32" />\n    <ProjectConfiguration Include="Debug|Win32" />\n'
            '  </ItemGroup>\n%s\n'
            '  <ItemDefinitionGroup><ClCompile><PreprocessorDefinitions>%s;%%(PreprocessorDefinitions)'
            '</PreprocessorDefinitions></ClCompile></ItemDefinitionGroup>\n'
            '  <ItemGroup>\n%s\n  </ItemGroup>\n</Project>\n') % (NS, extra, defines, items)


def run_cli(args):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


def func_names(root):
    g = load_graph(index_path_for_root(root))
    return {(g.files[n.file].path, n.qname) for n in g.nodes if n.kind == "function" and "decl" not in n.flags}


def test_bigapp_project():
    path = os.path.join(BIGAPP, "BigApp.vcxproj")
    p = read_project(path)
    check(p.config == "Release|Win32", "default config Release|Win32", p.config)
    check(p.configs == ["Debug|Win32", "Release|Win32", "Release|x64"], "configs listed", p.configs)
    d = p.defines
    for name in ("WIN32", "_WINDOWS", "NDEBUG", "UNICODE", "_UNICODE", "_AFXDLL", "_MT", "_DLL", "_M_IX86"):
        check(name in d, "Release define " + name, sorted(d))
    check(d.get("BIGAPP_FEATURE_PDF") == "1", "define with value from imported .props", d.get("BIGAPP_FEATURE_PDF"))
    check("_DEBUG" not in d and "OUTDIR_NAME" not in d, "no _DEBUG, unresolved $(...) define skipped", sorted(d))
    check(p.undefs == ["BIGAPP_OLD_API"], "undefs from .props", p.undefs)
    check(any("OUTDIR_NAME" in n for n in p.notes), "unresolved define is noted", p.notes)
    check(not any("UserRootDir" in n for n in p.notes), "Microsoft imports skipped silently", p.notes)
    rels = sorted(os.path.relpath(f, BIGAPP).replace(os.sep, "/") for f in p.files)
    check(len(rels) == 33, "33 files listed", len(rels))
    check("res/BigApp.rc2" in rels and "ReadMe.txt" not in rels, "None items: sources only", rels)
    check("Billing/InvoiceDlg.cpp" not in rels, "other project's files not listed")

    dbg = read_project(path, "Debug")
    check(dbg.config == "Debug|Win32" and "_DEBUG" in dbg.defines and "NDEBUG" not in dbg.defines,
          "config by name only (Debug)", (dbg.config, sorted(dbg.defines)))
    x64 = read_project(path, "release|X64")
    check(x64.config == "Release|x64" and "_WIN64" in x64.defines and "WIN32" not in x64.defines,
          "x64 config (case-insensitive)", sorted(x64.defines))
    try:
        read_project(path, "Foo")
        check(False, "unknown configuration raises")
    except ValueError as ex:
        check("Release|x64" in str(ex), "error lists configurations", ex)


def test_solution():
    sln = os.path.join(BIGAPP, "BigApp.sln")
    entries = read_solution(sln)
    check([e[0] for e in entries] == ["BigApp", "Billing"], "sln lists .vcxproj only", entries)
    projects = expand_inputs([sln, os.path.join(BIGAPP, "Billing", "Billing.vcxproj")], "Release|x64")
    check(len(projects) == 2, "duplicate project given twice is read once", len(projects))
    bill = projects[1]
    check(bill.config == "Release|Win32" and any("not in project" in n for n in bill.notes),
          "sln project without the configuration falls back (noted)", (bill.config, bill.notes))
    for name in ("BILLING_LIB", "_MBCS", "BIGAPP_FEATURE_PDF"):
        check(name in bill.defines, "Billing define " + name, sorted(bill.defines))
    alone = read_project(os.path.join(BIGAPP, "Billing", "Billing.vcxproj"))
    check("BIGAPP_FEATURE_PDF" in alone.defines and not alone.notes,
          "$(SolutionDir) guessed from the nearest .sln upward", (sorted(alone.defines), alone.notes))

    plan = plan_index(BIGAPP, expand_inputs([sln]))
    check(len(plan.files) == 47, "plan: 47 files from the solution", len(plan.files))
    stdafx = os.path.join(BIGAPP, "stdafx.cpp")
    inv = os.path.join(BIGAPP, "Billing", "InvoiceDlg.cpp")
    check("BILLING_LIB" not in plan.pp_by_file[stdafx].defines, "shared file uses the first project listing it")
    check("BILLING_LIB" in plan.pp_by_file[inv].defines, "Billing file uses Billing defines")
    check(plan.pp_by_file[inv].undef_unknown, "undef-unknown on for project builds")


def test_conditions_and_errors(tmp):
    extra = ('  <PropertyGroup Condition="(\'$(Configuration)\'==\'Release\' and \'$(Platform)\'!=\'x64\') or '
             '\'$(Configuration)\'==\'Ship\'"><CharacterSet>MultiByte</CharacterSet></PropertyGroup>\n'
             '  <PropertyGroup Condition="exists(\'marker.txt\')"><UseOfMfc>Dynamic</UseOfMfc></PropertyGroup>\n'
             '  <PropertyGroup Condition="!exists(\'nothere.txt\')"><ConfigurationType>DynamicLibrary</ConfigurationType>'
             '</PropertyGroup>\n'
             '  <PropertyGroup Condition="\'$(Mystery)\'==\'1\'"><Foo>1</Foo></PropertyGroup>\n'
             '  <ImportGroup><Import Project="sub\\more.props" /><Import Project="missing.props" /></ImportGroup>\n')
    write(os.path.join(tmp, "marker.txt"), "x")
    write(os.path.join(tmp, "sub", "more.props"),
          '<Project xmlns="%s"><Import Project="..\\loop.props" /><ItemDefinitionGroup><ClCompile>'
          '<PreprocessorDefinitions>FROM_PROPS;%%(PreprocessorDefinitions)</PreprocessorDefinitions>'
          '</ClCompile></ItemDefinitionGroup></Project>' % NS)
    write(os.path.join(tmp, "loop.props"), '<Project xmlns="%s"><Import Project="sub\\more.props" /></Project>' % NS)
    write(os.path.join(tmp, "c.vcxproj"), vcxproj("OWN", ["a.cpp"], extra))
    p = read_project(os.path.join(tmp, "c.vcxproj"))
    d = p.defines
    check("_MBCS" in d and "_AFXDLL" in d and "_WINDLL" in d, "and/or/!=/exists/!exists conditions", sorted(d))
    check("FROM_PROPS" in d and "OWN" in d, "props define inherited via %(PreprocessorDefinitions)", sorted(d))
    check(any("Mystery" in n for n in p.notes), "unknown property condition noted", p.notes)
    check(any("missing.props" in n for n in p.notes), "missing import noted", p.notes)
    write(os.path.join(tmp, "bad.vcxproj"), "<Project><oops></Project>")
    try:
        read_project(os.path.join(tmp, "bad.vcxproj"))
        check(False, "broken XML raises ValueError")
    except ValueError:
        check(True, "")


def test_index_per_project(tmp):
    root = os.path.join(tmp, "app")
    body = "#ifdef FEATURE_A\nvoid OnA_%s() {}\n#else\nvoid OffA_%s() {}\n#endif\n"
    write(os.path.join(root, "A", "a.cpp"), body % ("a", "a"))
    write(os.path.join(root, "B", "b.cpp"), body % ("b", "b"))
    write(os.path.join(root, "B", "unlisted.cpp"), "void Unlisted() {}\n")
    write(os.path.join(tmp, "outside.cpp"), "void Outside() {}\n")
    write(os.path.join(root, "A", "a.vcxproj"), vcxproj("FEATURE_A", ["a.cpp", "gone.cpp", "..\\..\\outside.cpp"]))
    write(os.path.join(root, "B", "b.vcxproj"), vcxproj("OTHER", ["b.cpp"]))
    projs = "%s;%s" % (os.path.join(root, "A", "a.vcxproj"), os.path.join(root, "B", "b.vcxproj"))
    code, out, err = run_cli(["index", root, "--vcxproj", projs])
    check(code == 0, "index --vcxproj exit 0", err)
    check("project a [Release|Win32]: 1 files" in out and "outside the root" in out and "not found on disk" in out,
          "index prints the plan", out)
    names = func_names(root)
    check(("A/a.cpp", "OnA_a") in names and ("B/b.cpp", "OffA_b") in names, "#ifdef decided per project", names)
    check(not any(q in ("Unlisted", "Outside") for _, q in names), "only listed files under root", names)
    code, out, err = run_cli(["index", root, "--vcxproj", projs, "--vcxproj-scope", "folders"])
    check(code == 0 and ("B/unlisted.cpp", "Unlisted") in func_names(root), "--vcxproj-scope folders", (out, err))
    code, out, err = run_cli(["index", root, "--vcxproj", os.path.join(root, "B", "b.vcxproj"), "--define", "FEATURE_A"])
    check(("B/b.cpp", "OnA_b") in func_names(root), "--define adds to project defines", out)
    code, out, err = run_cli(["index", root, "--vcxproj", os.path.join(root, "B", "b.vcxproj"), "--config", "Nope"])
    check(code == 2 and "Nope" in err, "bad --config -> error exit 2", (code, err))


def main():
    tmp = tempfile.mkdtemp(prefix="mfcgraph_vcx_")
    try:
        test_bigapp_project()
        test_solution()
        test_conditions_and_errors(tmp)
        test_index_per_project(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("vcxproj: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
