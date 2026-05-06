#!/usr/bin/env python3
"""
stataudit_gui — Tkinter GUI for stataudit

Provides a graphical interface for auditing statistical reporting in manuscripts.
Stdlib-only — requires Python built with Tk support (standard in CPython distributions).
"""

from __future__ import annotations

import importlib.util
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from typing import List, Optional


def _import_stataudit():
    """Import stataudit, falling back to the sibling .py file if needed."""
    try:
        import stataudit as sa
        return sa
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "stataudit", Path(__file__).with_name("stataudit.py")
        )
        sa = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(sa)  # type: ignore[union-attr]
        return sa


_sa = _import_stataudit()
audit_text = _sa.audit_text
AuditReport = _sa.AuditReport
Finding = _sa.Finding
Severity = _sa.Severity
_RULES = _sa._RULES

# ── Colour palette ────────────────────────────────────────────────────────────

_SEV_FG = {
    "ERROR":   "#c62828",
    "WARNING": "#e65100",
    "INFO":    "#1565c0",
}
_SEV_BG = {
    "ERROR":   "#ffebee",
    "WARNING": "#fff3e0",
    "INFO":    "#e3f2fd",
}
_SEV_ICON = {
    "ERROR":   "✖",
    "WARNING": "⚠",
    "INFO":    "ℹ",
}

# ── Main window ───────────────────────────────────────────────────────────────


