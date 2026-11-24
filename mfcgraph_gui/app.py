"""mfcgraph GUI window (tkinter). Start with `python mfcgraph.py gui [--root DIR]`.

Tabs: "Hướng dẫn" (guide.GUIDE) and "Index" (project choice, options, run index in a worker thread with a live log,
then write / copy the MCP server entry). All work is done by logic.py; this file only builds widgets.
Interface: run(root="") -> int (exit code), App(master, root="")
"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from mfcgraph_core import VERSION, mcp_config

from . import logic
from .guide import GUIDE

PAD = {"padx": 6, "pady": 3}


class App(object):
    def __init__(self, master, root=""):
        self.master = master
        self.queue = queue.Queue()
        self.worker = None
        master.title("mfcgraph %s" % VERSION)
        master.minsize(760, 560)
        nb = ttk.Notebook(master)
        nb.pack(fill="both", expand=True)
        nb.add(self._guide_tab(nb), text="Hướng dẫn")
        main = self._index_tab(nb)
        nb.add(main, text="Index")
        self.load_form(logic.form_from_settings(root) if root else logic.Form())
        if root:
            nb.select(main)
        master.after(100, self._poll)

    # ---- widgets -------------------------------------------------------------------------------------------
    def _guide_tab(self, nb):
        frame = ttk.Frame(nb)
        txt = ScrolledText(frame, wrap="word", font=("Consolas", 10))
        txt.insert("1.0", GUIDE)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=4, pady=4)
        return frame

    def _index_tab(self, nb):
        f = ttk.Frame(nb)
        f.columnconfigure(1, weight=1)
        self.root_var = tk.StringVar()
        ttk.Label(f, text="Thư mục gốc (root):").grid(row=0, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.root_var).grid(row=0, column=1, sticky="ew", **PAD)
        ttk.Button(f, text="Chọn...", command=self.pick_root).grid(row=0, column=2, sticky="ew", **PAD)

        ttk.Label(f, text="Project (.vcxproj):").grid(row=1, column=0, sticky="nw", **PAD)
        self.proj_list = tk.Listbox(f, height=5, selectmode="extended")
        self.proj_list.grid(row=1, column=1, sticky="nsew", **PAD)
        btns = ttk.Frame(f)
        btns.grid(row=1, column=2, sticky="n", **PAD)
        ttk.Button(btns, text="Thêm .vcxproj...", command=self.add_vcxproj).pack(fill="x", pady=1)
        ttk.Button(btns, text="Thêm từ .sln...", command=self.add_from_sln).pack(fill="x", pady=1)
        ttk.Button(btns, text="Bỏ chọn", command=self.remove_projects).pack(fill="x", pady=1)

        opts = ttk.Frame(f)
        opts.grid(row=2, column=0, columnspan=3, sticky="ew", **PAD)
        self.config_var = tk.StringVar()
        self.scope_var = tk.StringVar(value="listed")
        self.codepage_var = tk.StringVar(value="1258")
        ttk.Label(opts, text="Cấu hình build:").grid(row=0, column=0, sticky="w")
        self.config_box = ttk.Combobox(opts, textvariable=self.config_var, width=22)
        self.config_box.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(opts, text="Phạm vi:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Combobox(opts, textvariable=self.scope_var, values=("listed", "folders"), width=9,
                     state="readonly").grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(opts, text="Codepage:").grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Combobox(opts, textvariable=self.codepage_var, values=logic.CODEPAGES, width=7).grid(
            row=0, column=5, sticky="w", padx=4)

        self.define_var, self.undef_var, self.exclude_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for i, (label, var) in enumerate((("Define thêm (A;B=1):", self.define_var), ("Undef (C;D):", self.undef_var),
                                          ("Bỏ thư mục (x;y):", self.exclude_var))):
            ttk.Label(f, text=label).grid(row=3 + i, column=0, sticky="w", **PAD)
            ttk.Entry(f, textvariable=var).grid(row=3 + i, column=1, columnspan=2, sticky="ew", **PAD)

        run = ttk.Frame(f)
        run.grid(row=6, column=0, columnspan=3, sticky="ew", **PAD)
        self.run_btn = ttk.Button(run, text="▶ Chạy index", command=self.start_index)
        self.run_btn.pack(side="left")
        self.progress = ttk.Progressbar(run, mode="determinate", length=180, value=0)
        self.progress.pack(side="left", padx=8)
        self.status_var = tk.StringVar()
        ttk.Label(run, textvariable=self.status_var).pack(side="left")

        self.log = ScrolledText(f, height=10, wrap="word", font=("Consolas", 9), state="disabled")
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew", **PAD)
        f.rowconfigure(7, weight=1)
        self._mcp_frame(f).grid(row=8, column=0, columnspan=3, sticky="ew", **PAD)
        return f

    def _mcp_frame(self, parent):
        box = ttk.LabelFrame(parent, text="Kết nối Copilot (MCP) — chỉ ghi khi bạn bấm nút")
        box.columnconfigure(1, weight=1)
        self.name_var = tk.StringVar(value=mcp_config.DEFAULT_NAME)
        self.target_var = tk.StringVar()
        ttk.Label(box, text="Tên server:").grid(row=0, column=0, sticky="w", **PAD)
        ttk.Entry(box, textvariable=self.name_var, width=24).grid(row=0, column=1, sticky="w", **PAD)
        ttk.Label(box, text="File đích:").grid(row=1, column=0, sticky="w", **PAD)
        self.target_box = ttk.Combobox(box, textvariable=self.target_var)
        self.target_box.grid(row=1, column=1, sticky="ew", **PAD)
        ttk.Button(box, text="Chọn...", command=self.pick_target).grid(row=1, column=2, **PAD)
        row = ttk.Frame(box)
        row.grid(row=2, column=0, columnspan=3, sticky="w", **PAD)
        ttk.Button(row, text="Xem trước & ghi vào mcp.json...", command=self.preview_mcp).pack(side="left")
        ttk.Button(row, text="Copy cấu hình MCP", command=self.copy_mcp).pack(side="left", padx=6)
        self.root_var.trace_add("write", lambda *_: self._refresh_targets())
        return box

    # ---- form ----------------------------------------------------------------------------------------------
    def load_form(self, form):
        self.root_var.set(form.root)
        self.proj_list.delete(0, "end")
        for p in form.projects:
            self.proj_list.insert("end", p)
        self.config_var.set(form.config)
        self.scope_var.set(form.scope or "listed")
        self.codepage_var.set(str(form.codepage))
        self.define_var.set(form.define)
        self.undef_var.set(form.undef)
        self.exclude_var.set(form.exclude)
        self._refresh_configs()

    def read_form(self):
        try:
            codepage = int(self.codepage_var.get().strip() or "1258")
        except ValueError:
            raise ValueError("Codepage phải là số (vd. 1258, 932).")
        return logic.Form(root=self.root_var.get().strip(), projects=list(self.proj_list.get(0, "end")),
                          config=self.config_var.get().strip(), scope=self.scope_var.get(), codepage=codepage,
                          define=self.define_var.get(), undef=self.undef_var.get(), exclude=self.exclude_var.get())

    def _projects(self):
        return list(self.proj_list.get(0, "end"))

    def _add_projects(self, paths):
        have = set(self._projects())
        for p in paths:
            p = os.path.normpath(p)
            if p not in have:
                self.proj_list.insert("end", p)
                have.add(p)
        if not self.root_var.get().strip() and self._projects():
            self.root_var.set(logic.common_root(self._projects()))
        self._refresh_configs()

    def _refresh_configs(self):
        self.config_box["values"] = [""] + logic.project_configs(self._projects())

    def _refresh_targets(self):
        root = self.root_var.get().strip()
        values = [p for _, p in mcp_config.suggest_targets(root)] if root else []
        self.target_box["values"] = values
        if values and (not self.target_var.get() or self.target_var.get() not in values):
            self.target_var.set(values[0])

    # ---- actions -------------------------------------------------------------------------------------------
    def pick_root(self):
        d = filedialog.askdirectory(title="Chọn thư mục gốc", initialdir=self.root_var.get() or None)
        if d:
            self.load_form(logic.form_from_settings(os.path.normpath(d)))

    def add_vcxproj(self):
        paths = filedialog.askopenfilenames(title="Chọn .vcxproj", initialdir=self.root_var.get() or None,
                                            filetypes=[("Visual C++ project", "*.vcxproj"), ("All files", "*.*")])
        self._add_projects(paths)

    def add_from_sln(self):
        sln = filedialog.askopenfilename(title="Chọn .sln", initialdir=self.root_var.get() or None,
                                         filetypes=[("Solution", "*.sln"), ("All files", "*.*")])
        if not sln:
            return
        try:
            entries = logic.solution_projects(sln)
        except ValueError as ex:
            messagebox.showerror("mfcgraph", str(ex))
            return
        if not entries:
            messagebox.showinfo("mfcgraph", "Solution không có .vcxproj nào.")
            return
        SolutionPicker(self.master, entries, self._add_projects)

    def remove_projects(self):
        for i in reversed(self.proj_list.curselection()):
            self.proj_list.delete(i)
        self._refresh_configs()

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_index(self):
        if self.worker is not None:
            return
        try:
            form = self.read_form()
            logic.index_argv(form)
        except ValueError as ex:
            messagebox.showerror("mfcgraph", str(ex))
            return
        self.run_btn.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.status_var.set("Đang index...")
        self.worker = threading.Thread(target=self._index_thread, args=(form,), daemon=True)
        self.worker.start()

    def _index_thread(self, form):
        code = logic.run_index(form, lambda s: self.queue.put(("log", s)))
        self.queue.put(("done", code))

    def _poll(self):
        try:
            while True:
                kind, val = self.queue.get_nowait()
                if kind == "log":
                    self.append_log(val)
                else:
                    self.worker = None
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.run_btn.configure(state="normal")
                    self.status_var.set("Xong." if val == 0 else "Lỗi (xem log).")
                    self.append_log("\n")
        except queue.Empty:
            pass
        self.master.after(100, self._poll)

    def pick_target(self):
        root = self.root_var.get().strip()
        p = filedialog.asksaveasfilename(title="File cấu hình MCP", initialdir=root or None,
                                         initialfile="mcp.json" if not self.target_var.get() else
                                         os.path.basename(self.target_var.get()),
                                         defaultextension=".json", confirmoverwrite=False,
                                         filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if p:
            self.target_var.set(os.path.normpath(p))

    def _mcp_inputs(self):
        root = self.root_var.get().strip()
        if not root:
            raise ValueError("Chưa chọn thư mục gốc (root).")
        target = self.target_var.get().strip()
        if not target:
            raise ValueError("Chưa chọn file đích (.mcp.json / .vscode\\mcp.json).")
        return root, target, self.name_var.get().strip() or mcp_config.DEFAULT_NAME

    def preview_mcp(self):
        try:
            root, target, name = self._mcp_inputs()
            text, action = logic.mcp_preview(root, target, name)
        except (ValueError, OSError) as ex:
            messagebox.showerror("mfcgraph", str(ex))
            return
        if action == "unchanged":
            messagebox.showinfo("mfcgraph", "%s đã có đúng mục '%s'. Không cần ghi." % (target, name))
            return
        if not logic.has_index(root):
            if not messagebox.askyesno("mfcgraph", "Root này chưa có index. Vẫn ghi cấu hình MCP?\n"
                                                   "(Nhớ bấm \"Chạy index\" trước khi mở IDE.)"):
                return
        Preview(self.master, target, text, action, lambda: self._write_mcp(root, target, name))

    def _write_mcp(self, root, target, name):
        try:
            msg = logic.mcp_write(root, target, name)
        except (ValueError, OSError) as ex:
            messagebox.showerror("mfcgraph", str(ex))
            return
        self.append_log(msg + "\n")
        messagebox.showinfo("mfcgraph", msg)

    def copy_mcp(self):
        root = self.root_var.get().strip()
        if not root:
            messagebox.showerror("mfcgraph", "Chưa chọn thư mục gốc (root).")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(logic.mcp_snippet(root, self.name_var.get().strip()))
        self.status_var.set("Đã copy cấu hình MCP vào clipboard.")


class SolutionPicker(object):
    """Checkbox list of a solution's projects."""

    def __init__(self, master, entries, on_ok):
        self.top = tk.Toplevel(master)
        self.top.title("Chọn project trong solution")
        self.top.transient(master)
        self.vars = []
        canvas = tk.Canvas(self.top, width=520, height=min(400, 26 * len(entries) + 10))
        bar = ttk.Scrollbar(self.top, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        for name, path in entries:
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(inner, text="%s   (%s)" % (name, path), variable=v).pack(anchor="w", padx=6, pady=1)
            self.vars.append((v, path))
        canvas.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        row = ttk.Frame(self.top)
        row.grid(row=1, column=0, columnspan=2, sticky="e", padx=6, pady=6)
        ttk.Button(row, text="Chọn tất cả", command=lambda: [v.set(True) for v, _ in self.vars]).pack(side="left")
        ttk.Button(row, text="Thêm", command=lambda: self._ok(on_ok)).pack(side="left", padx=4)
        ttk.Button(row, text="Hủy", command=self.top.destroy).pack(side="left")
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

    def _ok(self, on_ok):
        chosen = [p for v, p in self.vars if v.get()]
        self.top.destroy()
        on_ok(chosen)


class Preview(object):
    """Shows the new MCP config file before writing it."""

    def __init__(self, master, target, text, action, on_write):
        self.top = tk.Toplevel(master)
        self.top.title("Xem trước: " + target)
        self.top.transient(master)
        what = "thêm mục mới" if action == "added" else "cập nhật mục đã có"
        note = "Sẽ %s vào %s.%s" % (what, target, " Bản cũ lưu thành .bak." if os.path.exists(target) else "")
        ttk.Label(self.top, text=note, wraplength=640).pack(anchor="w", padx=6, pady=4)
        txt = ScrolledText(self.top, width=90, height=22, font=("Consolas", 9))
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=6)
        row = ttk.Frame(self.top)
        row.pack(anchor="e", padx=6, pady=6)
        ttk.Button(row, text="Ghi", command=lambda: (self.top.destroy(), on_write())).pack(side="left", padx=4)
        ttk.Button(row, text="Hủy", command=self.top.destroy).pack(side="left")


def run(root=""):
    master = tk.Tk()
    App(master, os.path.abspath(root) if root else "")
    master.mainloop()
    return 0
