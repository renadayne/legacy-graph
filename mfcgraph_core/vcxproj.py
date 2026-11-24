"""Read Visual Studio project files (.vcxproj, imported .props, .sln) for indexing: defines and file lists.

Interface:
    read_project(path, config=None, solution_dir=None, lenient=False) -> Project
        Project.name, .path (abs), .configs ["Release|Win32", ...], .config (the one used), .defines {name: value},
        .undefs [names], .files [abs paths of ClCompile/ClInclude/ResourceCompile (+ None/Text with source extensions)],
        .notes [human-readable things that could not be evaluated; counts only, no code]
        config: "Release|x64" or just "Debug"; None picks Release|Win32, else the first Release*, else the first.
        Projects reached through a .sln are lenient (missing configuration -> default one, noted).
        Raises ValueError when the file cannot be read/parsed or `config` is not one of the project's configurations.
    read_solution(path) -> [(project_name, abs_vcxproj_path)]   (.vcxproj entries only, sorted by name)
    expand_inputs(paths, config=None) -> [Project]  .sln entries expand to all their .vcxproj
    plan_index(root, projects, scope="listed", defines=None, undefs=(), undef_unknown=True, excludes=())
        -> IndexPlan(files [abs paths under root, sorted], pp (default PPConfig), pp_by_file {abs path: PPConfig},
                     outside (files skipped: not under root), missing (listed but not on disk), lines [report])
        scope "listed": only files the projects list; "folders": every source file under each project's folder too.

MSBuild is evaluated only as far as indexing needs: properties in document order, conditions on $(Configuration) /
$(Platform) / known properties with == != and/or Exists(); unknown conditions count as true (noted). Implicit compiler
defines from project settings: CharacterSet, UseOfMfc, ConfigurationType=DynamicLibrary, RuntimeLibrary, platform.
Imports of Microsoft's own props ($(VCTargetsPath), $(UserRootDir), ...) are skipped. Local files only, no network
(xml.etree does not fetch external entities).
"""
import os
import re
import xml.etree.ElementTree as ET

from .index import CPP_EXTS, RC_EXTS, scan_tree
from .pp_eval import PPConfig

SOURCE_EXTS = CPP_EXTS | RC_EXTS
_FILE_ITEMS = ("ClCompile", "ClInclude", "ResourceCompile")
_EXTRA_ITEMS = ("None", "Text")  # .rc2 / .inl often listed here
_SKIP_IMPORT_PROPS = ("vctargetspath", "userrootdir", "msbuildextensionspath", "msbuildbinpath", "msbuildtoolspath",
                      "vsinstalldir", "programfiles", "windowssdkdir")
_MAX_IMPORT_DEPTH = 8
_PROP_REF = re.compile(r"\$\(([A-Za-z_][\w.]*)\)")
_CMP = re.compile(r"^'([^']*)'\s*(==|!=)\s*'([^']*)'$")
_EXISTS = re.compile(r"^(!)?\s*exists\s*\(\s*'([^']*)'\s*\)$", re.I)