class StatAuditApp:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("stataudit — Statistical Reporting Auditor")
        self.root.minsize(960, 660)
        self._report: Optional[AuditReport] = None
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open…\tCtrl+O", command=self._open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Export Text…", command=lambda: self._export("text"))
        file_menu.add_command(label="Export Markdown…", command=lambda: self._export("markdown"))
        file_menu.add_command(label="Export JSON…", command=lambda: self._export("json"))
        file_menu.add_separator()
        file_menu.add_command(label="Quit\tCtrl+Q", command=self.root.quit)

        audit_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Audit", menu=audit_menu)
        audit_menu.add_command(label="Run Audit\tCtrl+R", command=self._run_audit)
        audit_menu.add_command(label="Clear All\tCtrl+L", command=self._clear_all)

        help_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Rule Reference", command=self._show_rules)
        help_menu.add_command(label="About", command=self._show_about)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_toolbar()

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))

        left_frame = ttk.Frame(paned)
        right_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=1)

        self._build_input_panel(left_frame)
        self._build_results_panel(right_frame)
        self._build_statusbar()

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, relief=tk.GROOVE)
        bar.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        ttk.Button(bar, text="📂 Open File", command=self._open_file).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        ttk.Button(bar, text="▶ Run Audit", command=self._run_audit).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(bar, text="✖ Clear", command=self._clear_all).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        ttk.Label(bar, text="Min severity:").pack(side=tk.LEFT, padx=(4, 2))
        self._sev_var = tk.StringVar(value="INFO")
        ttk.Combobox(
            bar, textvariable=self._sev_var, state="readonly",
            values=["INFO", "WARNING", "ERROR"], width=9,
        ).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        self._summary_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._summary_var, foreground="#444").pack(side=tk.LEFT, padx=6)

    def _build_input_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Manuscript text:", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 2))

        self._text_input = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, font=("Courier", 10), undo=True,
        )
        self._text_input.grid(row=1, column=0, sticky="nsew")
        self._text_input.bind("<Control-Return>", lambda _e: self._run_audit())

    def _build_results_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=2)
        parent.rowconfigure(3, weight=1)

        ttk.Label(parent, text="Findings:", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 2))

        # Treeview + scrollbar
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        cols = ("icon", "severity", "rule", "location", "text")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("icon",     text="")
        self._tree.heading("severity", text="Severity")
        self._tree.heading("rule",     text="Rule")
        self._tree.heading("location", text="Location")
        self._tree.heading("text",     text="Matched text")
        self._tree.column("icon",     width=28,  stretch=False, anchor="center")
        self._tree.column("severity", width=80,  stretch=False)
        self._tree.column("rule",     width=200, stretch=False)
        self._tree.column("location", width=90,  stretch=False)
        self._tree.column("text",     width=240)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for sev in Severity:
            self._tree.tag_configure(
                sev.value,
                foreground=_SEV_FG[sev.value],
                background=_SEV_BG[sev.value],
            )

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail pane
        ttk.Label(parent, text="Finding details:", font=("TkDefaultFont", 9, "bold")).grid(
            row=2, column=0, sticky="w", pady=(8, 2))

        self._detail = scrolledtext.ScrolledText(
            parent, height=7, wrap=tk.WORD, font=("Courier", 9), state="disabled",
        )
        self._detail.grid(row=3, column=0, sticky="nsew")

        # Export row
        exp = ttk.Frame(parent)
        exp.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(exp, text="Export:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(exp, text="Text",     command=lambda: self._export("text")).pack(side=tk.LEFT, padx=2)
        ttk.Button(exp, text="Markdown", command=lambda: self._export("markdown")).pack(side=tk.LEFT, padx=2)
        ttk.Button(exp, text="JSON",     command=lambda: self._export("json")).pack(side=tk.LEFT, padx=2)

    def _build_statusbar(self) -> None:
        self._status_var = tk.StringVar(value="Ready.  Paste text or open a file, then press Run Audit.")
        bar = ttk.Label(self.root, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W)
        bar.grid(row=2, column=0, sticky="ew", padx=0)

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _e: self._open_file())
        self.root.bind("<Control-r>", lambda _e: self._run_audit())
        self.root.bind("<Control-l>", lambda _e: self._clear_all())
        self.root.bind("<Control-q>", lambda _e: self.root.quit())

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open manuscript",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Error opening file", str(exc))
            return
        self._text_input.delete("1.0", tk.END)
        self._text_input.insert("1.0", text)
        self._status(f"Opened: {path}")

    def _clear_all(self) -> None:
        self._text_input.delete("1.0", tk.END)
        self._clear_results()
        self._status("Cleared.")

    def _run_audit(self) -> None:
        text = self._text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No text", "Please paste or open manuscript text first.")
            return
        min_sev = Severity(self._sev_var.get())
        findings = audit_text(text, min_sev)
        self._report = AuditReport(source="GUI input", findings=findings)
        self._populate_tree(findings)
        s = self._report.summary["by_severity"]
        self._summary_var.set(
            f"Total: {len(findings)}  ·  "
            f"ERROR {s['ERROR']}  ·  WARNING {s['WARNING']}  ·  INFO {s['INFO']}"
        )
        self._status(f"Audit complete — {len(findings)} finding(s).")

    def _populate_tree(self, findings: List[Finding]) -> None:
        self._clear_results()
        for f in findings:
            self._tree.insert(
                "", tk.END,
                values=(
                    _SEV_ICON[f.severity.value],
                    f.severity.value,
                    f.rule,
                    f.location,
                    f.text[:80],
                ),
                tags=(f.severity.value,),
            )

    def _clear_results(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._set_detail("")
        self._summary_var.set("")
        self._report = None

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel or self._report is None:
            return
        idx = self._tree.index(sel[0])
        if idx < len(self._report.findings):
            f = self._report.findings[idx]
            self._set_detail(
                f"Rule      : {f.rule}\n"
                f"Severity  : {f.severity.value}\n"
                f"Location  : {f.location}\n"
                f"Text      : {f.text!r}\n"
                f"\nSuggestion:\n  {f.suggestion}\n"
            )

    def _set_detail(self, text: str) -> None:
        self._detail.config(state="normal")
        self._detail.delete("1.0", tk.END)
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    def _export(self, fmt: str) -> None:
        if self._report is None:
            messagebox.showwarning("No report", "Run an audit first.")
            return
        ext = {"text": ".txt", "markdown": ".md", "json": ".json"}[fmt]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("All files", "*.*")],
            title=f"Save {fmt} report",
        )
        if not path:
            return
        content = {
            "text":     self._report.to_text,
            "markdown": self._report.to_markdown,
            "json":     self._report.to_json,
        }[fmt]()
        try:
            Path(path).write_text(content, encoding="utf-8")
            self._status(f"Report saved: {path}")
        except OSError as exc:
            messagebox.showerror("Error saving file", str(exc))

    # ── Help dialogs ──────────────────────────────────────────────────────────

    def _show_rules(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Rule Reference")
        win.minsize(700, 400)

        cols = ("rule", "severity", "suggestion")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("rule",       text="Rule")
        tree.heading("severity",   text="Severity")
        tree.heading("suggestion", text="Suggestion")
        tree.column("rule",       width=200, stretch=False)
        tree.column("severity",   width=80,  stretch=False)
        tree.column("suggestion", width=400)

        for sev in Severity:
            tree.tag_configure(sev.value, foreground=_SEV_FG[sev.value])

        for name, _, sev, suggestion in _RULES:
            tree.insert("", tk.END, values=(name, sev.value, suggestion), tags=(sev.value,))

        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About stataudit",
            "stataudit v0.1.0\n\n"
            "Statistical Reporting Auditor for scientific manuscripts.\n\n"
            "Author: Vaibhav Deshmukh\n"
            "License: MIT\n\n"
            "Checks p-values, CIs, effect sizes, degrees of freedom, "
            "sample sizes, and other statistical reporting conventions.",
        )

    def _status(self, msg: str) -> None:
        self._status_var.set(msg)


# ── Entry point ───────────────────────────────────────────────────────────────


def launch() -> None:
    """Start the stataudit GUI application."""
    root = tk.Tk()
    StatAuditApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
