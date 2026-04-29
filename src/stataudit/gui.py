"""Tkinter GUI for StatAudit.

Launch with:
    python -m stataudit.gui
    stataudit --gui          (CLI flag)
    stataudit-gui            (dedicated entry point)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from typing import Optional

from . import __version__
from ._rules import RULES
from .auditor import audit_file, audit_text
from .report import AuditReport, Severity

_SEV_FG = {"ERROR": "#c0392b", "WARNING": "#c67c00", "INFO": "#1a6fa8"}
_SEV_BG = {"ERROR": "#fde8e6", "WARNING": "#fef6e7", "INFO": "#e8f4fc"}


class _RulesWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Registered Rules")
        self.geometry("860x380")
        self.resizable(True, True)

        cols = ("name", "severity", "suggestion")
        tree = ttk.Treeview(self, columns=cols, show="headings")
        tree.heading("name", text="Rule Name")
        tree.heading("severity", text="Severity")
        tree.heading("suggestion", text="Suggestion / Guidance")
        tree.column("name", width=200, minwidth=140, stretch=False)
        tree.column("severity", width=80, minwidth=70, stretch=False)
        tree.column("suggestion", width=540)

        for sev, color in _SEV_FG.items():
            tree.tag_configure(sev, foreground=color)

        for name, _, sev, suggestion in RULES:
            tree.insert("", tk.END, values=(name, sev.value, suggestion), tags=(sev.value,))

        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)


class StatAuditApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"StatAudit {__version__} — Statistical Reporting Auditor")
        self.geometry("1150x740")
        self.minsize(820, 520)
        self._report: Optional[AuditReport] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_menu()

        # Top toolbar
        tb = ttk.Frame(self, padding=(4, 4, 4, 0))
        tb.pack(side=tk.TOP, fill=tk.X)
        self._build_toolbar(tb)

        # Horizontal paned window: left = input, right = results
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left = ttk.Frame(paned)
        paned.add(left, weight=2)
        self._build_input_panel(left)

        right = ttk.Frame(paned)
        paned.add(right, weight=3)
        self._build_results_panel(right)

        # Status bar
        self._status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self._status, relief=tk.SUNKEN, anchor=tk.W,
                  padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open File…", accelerator="Ctrl+O", command=self._open_file)
        file_menu.add_command(label="Clear Input", command=self._clear_input)
        file_menu.add_separator()
        file_menu.add_command(label="Export JSON…", command=lambda: self._export("json"))
        file_menu.add_command(label="Export Markdown…", command=lambda: self._export("markdown"))
        file_menu.add_command(label="Export HTML…", command=lambda: self._export("html"))
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator="Ctrl+Q", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=False)
        tools_menu.add_command(label="List Rules…", command=self._show_rules)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)
        self.bind_all("<Control-o>", lambda _e: self._open_file())
        self.bind_all("<Control-q>", lambda _e: self.quit())

    def _build_toolbar(self, parent: ttk.Frame) -> None:
        ttk.Button(parent, text="Open File…", command=self._open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(parent, text="Clear", command=self._clear_input).pack(side=tk.LEFT, padx=2)
        ttk.Separator(parent, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        ttk.Label(parent, text="Min Severity:").pack(side=tk.LEFT)
        self._sev_var = tk.StringVar(value="INFO")
        ttk.Combobox(
            parent, textvariable=self._sev_var,
            values=["INFO", "WARNING", "ERROR"],
            state="readonly", width=10,
        ).pack(side=tk.LEFT, padx=(2, 8))

        ttk.Button(parent, text="▶  Run Audit", command=self._run_audit).pack(side=tk.LEFT, padx=2)
        ttk.Separator(parent, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        ttk.Button(parent, text="Rules…", command=self._show_rules).pack(side=tk.LEFT, padx=2)
        ttk.Separator(parent, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        ttk.Label(parent, text="Export:").pack(side=tk.LEFT)
        ttk.Button(parent, text="JSON", command=lambda: self._export("json")).pack(side=tk.LEFT, padx=2)
        ttk.Button(parent, text="Markdown", command=lambda: self._export("markdown")).pack(side=tk.LEFT, padx=2)
        ttk.Button(parent, text="HTML", command=lambda: self._export("html")).pack(side=tk.LEFT, padx=2)

        self._char_lbl = tk.StringVar(value="0 chars")
        ttk.Label(parent, textvariable=self._char_lbl, foreground="#666").pack(side=tk.RIGHT, padx=8)

    def _build_input_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Input Text", font=("", 10, "bold")).pack(anchor=tk.W, padx=4, pady=(2, 0))
        self._text_input = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, font=("Courier", 10), undo=True,
            relief=tk.FLAT, borderwidth=1,
        )
        self._text_input.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._text_input.bind("<KeyRelease>", self._on_text_change)

    def _build_results_panel(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=4, pady=(2, 0))
        ttk.Label(header, text="Findings", font=("", 10, "bold")).pack(side=tk.LEFT)
        self._count_lbl = tk.StringVar(value="")
        ttk.Label(header, textvariable=self._count_lbl, foreground="#555").pack(side=tk.LEFT, padx=8)

        # Treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        cols = ("severity", "rule", "location", "text", "suggestion")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("severity", text="Severity")
        self._tree.heading("rule", text="Rule")
        self._tree.heading("location", text="Location")
        self._tree.heading("text", text="Matched Text")
        self._tree.heading("suggestion", text="Suggestion")

        self._tree.column("severity", width=80, minwidth=70, stretch=False)
        self._tree.column("rule", width=170, minwidth=120, stretch=False)
        self._tree.column("location", width=85, minwidth=70, stretch=False)
        self._tree.column("text", width=200, minwidth=120)
        self._tree.column("suggestion", width=320, minwidth=180)

        for sev, fg in _SEV_FG.items():
            self._tree.tag_configure(sev, foreground=fg, background=_SEV_BG[sev])

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Detail pane
        ttk.Label(parent, text="Detail", font=("", 9, "bold")).pack(anchor=tk.W, padx=4, pady=(0, 2))
        self._detail = scrolledtext.ScrolledText(
            parent, height=5, wrap=tk.WORD, font=("Courier", 9),
            state=tk.DISABLED, relief=tk.FLAT, borderwidth=1,
        )
        self._detail.pack(fill=tk.X, padx=4, pady=(0, 4))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_text_change(self, _event=None) -> None:
        n = len(self._text_input.get("1.0", tk.END)) - 1  # -1 for trailing newline
        self._char_lbl.set(f"{n:,} chars")

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open text file for auditing",
            filetypes=[
                ("Text / Manuscript", "*.txt *.md *.tex *.rst *.csv"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            self._text_input.delete("1.0", tk.END)
            self._text_input.insert("1.0", content)
            self._on_text_change()
            self._status.set(f"Loaded: {path}")
        except OSError as exc:
            messagebox.showerror("Open Error", str(exc))

    def _clear_input(self) -> None:
        self._text_input.delete("1.0", tk.END)
        self._on_text_change()
        self._clear_results()
        self._status.set("Input cleared.")

    def _clear_results(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._count_lbl.set("")
        self._report = None
        self._set_detail("")

    def _run_audit(self) -> None:
        text = self._text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Input", "Please enter or load text to audit.")
            return
        min_sev = Severity(self._sev_var.get())
        try:
            findings = audit_text(text, min_sev)
            self._report = AuditReport(source="<input>", findings=findings)
            self._populate_results()
            n = len(findings)
            self._status.set(f"Audit complete — {n} finding{'s' if n != 1 else ''}.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Audit Error", str(exc))

    def _populate_results(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if self._report is None:
            return
        s = self._report.summary["by_severity"]
        self._count_lbl.set(
            f"{self._report.summary['total']} total  ·  "
            f"ERROR {s['ERROR']}  WARNING {s['WARNING']}  INFO {s['INFO']}"
        )
        for f in self._report.findings:
            self._tree.insert(
                "", tk.END,
                values=(f.severity.value, f.rule, f.location, f.text, f.suggestion),
                tags=(f.severity.value,),
            )

    def _on_tree_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0])["values"]
        if not vals:
            return
        sev, rule, loc, text, suggestion = vals
        detail = (
            f"[{sev}] {rule}\n"
            f"  Location  : {loc}\n"
            f"  Text      : {text!r}\n"
            f"  Suggestion: {suggestion}"
        )
        self._set_detail(detail)

    def _set_detail(self, text: str) -> None:
        self._detail.config(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)
        self._detail.insert("1.0", text)
        self._detail.config(state=tk.DISABLED)

    def _export(self, fmt: str) -> None:
        if self._report is None:
            messagebox.showwarning("No Results", "Run an audit first, then export.")
            return
        ext = {"json": ".json", "markdown": ".md", "html": ".html"}[fmt]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(fmt.upper(), f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            if fmt == "json":
                content = self._report.to_json()
            elif fmt == "markdown":
                content = self._report.to_markdown()
            else:
                content = self._report._to_html()
            Path(path).write_text(content, encoding="utf-8")
            self._status.set(f"Exported to: {path}")
        except OSError as exc:
            messagebox.showerror("Export Error", str(exc))

    def _show_rules(self) -> None:
        _RulesWindow(self)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About StatAudit",
            f"StatAudit  v{__version__}\n\n"
            "Statistical Reporting Auditor for scientific manuscripts.\n\n"
            "Checks p-values, confidence intervals, effect sizes,\n"
            "sample sizes, degrees of freedom, and more.\n\n"
            "MIT License — Vaibhav Deshmukh",
        )


def launch() -> None:
    """Entry point for the GUI (also called by ``stataudit --gui``)."""
    app = StatAuditApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
