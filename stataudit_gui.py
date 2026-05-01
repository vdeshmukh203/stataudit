#!/usr/bin/env python3
"""
stataudit_gui — Graphical interface for the Statistical Reporting Auditor.

Provides a Tkinter-based desktop application wrapping the stataudit library.
Stdlib-only; no external dependencies required.

Launch:
    python stataudit_gui.py
    # or, after installation:
    stataudit-gui
"""

from __future__ import annotations

import sys
import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

# Ensure stataudit.py on the same directory is importable when run directly.
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import stataudit as sa

__version__ = sa.__version__

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_SEV_FG = {"ERROR": "#c0392b", "WARNING": "#b7600a", "INFO": "#1a7a3c"}
_SEV_TAG_OPTS = {
    "ERROR":   {"foreground": _SEV_FG["ERROR"],   "font": ("TkDefaultFont", 9, "bold")},
    "WARNING": {"foreground": _SEV_FG["WARNING"], "font": ("TkDefaultFont", 9, "bold")},
    "INFO":    {"foreground": _SEV_FG["INFO"],    "font": ("TkDefaultFont", 9)},
}


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class StatAuditApp:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"stataudit {__version__} — Statistical Reporting Auditor")
        self.root.geometry("1200x750")
        self.root.minsize(800, 500)

        self._report: Optional[sa.AuditReport] = None
        self._sort_col: str = ""
        self._sort_rev: bool = False

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        # Keyboard shortcuts
        self.root.bind("<Control-o>", lambda _e: self.open_file())
        self.root.bind("<Control-Return>", lambda _e: self.run_audit())
        self.root.bind("<Control-s>", lambda _e: self.export_report())

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        # File
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open File…", accelerator="Ctrl+O",
                              command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Export Report…", accelerator="Ctrl+S",
                              command=self.export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="List All Rules", command=self.show_rules)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(4, 3))
        bar.pack(fill=tk.X)

        ttk.Button(bar, text="Open File", command=self.open_file).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Audit  (Ctrl+↵)", command=self.run_audit).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Clear", command=self.clear_all).pack(
            side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y,
                                                     padx=6, pady=2)

        ttk.Label(bar, text="Min severity:").pack(side=tk.LEFT)
        self._severity_var = tk.StringVar(value="INFO")
        sev_cb = ttk.Combobox(bar, textvariable=self._severity_var,
                               values=["INFO", "WARNING", "ERROR"],
                               width=9, state="readonly")
        sev_cb.pack(side=tk.LEFT, padx=(2, 0))

        ttk.Button(bar, text="Export Report…", command=self.export_report).pack(
            side=tk.RIGHT, padx=2)

    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 2))

        # ── Left: manuscript text input ────────────────────────────────
        left = ttk.LabelFrame(paned, text="Manuscript Text")
        paned.add(left, weight=1)

        self._text_area = scrolledtext.ScrolledText(
            left, wrap=tk.WORD, font=("Monospace", 10),
            undo=True, autoseparators=True,
        )
        self._text_area.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        # Hint text
        hint = ("Paste manuscript text here, or use File → Open File…\n"
                "Then press Audit (Ctrl+↵) to run the audit.")
        self._text_area.insert("1.0", hint)
        self._text_area.tag_add("hint", "1.0", tk.END)
        self._text_area.tag_configure("hint", foreground="#aaaaaa")
        self._text_area.bind("<FocusIn>", self._clear_hint)
        self._hint_active = True

        # ── Right: findings + detail ───────────────────────────────────
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        findings_frame = ttk.LabelFrame(right, text="Audit Findings")
        findings_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Severity", "Rule", "Location", "Text")
        self._tree = ttk.Treeview(findings_frame, columns=cols,
                                  show="headings", selectmode="browse")
        col_widths = {"Severity": 75, "Rule": 170, "Location": 70, "Text": 260}
        for col in cols:
            self._tree.heading(
                col, text=col,
                command=lambda c=col: self._sort_by(c),
            )
            self._tree.column(col, width=col_widths[col], minwidth=50)

        vsb = ttk.Scrollbar(findings_frame, orient=tk.VERTICAL,
                             command=self._tree.yview)
        hsb = ttk.Scrollbar(findings_frame, orient=tk.HORIZONTAL,
                             command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        findings_frame.rowconfigure(0, weight=1)
        findings_frame.columnconfigure(0, weight=1)

        for sev, opts in _SEV_TAG_OPTS.items():
            self._tree.tag_configure(sev, **opts)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Summary strip
        self._summary_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self._summary_var,
                  font=("TkDefaultFont", 9)).pack(anchor=tk.W, padx=4)

        # Suggestion detail
        detail_frame = ttk.LabelFrame(right, text="Suggestion")
        detail_frame.pack(fill=tk.X, padx=0, pady=(2, 0))
        self._detail = tk.Text(detail_frame, height=3, wrap=tk.WORD,
                               font=("TkDefaultFont", 9),
                               state=tk.DISABLED, relief=tk.FLAT,
                               background=self.root.cget("background"))
        self._detail.pack(fill=tk.X, padx=4, pady=3)

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, relief=tk.SUNKEN)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self._status_var = tk.StringVar(
            value="Ready.  Open a file or paste text, then click Audit.")
        ttk.Label(bar, textvariable=self._status_var,
                  anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _clear_hint(self, _event=None) -> None:
        if self._hint_active:
            self._text_area.delete("1.0", tk.END)
            self._text_area.tag_remove("hint", "1.0", tk.END)
            self._hint_active = False

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Manuscript",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Open Error", str(exc))
            return
        self._clear_hint()
        self._text_area.delete("1.0", tk.END)
        self._text_area.insert("1.0", text)
        self._status_var.set(f"Loaded: {path}")
        self.run_audit()

    def run_audit(self) -> None:
        text = self._text_area.get("1.0", tk.END).strip()
        if not text or self._hint_active:
            self._status_var.set("Nothing to audit — paste text or open a file first.")
            return

        min_sev = sa.Severity(self._severity_var.get())
        findings = sa.audit_text(text, min_sev)
        self._report = sa.AuditReport(source="<gui>", findings=findings)

        self._populate_tree(findings)

        s = self._report.summary["by_severity"]
        total = len(findings)
        self._summary_var.set(
            f"  {total} finding{'s' if total != 1 else ''}  —  "
            f"ERROR {s['ERROR']}  ·  WARNING {s['WARNING']}  ·  INFO {s['INFO']}"
        )
        self._status_var.set(
            f"Audit complete: {total} finding{'s' if total != 1 else ''} found."
        )

    def _populate_tree(self, findings: list) -> None:
        self._tree.delete(*self._tree.get_children())
        for f in findings:
            self._tree.insert(
                "", tk.END,
                values=(f.severity.value, f.rule, f.location, f.text),
                tags=(f.severity.value,),
            )

    def _on_select(self, _event=None) -> None:
        selected = self._tree.selection()
        if not selected or self._report is None:
            return
        idx = self._tree.index(selected[0])
        if idx < len(self._report.findings):
            suggestion = self._report.findings[idx].suggestion
            self._detail.configure(state=tk.NORMAL)
            self._detail.delete("1.0", tk.END)
            self._detail.insert("1.0", suggestion)
            self._detail.configure(state=tk.DISABLED)

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        items = [
            (self._tree.set(child, col), child)
            for child in self._tree.get_children("")
        ]
        items.sort(reverse=self._sort_rev)
        for rank, (_, child) in enumerate(items):
            self._tree.move(child, "", rank)
        arrow = " ▲" if not self._sort_rev else " ▼"
        for c in ("Severity", "Rule", "Location", "Text"):
            self._tree.heading(c, text=c + (arrow if c == col else ""))

    def clear_all(self) -> None:
        self._text_area.delete("1.0", tk.END)
        self._tree.delete(*self._tree.get_children())
        self._detail.configure(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)
        self._detail.configure(state=tk.DISABLED)
        self._summary_var.set("")
        self._report = None
        self._status_var.set("Ready.")

    def export_report(self) -> None:
        if self._report is None or not self._report.findings:
            messagebox.showinfo("Export", "Run an audit first — no findings to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Report",
            defaultextension=".txt",
            filetypes=[
                ("Plain text", "*.txt"),
                ("Markdown",   "*.md"),
                ("JSON",       "*.json"),
                ("HTML",       "*.html"),
            ],
        )
        if not path:
            return
        p = pathlib.Path(path)
        fmt_map = {
            ".md":   self._report.to_markdown,
            ".json": self._report.to_json,
            ".html": self._report.to_html,
        }
        content = fmt_map.get(p.suffix, self._report.to_text)()
        try:
            p.write_text(content, encoding="utf-8")
            self._status_var.set(f"Report exported to {path}")
        except OSError as exc:
            messagebox.showerror("Export Error", str(exc))

    def show_rules(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Detection Rules")
        win.geometry("820x460")

        cols = ("Rule", "Severity", "Suggestion")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("Rule",       text="Rule Name")
        tree.heading("Severity",   text="Severity")
        tree.heading("Suggestion", text="Suggestion")
        tree.column("Rule",       width=200, minwidth=120)
        tree.column("Severity",   width=80,  minwidth=70)
        tree.column("Suggestion", width=520, minwidth=200)

        vsb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        for sev, opts in _SEV_TAG_OPTS.items():
            tree.tag_configure(sev, **opts)

        for name, _pat, sev, suggestion in sa._RULES:
            tree.insert("", tk.END,
                        values=(name, sev.value, suggestion),
                        tags=(sev.value,))

    def show_about(self) -> None:
        messagebox.showinfo(
            "About stataudit",
            f"stataudit  v{__version__}\n\n"
            "Statistical Reporting Auditor for academic manuscripts.\n\n"
            "Detects common statistical reporting errors and omissions:\n"
            "  • Missing or imprecise p-values\n"
            "  • Unreported confidence intervals\n"
            "  • Missing degrees of freedom\n"
            "  • Absent effect sizes\n"
            "  • One-tailed test usage\n"
            "  • Small sample sizes\n"
            "  … and more.\n\n"
            "License: MIT\n"
            "Author: Vaibhav Deshmukh",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the stataudit GUI application."""
    root = tk.Tk()
    _app = StatAuditApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