class Project(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.configs = []
        self.config = ""
        self.defines = {}
        self.undefs = []
        self.files = []
        self.notes = []


class IndexPlan(object):
    def __init__(self):
        self.files = []
        self.pp = None
        self.pp_by_file = {}
        self.outside = 0
        self.missing = 0
        self.lines = []


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _is_ms_import(raw):
    low = raw.lower()
    return any("$(" + k in low for k in _SKIP_IMPORT_PROPS)


def _parse_xml(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        return ET.fromstring(data)
    except (OSError, ET.ParseError) as ex:
        raise ValueError("cannot read project file %s (%s)" % (path, ex))


def _list_configs(root):
    out = []
    for el in root.iter():
        if _local(el.tag) == "ProjectConfiguration":
            inc = el.get("Include", "")
            if inc and inc not in out:
                out.append(inc)
    return out


def pick_config(configs, wanted=None):
    """wanted "Release|x64" (exact) or "Debug" (first Debug|*); None -> Release|Win32, first Release*, first."""
    if wanted:
        low = wanted.lower()
        for c in configs:
            if c.lower() == low:
                return c
        for c in configs:
            if c.lower().split("|")[0] == low:
                return c
        if configs:
            raise ValueError("configuration %r not in project (has: %s)" % (wanted, ", ".join(configs)))
        return wanted
    for c in configs:
        if c.lower() == "release|win32":
            return c
    for c in configs:
        if c.lower().startswith("release"):
            return c
    return configs[0] if configs else "Release|Win32"


class _Evaluator(object):
    """Walks one project (and its imports) in document order, keeping properties and ClCompile settings."""

    def __init__(self, project, config, solution_dir):
        conf, _, plat = config.partition("|")
        proj_dir = os.path.dirname(project.path)
        self.p = project
        self.props = {"configuration": conf, "platform": plat or "Win32", "projectname": project.name,
                      "projectdir": proj_dir + os.sep, "msbuildprojectdirectory": proj_dir,
                      "msbuildprojectname": project.name}
        if solution_dir:
            self.props["solutiondir"] = os.path.abspath(solution_dir) + os.sep
        self.defines = []      # ordered list of "NAME" / "NAME=value"
        self.undefs = []
        self.runtime = ""
        self.files = []
        self.seen = set()
        self.p_root = None

    def note(self, text):
        if text not in self.p.notes:
            self.p.notes.append(text)

    def subst(self, text):
        def rep(m):
            v = self.props.get(m.group(1).lower())
            return m.group(0) if v is None else v
        return _PROP_REF.sub(rep, text or "")

    def cond(self, el, file_dir):
        c = el.get("Condition")
        if not c:
            return True
        r = self._eval_cond(self.subst(c).strip(), file_dir)
        if r is None:
            self.note("condition not evaluated (taken as true): " + c.strip()[:80])
            return True
        return r

    def _eval_cond(self, text, file_dir):
        while text.startswith("(") and text.endswith(")"):
            text = text[1:-1].strip()
        parts = re.split(r"\s+or\s+", text, flags=re.I)
        if len(parts) > 1:
            vals = [self._eval_cond(x, file_dir) for x in parts]
            return True if True in vals else (None if None in vals else False)
        parts = re.split(r"\s+and\s+", text, flags=re.I)
        if len(parts) > 1:
            vals = [self._eval_cond(x, file_dir) for x in parts]
            return False if False in vals else (None if None in vals else True)
        m = _CMP.match(text)
        if m:
            a, op, b = m.group(1), m.group(2), m.group(3)
            if "$(" in a or "$(" in b:
                return None
            same = a.strip().lower() == b.strip().lower()
            return same if op == "==" else not same
        m = _EXISTS.match(text)
        if m:
            if "$(" in m.group(2):
                return None
            found = os.path.exists(os.path.join(file_dir, m.group(2)))
            return (not found) if m.group(1) else found
        return None

    def walk_file(self, path, depth):
        key = os.path.normcase(os.path.abspath(path))
        if key in self.seen or depth > _MAX_IMPORT_DEPTH:
            return
        self.seen.add(key)
        root = self.p_root if depth == 0 else _parse_xml(path)
        saved = self.props.get("msbuildthisfiledirectory")
        file_dir = os.path.dirname(os.path.abspath(path))
        self.props["msbuildthisfiledirectory"] = file_dir + os.sep
        self.walk(root, file_dir, depth)
        if saved is not None:
            self.props["msbuildthisfiledirectory"] = saved

    def walk(self, el, file_dir, depth):
        for child in list(el):
            name = _local(child.tag)
            if name == "Import" and _is_ms_import(child.get("Project", "")):
                continue
            if not name or not self.cond(child, file_dir):
                continue
            if name == "PropertyGroup":
                for prop in list(child):
                    pname = _local(prop.tag)
                    if pname and self.cond(prop, file_dir):
                        self.props[pname.lower()] = self.subst((prop.text or "").strip())
            elif name == "ItemDefinitionGroup":
                for tool in list(child):
                    if _local(tool.tag) == "ClCompile" and self.cond(tool, file_dir):
                        self.cl_settings(tool, file_dir)
            elif name in ("ItemGroup", "ImportGroup", "Choose", "When", "Otherwise"):
                if name == "ItemGroup":
                    self.items(child, file_dir)
                else:
                    self.walk(child, file_dir, depth)
            elif name == "Import":
                self.do_import(child.get("Project", ""), file_dir, depth)

    def cl_settings(self, tool, file_dir):
        for s in list(tool):
            sname = _local(s.tag)
            if not self.cond(s, file_dir):
                continue
            if sname == "PreprocessorDefinitions":
                self.defines = self.merge_list(self.defines, s.text, "PreprocessorDefinitions")
            elif sname == "UndefinePreprocessorDefinitions":
                self.undefs = self.merge_list(self.undefs, s.text, "UndefinePreprocessorDefinitions")
            elif sname == "RuntimeLibrary":
                self.runtime = (s.text or "").strip()

    def merge_list(self, inherited, text, meta):
        out = []
        keep = False
        for part in self.subst(text or "").split(";"):
            part = part.strip()
            if not part:
                continue
            if part.lower() == "%(" + meta.lower() + ")":
                keep = True
                continue
            if "$(" in part or "%(" in part:
                self.note("define not evaluated (skipped): " + part[:60])
                continue
            out.append(part)
        return (list(inherited) + out) if keep else out

    def items(self, group, file_dir):
        for item in list(group):
            name = _local(item.tag)
            if name not in _FILE_ITEMS and name not in _EXTRA_ITEMS:
                continue
            if not self.cond(item, file_dir):
                continue
            for inc in self.subst(item.get("Include", "")).split(";"):
                inc = inc.strip()
                if not inc:
                    continue
                if "$(" in inc or "*" in inc or "?" in inc:
                    self.note("file item not evaluated (skipped): " + inc[:60])
                    continue
                if name in _EXTRA_ITEMS and os.path.splitext(inc)[1].lower() not in SOURCE_EXTS:
                    continue
                p = os.path.normpath(os.path.join(file_dir, inc.replace("\\", os.sep)))
                if p not in self.files:
                    self.files.append(p)

    def do_import(self, raw, file_dir, depth):
        path = self.subst(raw)
        if "$(" in path:
            self.note("import not resolved (skipped): " + raw[:80])
            return
        path = os.path.normpath(os.path.join(file_dir, path.replace("\\", os.sep)))
        if not os.path.isfile(path):
            self.note("import not found (skipped): " + raw[:80])
            return
        try:
            self.walk_file(path, depth + 1)
        except ValueError as ex:
            self.note(str(ex))

    def implicit_defines(self):
        out = []
        cs = self.props.get("characterset", "").lower()
        if cs == "unicode":
            out += ["UNICODE", "_UNICODE"]
        elif cs == "multibyte":
            out.append("_MBCS")
        if self.props.get("useofmfc", "").lower() == "dynamic":
            out.append("_AFXDLL")
        if self.props.get("configurationtype", "").lower() == "dynamiclibrary":
            out.append("_WINDLL")
        plat = self.props.get("platform", "").lower()
        if plat == "x64":
            out += ["_WIN64", "_M_X64"]
        elif plat == "win32":
            out.append("_M_IX86")
        rt = self.runtime.lower()
        if rt:
            out.append("_MT")
            if "debug" in rt:
                out.append("_DEBUG")
            if rt.endswith("dll"):
                out.append("_DLL")
        return out


def _nearest_solution_dir(project_path, levels=6):
    """$(SolutionDir) guess for a project opened on its own: the closest folder upward holding a .sln."""
    d = os.path.dirname(project_path)
    for _ in range(levels):
        try:
            if any(f.lower().endswith(".sln") for f in os.listdir(d)):
                return d
        except OSError:
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def read_project(path, config=None, solution_dir=None, lenient=False):
    """lenient: a configuration the project does not have falls back to the default one (noted) instead of failing."""
    p = Project(path)
    root = _parse_xml(p.path)
    p.configs = _list_configs(root)
    try:
        p.config = pick_config(p.configs, config)
    except ValueError:
        if not lenient:
            raise
        p.config = pick_config(p.configs)
        p.notes.append("configuration %s not in project, used %s" % (config, p.config))
    ev = _Evaluator(p, p.config, solution_dir or _nearest_solution_dir(p.path))
    ev.p_root = root
    ev.walk_file(p.path, 0)
    for d in ev.implicit_defines() + ev.defines:
        name, _, val = d.partition("=")
        p.defines[name.strip()] = val.strip() or "1"
    p.undefs = sorted(set(u.strip() for u in ev.undefs if u.strip()))
    for u in p.undefs:
        p.defines.pop(u, None)
    p.files = ev.files
    return p


_SLN_PROJECT = re.compile(r'^Project\("\{[^}]*\}"\)\s*=\s*"([^"]*)"\s*,\s*"([^"]*)"', re.M)


def read_solution(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as ex:
        raise ValueError("cannot read solution file %s (%s)" % (path, ex))
    text = data.decode("utf-8-sig", "replace")
    if "\x00" in text:
        text = data.decode("utf-16", "replace")
    base = os.path.dirname(os.path.abspath(path))
    out = []
    for name, rel in _SLN_PROJECT.findall(text):
        if rel.lower().endswith(".vcxproj"):
            out.append((name, os.path.normpath(os.path.join(base, rel.replace("\\", os.sep)))))
    return sorted(out, key=lambda x: (x[0].lower(), x[1]))


def expand_inputs(paths, config=None):
    """paths: .vcxproj and/or .sln files. A .sln gives all its projects (solution dir known for $(SolutionDir))."""
    out = []
    seen = set()
    for raw in paths:
        path = os.path.abspath(raw)
        if path.lower().endswith(".sln"):
            entries = [(e[1], os.path.dirname(path)) for e in read_solution(path)]
        else:
            entries = [(path, None)]
        for proj, sln_dir in entries:
            key = os.path.normcase(proj)
            if key in seen:
                continue
            seen.add(key)
            out.append(read_project(proj, config, sln_dir, lenient=sln_dir is not None))
    return out


def _under(path, root):
    rel = os.path.relpath(path, root)
    return not (rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel))


def plan_index(root, projects, scope="listed", defines=None, undefs=(), undef_unknown=True, excludes=()):
    if scope not in ("listed", "folders"):
        raise ValueError("--vcxproj-scope must be 'listed' or 'folders'")
    root = os.path.abspath(root)
    plan = IndexPlan()
    chosen = {}
    for proj in projects:
        d = dict(proj.defines)
        d.update(defines or {})
        u = set(proj.undefs) | set(undefs)
        pp = PPConfig(d, u, undef_unknown)
        if plan.pp is None:
            plan.pp = pp
        files = list(proj.files)
        if scope == "folders":
            files += sorted(scan_tree(os.path.dirname(proj.path), excludes))
        n_files = 0
        for f in files:
            key = os.path.normcase(os.path.abspath(f))
            if key in chosen:
                continue
            if not _under(f, root):
                plan.outside += 1
                continue
            if not os.path.isfile(f):
                plan.missing += 1
                continue
            chosen[key] = f
            plan.pp_by_file[os.path.abspath(f)] = pp
            n_files += 1
        plan.lines.append("project %s [%s]: %d files, %d defines%s" % (
            proj.name, proj.config, n_files, len(d), ("; %d note(s)" % len(proj.notes)) if proj.notes else ""))
        for note in proj.notes[:5]:
            plan.lines.append("  note: " + note)
        if len(proj.notes) > 5:
            plan.lines.append("  note: (+%d more)" % (len(proj.notes) - 5))
    if plan.pp is None:
        plan.pp = PPConfig(defines or {}, set(undefs), undef_unknown)
    plan.files = sorted(chosen.values(), key=lambda p: os.path.relpath(p, root).replace(os.sep, "/"))
    if plan.outside:
        plan.lines.append("skipped %d file(s) outside the root folder" % plan.outside)
    if plan.missing:
        plan.lines.append("skipped %d listed file(s) not found on disk" % plan.missing)
    return plan
