"""Name resolution: raw facts -> graph with typed, confidence-tagged edges.

Confidence levels:
  exact     - qualified call, call through this/class scope, or receiver of known type
  likely    - only one function with that name exists in the codebase
  ambiguous - several candidates; one edge per candidate (max 6)
  heuristic - pattern based (SendMessage -> message handler)
  external  - target not in the indexed code (MFC, Win32, CRT, 3rd party)
"""
import re

from .extract_cpp import is_all_caps_ident
from .model import Node, Edge

FRAMEWORK_VIRTUALS = frozenset("""
InitInstance ExitInstance OnIdle Run PreTranslateMessage OnInitDialog DoDataExchange OnOK OnCancel OnDraw
OnInitialUpdate OnUpdate OnNewDocument OnOpenDocument OnSaveDocument OnCloseDocument DeleteContents Serialize
PreCreateWindow OnCreateClient OnCmdMsg WindowProc DefWindowProc OnCommand OnNotify OnChildNotify PostNcDestroy
OnPrepareDC OnPreparePrinting OnBeginPrinting OnEndPrinting OnPrint OnActivateView OnSetActive OnKillActive
OnApply OnWizardNext OnWizardBack OnWizardFinish DrawItem MeasureItem CompareItem DeleteItem AssertValid Dump
PreSubclassWindow OnToolHitTest OnAmbientProperty ContinueModal OnFileNew OnFileOpen SaveModified OnDragEnter
OnDragOver OnDrop OnScroll OnScrollBy CreateDocument OnUpdateFrameTitle LoadFrame RecalcLayout OnShowViewMenu
OnHelpInfo OnWndMsg OnDestroy""".split())


def last_component(q):
    p = q.rfind("::")
    return q if p < 0 else q[p + 2:]


def add_flag(n, f):
    if not n.flags:
        n.flags = f
    elif f not in n.flags.split(","):
        n.flags += "," + f


def parse_int(v):
    s = v.strip()
    while s.startswith("(") and s.endswith(")") and len(s) >= 2:
        s = s[1:-1].strip()
    if not s:
        return None
    try:
        return int(s, 0)
    except ValueError:
        if re.fullmatch(r"[+-]?0[0-7]+", s):
            return int(s, 8)
        return None


class Resolver:
    def __init__(self, raw, g):
        self.r = raw
        self.g = g
        self.file_node = []
        self.class_by_name = {}
        self.bases = {}
        self.methods = {}        # class -> {name: [fn]}
        self.free_by_name = {}
        self.method_by_name = {}
        self.ext = {}
        self.ids = {}
        self.dialogs = {}
        self.msg_ids = set()
        self.fields = {}
        self.edge_seen = set()
        self.conf_count = {}
        self.func_node = {}
        self.handlers_total = self.handlers_resolved = self.handlers_framework = 0
        self.includes_total = self.includes_resolved = 0
        self._anc_cache = {}

    def run(self):
        self.g.files = self.r.files
        self.make_file_nodes()
        self.make_classes()
        self.make_functions()
        self.make_inheritance()
        self.make_overrides()
        self.make_ids()
        self.make_msgmaps()
        self.make_resources()
        self.make_calls()
        self.make_includes()
        self.compute_stats()

    # ---- primitives ----
    def add_node(self, n):
        n.id = len(self.g.nodes)
        self.g.nodes.append(n)
        return n.id

    def add_edge(self, s, d, kind, file, line, conf, extra=""):
        key = (s, d, kind + "|" + extra)
        if key in self.edge_seen:
            return
        self.edge_seen.add(key)
        self.g.edges.append(Edge(s, d, kind, file, line, conf, extra))

    def external(self, name, hint=""):
        x = self.ext.get(name)
        if x is not None:
            return x
        n = Node("external", last_component(name), name)
        n.extra = hint
        x = self.add_node(n)
        self.ext[name] = x
        return x

    def id_node(self, name):
        x = self.ids.get(name)
        if x is not None:
            return x
        x = self.add_node(Node("id", name, name))
        self.ids[name] = x
        return x

    def count(self, conf):
        self.conf_count[conf] = self.conf_count.get(conf, 0) + 1

    # ---- classes & functions ----
    def make_file_nodes(self):
        for i, f in enumerate(self.r.files):
            n = Node("file", f.path, f.path)
            n.file = i
            n.line = 1
            n.end = f.lines
            self.file_node.append(self.add_node(n))

    def find_class(self, name):
        lst = self.class_by_name.get(last_component(name))
        if not lst:
            return -1
        if len(lst) > 1 and "::" in name:
            for c in lst:
                if self.g.nodes[c].qname.endswith(name):
                    return c
        return lst[0]

    def make_classes(self):
        for c in self.r.classes:
            n = Node("class", last_component(c.name), c.name if not c.ns else c.ns + "::" + c.name)
            n.file = c.file
            n.line = c.line
            n.end = c.end or c.line
            n.extra = "" if not c.bases else "bases: " + ", ".join(c.bases)
            if c.idd:
                n.extra += ("" if not n.extra else "; ") + "IDD=" + c.idd
            x = self.add_node(n)
            self.class_by_name.setdefault(n.name, []).append(x)
            self.bases[x] = list(c.bases)
            self.fields[x] = c.fields
        for (file, macro, cls, base, line) in self.r.dynamics:
            c = self.find_class(cls)
            if c < 0:
                n = Node("class", last_component(cls), cls)
                n.file = file
                n.line = line
                n.end = line
                n.extra = "bases: %s (from %s)" % (base, macro)
                c = self.add_node(n)
                self.class_by_name.setdefault(n.name, []).append(c)
            if not self.bases.get(c):
                self.bases[c] = [base]

    def make_functions(self):
        defined = set()
        for pass_ in (0, 1):
            for fi, f in enumerate(self.r.funcs):
                if (pass_ == 0) != f.is_def:
                    continue
                owner = self.find_class(f.cls) if f.cls else -1
                if pass_ == 1 and (owner, f.name) in defined:
                    continue
                n = Node("function", f.name)
                if owner >= 0:
                    n.qname = self.g.nodes[owner].qname + "::" + f.name
                else:
                    q = f.ns if not f.cls else (f.cls if not f.ns else f.ns + "::" + f.cls)
                    n.qname = f.name if not q else q + "::" + f.name
                n.file = f.file
                n.line = f.line
                n.end = f.end
                n.owner = owner
                n.sig = f.sig
                if f.is_virtual:
                    add_flag(n, "virtual")
                if not f.is_def:
                    add_flag(n, "decl")
                x = self.add_node(n)
                self.func_node[fi] = x
                if owner >= 0:
                    self.methods.setdefault(owner, {}).setdefault(f.name, []).append(x)
                    self.method_by_name.setdefault(f.name, []).append(x)
                    if pass_ == 0:
                        defined.add((owner, f.name))
                else:
                    self.free_by_name.setdefault(f.name, []).append(x)

    def ancestors(self, cls):
        """Returns (known ancestor class ids, external base names) in BFS order."""
        cached = self._anc_cache.get(cls)
        if cached is not None:
            return cached
        seen = {cls}
        queue = [cls]
        known, ext, ext_seen = [], [], set()
        qi = 0
        while qi < len(queue):
            for b in self.bases.get(queue[qi], ()):
                bc = self.find_class(b)
                if bc >= 0:
                    if bc not in seen:
                        seen.add(bc)
                        known.append(bc)
                        queue.append(bc)
                elif b not in ext_seen:
                    ext_seen.add(b)
                    ext.append(b)
            qi += 1
        self._anc_cache[cls] = (known, ext)
        return known, ext

    def find_method(self, cls, name, search_bases=True):
        m = self.methods.get(cls)
        if m and name in m:
            return m[name]
        if not search_bases:
            return []
        for a in self.ancestors(cls)[0]:
            r = self.find_method(a, name, False)
            if r:
                return r
        return []

    def first_external_base(self, cls):
        ext = self.ancestors(cls)[1]
        return ext[0] if ext else ""

    def make_inheritance(self):
        for cid, bl in self.bases.items():
            n = self.g.nodes[cid]
            for b in bl:
                bc = self.find_class(b)
                if bc >= 0:
                    self.add_edge(cid, bc, "inherits", n.file, n.line, "exact")
                else:
                    self.add_edge(cid, self.external(b, "class"), "inherits", n.file, n.line, "external")

    def make_overrides(self):
        nodes = self.g.nodes
        for cid, by_name in self.methods.items():
            known, ext = self.ancestors(cid)
            for name, fns in by_name.items():
                found = False
                for a in known:
                    r = self.find_method(a, name, False)
                    if r:
                        for fn in fns:
                            self.add_edge(fn, r[0], "overrides", nodes[fn].file, nodes[fn].line, "exact")
                        found = True
                        break
                if ext and name in FRAMEWORK_VIRTUALS:
                    for fn in fns:
                        add_flag(nodes[fn], "framework-entry")
                        if not found:
                            self.add_edge(fn, self.external(ext[0] + "::" + name, "framework"), "overrides",
                                          nodes[fn].file, nodes[fn].line, "external")

    # ---- ids, message maps, resources ----
    def make_ids(self):
        for (file, nm, value, line) in self.r.defines:
            resource_like = nm.startswith("ID") and len(nm) > 3 and "_" in nm and is_all_caps_ident(nm)
            msg_like = nm.startswith("WM_") or nm.startswith("UWM_") or "_MSG" in nm
            if not resource_like and not msg_like:
                continue
            n = self.g.nodes[self.id_node(nm)]
            if n.file < 0:
                n.file = file
                n.line = line
                n.extra = "value=" + value
        for (file, sid, text, line) in self.r.strings:
            n = self.g.nodes[self.id_node(sid)]
            n.extra += ("" if not n.extra else "; ") + 'text="' + text + '"'
            if n.file < 0:
                n.file = file
                n.line = line

    def value_of(self, idn):
        x = self.g.nodes[idn].extra
        if not x.startswith("value="):
            return ""
        semi = x.find(";")
        return x[6:] if semi < 0 else x[6:semi]

    def make_msgmaps(self):
        nodes = self.g.nodes
        for mm in self.r.msgmaps:
            cls = self.find_class(mm.cls)
            for e in mm.entries:
                self.handlers_total += 1
                hname = last_component(e.handler)
                hqual = e.handler[:len(e.handler) - len(hname) - 2] if len(e.handler) > len(hname) else ""
                hcls = cls
                extra = e.macro + "@" + mm.cls
                if hqual:
                    q = self.find_class(hqual)
                    if q < 0:  # implemented by an MFC base class, e.g. &CWinApp::OnFileNew
                        self.handlers_framework += 1
                        x = self.external(hqual + "::" + hname, "framework-handler")
                        self.add_edge(self.id_node(e.id), x, "handled_by", mm.file, e.line, "external", extra)
                        if e.id2:
                            self.add_edge(self.id_node(e.id2), x, "handled_by", mm.file, e.line, "external", extra)
                        continue
                    hcls = q
                h = self.find_method(hcls, hname) if hcls >= 0 else []
                if not h and hcls < 0:
                    cand = self.method_by_name.get(hname, [])
                    if len(cand) == 1:
                        h = cand
                if e.kind == "message":
                    self.msg_ids.add(e.id)
                idnames = [e.id]
                if e.id2:
                    idnames.append(e.id2)
                    a, b = self.ids.get(e.id), self.ids.get(e.id2)
                    if a is not None and b is not None:
                        lo, hi = parse_int(self.value_of(a)), parse_int(self.value_of(b))
                        if lo is not None and hi is not None:
                            for nm, idx in self.ids.items():
                                v = parse_int(self.value_of(idx))
                                if v is not None and lo < v < hi:
                                    idnames.append(nm)
                if not h:
                    x = self.external(mm.cls + "::" + hname, "unresolved-handler")
                    for idn in idnames:
                        self.add_edge(self.id_node(idn), x, "handled_by", mm.file, e.line, "external", extra)
                    continue
                self.handlers_resolved += 1
                for fn in h:
                    add_flag(nodes[fn], "update-ui-handler" if e.kind == "update_ui" else "msg-handler")
                    for idn in idnames:
                        self.add_edge(self.id_node(idn), fn, "handled_by", mm.file, e.line, "exact", extra)

    def make_resources(self):
        for d in self.r.dialogs:
            n = Node("dialog", d["id"], d["id"])
            n.file = d["file"]
            n.line = d["line"]
            n.extra = "" if not d["caption"] else 'caption="' + d["caption"] + '"'
            dn = self.add_node(n)
            self.dialogs[d["id"]] = dn
            for (ctype, text, cid, cline) in d["controls"]:
                if cid in ("IDC_STATIC", "-1"):
                    continue
                extra = ctype + ("" if not text else ' "' + text + '"')
                self.add_edge(dn, self.id_node(cid), "contains", d["file"], cline, "exact", extra)
        for u in self.r.uiitems:
            if u["kind"] == "menu":
                name = "Menu %s: %s" % (u["owner"], u["label"])
            elif u["kind"] == "accel":
                name = "Accelerator " + u["label"]
            else:
                name = "Toolbar %s %s" % (u["owner"], u["label"])
            n = Node("ui", name, name)
            n.file = u["file"]
            n.line = u["line"]
            n.extra = u["kind"]
            un = self.add_node(n)
            self.add_edge(un, self.id_node(u["id"]), "triggers", u["file"], u["line"], "exact")
        for lst in self.class_by_name.values():
            for c in lst:
                ex = self.g.nodes[c].extra
                p = ex.find("IDD=")
                if p < 0:
                    continue
                idd = ex[p + 4:]
                target = self.dialogs.get(idd)
                if target is None:
                    target = self.id_node(idd)
                self.add_edge(c, target, "uses_dialog", self.g.nodes[c].file, self.g.nodes[c].line, "exact")

    # ---- calls ----
    def receiver_class(self, f, owner, recv):
        if not recv:
            return -1
        if recv in f.locals:
            return self.find_class(f.locals[recv])
        if owner < 0:
            return -1
        for c in [owner] + self.ancestors(owner)[0]:
            fm = self.fields.get(c)
            if fm and recv in fm:
                return self.find_class(fm[recv])
        return -1

    def receiver_type_name(self, f, owner, recv):
        if recv in f.locals:
            return f.locals[recv]
        if owner < 0:
            return ""
        return self.fields.get(owner, {}).get(recv, "")

    def return_class_of(self, fn, owner):
        cands = self.find_method(owner, fn) if owner >= 0 else []
        if not cands:
            fr = self.free_by_name.get(fn, [])
            if len(fr) == 1:
                cands = fr
        if not cands:
            return -1
        sig = self.g.nodes[cands[0]].sig
        pos = sig.find(fn + "(")
        if pos < 0:
            pos = sig.find(fn + " (")
        if pos < 0:
            return -1
        ret = sig[:pos]
        while True:  # drop trailing "Class::" qualifiers
            t = ret.strip()
            if not t.endswith("::"):
                break
            t = t[:-2]
            b = len(t)
            while b > 0 and (t[b - 1].isascii() and (t[b - 1].isalnum() or t[b - 1] == "_")):
                b -= 1
            ret = t[:b]
        for word in re.findall(r"[A-Za-z0-9_]+", ret):
            c = self.find_class(word)
            if c >= 0:
                return c
        return -1

    def link(self, src, targets, conf, file, line):
        if len(targets) == 1:
            self.add_edge(src, targets[0], "calls", file, line, conf)
            self.count(conf)
            return
        for t in targets[:6]:
            self.add_edge(src, t, "calls", file, line, "ambiguous")
        self.count("ambiguous")

    def ext_call(self, src, name, file, line):
        self.add_edge(src, self.external(name), "calls", file, line, "external")
        self.count("external")

    def make_calls(self):
        nodes = self.g.nodes
        for fi, f in enumerate(self.r.funcs):
            if not f.is_def:
                continue
            src = self.func_node.get(fi)
            if src is None:
                continue
            owner = nodes[src].owner
            for c in f.calls:
                if c.qual and c.qual != "::":
                    qc = self.find_class(c.qual)
                    if qc >= 0:
                        m = self.find_method(qc, c.name)
                        if m:
                            self.link(src, m, "exact", f.file, c.line)
                            continue
                        eb = self.first_external_base(qc)
                        self.ext_call(src, (eb or c.qual) + "::" + c.name, f.file, c.line)
                        continue
                    suffix = c.qual + "::" + c.name
                    exact = [fn for fn in self.free_by_name.get(c.name, []) if nodes[fn].qname.endswith(suffix)]
                    if exact:
                        self.link(src, exact, "exact", f.file, c.line)
                        continue
                    self.ext_call(src, suffix, f.file, c.line)
                    continue
                if c.qual == "::":
                    fr = self.free_by_name.get(c.name, [])
                    if fr:
                        self.link(src, fr, "likely" if len(fr) == 1 else "ambiguous", f.file, c.line)
                        continue
                    self.ext_call(src, "::" + c.name, f.file, c.line)
                    continue
                if c.member:
                    if c.recv == "this":
                        rc = owner
                    elif c.recv_type:
                        rc = self.find_class(c.recv_type)
                    elif c.recv_call:
                        rc = self.return_class_of(c.recv_call, owner)
                    else:
                        rc = self.receiver_class(f, owner, c.recv)
                    if rc >= 0:
                        m = self.find_method(rc, c.name)
                        if m:
                            self.link(src, m, "exact", f.file, c.line)
                            continue
                        eb = self.first_external_base(rc)
                        self.ext_call(src, (eb or nodes[rc].name) + "::" + c.name, f.file, c.line)
                        continue
                    if c.recv_type:
                        tname = c.recv_type
                    elif c.recv:
                        tname = self.receiver_type_name(f, owner, c.recv)
                    else:
                        tname = ""
                    if tname:
                        self.ext_call(src, tname + "::" + c.name, f.file, c.line)
                        continue
                    mb = self.method_by_name.get(c.name, [])
                    if mb:
                        self.link(src, mb, "likely" if len(mb) == 1 else "ambiguous", f.file, c.line)
                        continue
                    self.ext_call(src, "?::" + c.name, f.file, c.line)
                    continue
                if owner >= 0:
                    m = self.find_method(owner, c.name)
                    if m:
                        self.link(src, m, "exact", f.file, c.line)
                        continue
                fr = self.free_by_name.get(c.name, [])
                if fr:
                    same = [fn for fn in fr if f.ns and nodes[fn].qname.startswith(f.ns + "::")]
                    if same:
                        self.link(src, same, "exact" if len(same) == 1 else "ambiguous", f.file, c.line)
                    else:
                        self.link(src, fr, "likely" if len(fr) == 1 else "ambiguous", f.file, c.line)
                    continue
                global_like = c.name.startswith("Afx") or c.name[0] == "_" or c.name[0].islower()
                eb = self.first_external_base(owner) if (owner >= 0 and not global_like) else ""
                self.ext_call(src, (eb + "::" + c.name) if eb else c.name, f.file, c.line)
            for (rcls, line) in f.runtime:
                c = self.find_class(rcls)
                self.add_edge(src, c if c >= 0 else self.external(rcls, "class"), "runtime_class", f.file, line,
                              "exact" if c >= 0 else "external")
            for (api, caps, line) in f.sends:
                for cap in caps:
                    if cap in self.msg_ids or cap.startswith("WM_") or cap in self.ids:
                        self.add_edge(src, self.id_node(cap), "sends", f.file, line, "heuristic", api)
                        break
            if f.ddx and owner >= 0:
                for (macro, did, member, line) in f.ddx:
                    self.add_edge(owner, self.id_node(did), "binds", f.file, line, "exact", macro + " " + member)

    def make_includes(self):
        by_base = {}
        files = self.r.files
        for i, f in enumerate(files):
            p = f.path.lower()
            by_base.setdefault(p.rsplit("/", 1)[-1], []).append(i)
        for (file, target, line) in self.r.includes:
            self.includes_total += 1
            t = target.replace("\\", "/").lower()
            cands = by_base.get(t.rsplit("/", 1)[-1])
            if not cands:
                continue
            frm = files[file].path.lower()
            d = frm[:frm.rfind("/") + 1] if "/" in frm else ""
            best = -1
            for cand in cands:
                cp = files[cand].path.lower()
                if cp == d + t:
                    best = cand
                    break
                if best < 0 and cp.endswith(t):
                    best = cand
            if best < 0:
                best = cands[0]
            self.includes_resolved += 1
            self.add_edge(self.file_node[file], self.file_node[best], "includes", file, line, "exact")

    def compute_stats(self):
        s = self.g.stats
        cpp = hdr = rc = brace = 0
        skipped = 0
        enc = {}
        for f in self.r.files:
            p = f.path.lower()
            if p.endswith((".rc", ".rc2", ".dlg")):
                rc += 1
            elif p.endswith((".h", ".hpp", ".hxx", ".hh", ".inl")):
                hdr += 1
            else:
                cpp += 1
            if f.brace_error:
                brace += 1
            skipped += f.skipped_tokens
            enc[f.encoding] = enc.get(f.encoding, 0) + 1
        s["files.total"] = str(len(self.r.files))
        s["files.source"] = str(cpp)
        s["files.header"] = str(hdr)
        s["files.resource"] = str(rc)
        s["files.brace_error"] = str(brace)
        s["tokens.inactive_skipped"] = str(skipped)
        for k in sorted(enc):
            s["encoding." + k] = str(enc[k])
        classes = defs = decls = fw = handlers = 0
        for n in self.g.nodes:
            if n.kind == "class":
                classes += 1
            elif n.kind == "function":
                fl = n.flags.split(",")
                if "decl" in fl:
                    decls += 1
                else:
                    defs += 1
                if "framework-entry" in fl:
                    fw += 1
                if "msg-handler" in fl:
                    handlers += 1
        s["classes"] = str(classes)
        s["functions.defined"] = str(defs)
        s["functions.decl_only"] = str(decls)
        s["functions.framework_entry"] = str(fw)
        s["functions.msg_handler"] = str(handlers)
        s["calls.total"] = str(sum(self.conf_count.values()))
        for k in sorted(self.conf_count):
            s["calls." + k] = str(self.conf_count[k])
        s["msgmap.entries"] = str(self.handlers_total)
        s["msgmap.resolved"] = str(self.handlers_resolved)
        s["msgmap.framework"] = str(self.handlers_framework)
        s["msgmap.unresolved"] = str(self.handlers_total - self.handlers_resolved - self.handlers_framework)
        um = self.r.unknown_macros
        s["msgmap.unknown_macros"] = str(sum(um.values()))
        s["msgmap.unknown_macro_kinds"] = str(len(um))
        s["msgmap.unknown_macro_names"] = ",".join("%s=%d" % (k, um[k]) for k in sorted(um))
        menu = sum(1 for u in self.r.uiitems if u["kind"] == "menu")
        accel = sum(1 for u in self.r.uiitems if u["kind"] == "accel")
        s["rc.dialogs"] = str(len(self.r.dialogs))
        s["rc.menu_items"] = str(menu)
        s["rc.accelerators"] = str(accel)
        s["rc.toolbar_buttons"] = str(len(self.r.uiitems) - menu - accel)
        s["rc.strings"] = str(len(self.r.strings))
        s["includes.total"] = str(self.includes_total)
        s["includes.resolved"] = str(self.includes_resolved)
        s["nodes"] = str(len(self.g.nodes))
        s["edges"] = str(len(self.g.edges))


def resolve(raw, g):
    Resolver(raw, g).run()
    g.build_adjacency()
