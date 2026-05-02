#!/usr/bin/env python3
"""
stataudit_gui.py — Tkinter graphical interface for stataudit.

Launch with:
    python stataudit_gui.py
or via the installed entry point:
    stataudit-gui
"""

from __future__ import annotations

import sys
import pathlib

# Ensure root-level stataudit module is importable when run directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError:
    sys.exit(
        "Error: tkinter is not available.\n"
        "On Debian/Ubuntu: sudo apt install python3-tk\n"
        "On Fedora:        sudo dnf install python3-tkinter\n"
        "On macOS/Windows: tkinter ships with the standard Python installer."
    )

from stataudit import AuditReport, Finding, Severity, _RULES, audit_file, audit_text

_SEVERITY_COLORS = {
    "ERROR":   "#d32f2f",
    "WARNING": "#e65100",
    "INFO":    "#1565c0",
}

_SAMPLE_TEXT = """\
We recruited n = 18 participants and found a significant effect (p = .00001).
The ANOVA yielded F = 6.3, and a post-hoc t = -2.4 was observed.
Missing data were excluded without further explanation.
The regression model fit the data well.
A CI was computed for each condition.
One-tailed tests were applied throughout.
The mean response was 4.12345678 seconds.
"""


class _RulesDialog(tk.Toplevel):
    """Modal dialog listing all detection rules."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Detection Rules")
        self.resizable(True, True)
        self.minsize(700, 400)

        cols = ("Rule", "Severity", "Suggestion")
        tree = ttk.Treeview(self, columns=cols, show="headings")
        tree.heading("Rule", text="Rule")
        tree.heading("Severity", text="Severity")
        tree.heading("Suggestion", text="Suggestion")
        tree.column("Rule", width=200, anchor="w")
        tree.column("Severity", width=80, anchor="center")
        tree.column("Suggestion", width=400, anchor="w")

        for name, _, sev, suggestion in _RULES:
            tree.insert("", tk.END, values=(name, sev.value, suggestion),
                        tags=(sev.value,))

        for sev, color in _SEVERITY_COLORS.items():
            tree.tag_configure(sev, foreground=color)

        sb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=6, padx=(0, 6))

        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0, 6))
        self.grab_set()
        self.focus_set()


class StatAuditApp:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("stataudit — Statistical Reporting Auditor")
        self.root.minsize(960, 640)

        self._current_report: AuditReport | None = None
        self._current_source: str = "<editor>"

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        # Load sample text so the tool feels immediately usable
        self._input.insert("1.0", _SAMPLE_TEXT.strip())

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=False)
        fm.add_command(label="Open file…", accelerator="Ctrl+O", command=self._open_file)
        fm.add_separator()
        fm.add_command(label="Export as Markdown…", command=self._export_markdown)
        fm.add_command(label="Export as JSON…",     command=self._export_json)
        fm.add_command(label="Export as Text…",     command=self._export_text)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.root.quit)
        mb.add_cascade(label="File", menu=fm)

        em = tk.Menu(mb, tearoff=False)
        em.add_command(label="Clear all", command=self._clear_all)
        em.add_command(label="Load sample text", command=self._load_sample)
        mb.add_cascade(label="Edit", menu=em)

        hm = tk.Menu(mb, tearoff=False)
        hm.add_command(label="Show all rules…", command=self._show_rules)
        hm.add_command(label="About", command=self._show_about)
        mb.add_cascade(label="Help", menu=hm)

        self.root.config(menu=mb)
        self.root.bind_all("<Control-o>", lambda _e: self._open_file())

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, relief=tk.RIDGE)
        bar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        ttk.Button(bar, text="Open File", command=self._open_file).pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        ttk.Label(bar, text="Min severity:").pack(side=tk.LEFT, padx=(0, 2))
        self._sev_var = tk.StringVar(value="INFO")
        ttk.Combobox(
            bar, textvariable=self._sev_var,
            values=["INFO", "WARNING", "ERROR"],
            width=9, state="readonly",
        ).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Label(bar, text="Report format:").pack(side=tk.LEFT, padx=(0, 2))
        self._fmt_var = tk.StringVar(value="text")
        ttk.Combobox(
            bar, textvariable=self._fmt_var,
            values=["text", "markdown", "json"],
            width=9, state="readonly",
        ).pack(side=tk.LEFT, padx=(0, 4))
        self._fmt_var.trace_add("write", lambda *_: self._refresh_report())

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        ttk.Button(bar, text="▶  Run Audit", command=self._run_audit).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="✕  Clear",      command=self._clear_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Rules…",         command=self._show_rules).pack(side=tk.RIGHT, padx=4)

    def _build_body(self) -> None:
        # Outer vertical paned window
        outer = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 2))

        # ── Input panel ──────────────────────────────────────────────
        input_frame = ttk.LabelFrame(outer, text="Input text (paste or open a file)")
        self._input = scrolledtext.ScrolledText(
            input_frame, wrap=tk.WORD, height=10,
            font=("Courier", 10), undo=True,
        )
        self._input.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        outer.add(input_frame, weight=1)

        # ── Bottom split: findings table | report text ───────────────
        lower = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        outer.add(lower, weight=2)

        # Findings treeview
        findings_frame = ttk.LabelFrame(lower, text="Findings")
        cols = ("Severity", "Rule", "Location", "Snippet")
        self._tree = ttk.Treeview(
            findings_frame, columns=cols, show="headings",
            selectmode="browse", height=14,
        )
        for col, w in zip(cols, (80, 160, 80, 320)):
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort_tree(c))
            self._tree.column(col, width=w, minwidth=50, anchor="w")

        for sev, color in _SEVERITY_COLORS.items():
            self._tree.tag_configure(sev, foreground=color)

        tree_vsb = ttk.Scrollbar(findings_frame, orient=tk.VERTICAL,   command=self._tree.yview)
        tree_hsb = ttk.Scrollbar(findings_frame, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        tree_hsb.grid(row=1, column=0, sticky="ew")
        findings_frame.rowconfigure(0, weight=1)
        findings_frame.columnconfigure(0, weight=1)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        lower.add(findings_frame, weight=2)

        # Suggestion / report panel with tabs
        right_nb = ttk.Notebook(lower)
        lower.add(right_nb, weight=1)

        # Tab 1: suggestion detail for selected finding
        detail_frame = ttk.Frame(right_nb)
        right_nb.add(detail_frame, text="Detail")
        self._detail_text = scrolledtext.ScrolledText(
            detail_frame, wrap=tk.WORD, state=tk.DISABLED, height=14,
            font=("TkDefaultFont", 10),
        )
        self._detail_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Tab 2: full formatted report
        report_frame = ttk.Frame(right_nb)
        right_nb.add(report_frame, text="Report")
        self._report_text = scrolledtext.ScrolledText(
            report_frame, wrap=tk.WORD, state=tk.DISABLED, height=14,
            font=("Courier", 9),
        )
        self._report_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._right_nb = right_nb

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._status_var = tk.StringVar(value="Ready — paste text or open a file, then click Run Audit.")
        ttk.Label(bar, textvariable=self._status_var, anchor=tk.W).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=2
        )
        self._count_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._count_var, anchor=tk.E).pack(
            side=tk.RIGHT, padx=6
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open manuscript text file",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown",   "*.md"),
                ("All files",  "*.*"),
            ],
        )
        if not path:
            return
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("File error", str(exc))
            return
        self._input.delete("1.0", tk.END)
        self._input.insert("1.0", text)
        self._current_source = path
        self._status_var.set(f"Opened: {path}")
        self._run_audit(source=path)

    def _run_audit(self, source: str | None = None) -> None:
        text = self._input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("No input", "Please enter or load text before running the audit.")
            return

        min_sev = Severity(self._sev_var.get())
        findings = audit_text(text, min_sev)
        src = source or self._current_source
        self._current_report = AuditReport(source=src, findings=findings)

        self._populate_tree(findings)
        self._refresh_report()

        counts = self._current_report.summary["by_severity"]
        n = len(findings)
        self._count_var.set(
            f"ERROR: {counts['ERROR']}  WARNING: {counts['WARNING']}  INFO: {counts['INFO']}"
        )
        if n == 0:
            self._status_var.set("Audit complete — no findings.")
        else:
            self._status_var.set(
                f"Audit complete — {n} finding{'s' if n != 1 else ''} detected."
            )

    def _clear_all(self) -> None:
        self._input.delete("1.0", tk.END)
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._set_detail("")
        self._set_report("")
        self._current_report = None
        self._current_source = "<editor>"
        self._status_var.set("Cleared.")
        self._count_var.set("")

    def _load_sample(self) -> None:
        self._input.delete("1.0", tk.END)
        self._input.insert("1.0", _SAMPLE_TEXT.strip())
        self._current_source = "<editor>"
        self._status_var.set("Sample text loaded — click Run Audit.")

    # ------------------------------------------------------------------
    # Tree helpers
    # ------------------------------------------------------------------

    def _populate_tree(self, findings: list[Finding]) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        for f in findings:
            self._tree.insert(
                "", tk.END,
                values=(f.severity.value, f.rule, f.location, f.text),
                tags=(f.severity.value,),
            )

    _sort_reverse: dict[str, bool] = {}

    def _sort_tree(self, col: str) -> None:
        rows = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children("")]
        rev = self._sort_reverse.get(col, False)
        rows.sort(key=lambda x: x[0], reverse=rev)
        for idx, (_, iid) in enumerate(rows):
            self._tree.move(iid, "", idx)
        self._sort_reverse[col] = not rev

    def _on_select(self, _event: tk.Event) -> None:
        sel = self._tree.selection()
        if not sel or self._current_report is None:
            return
        vals = self._tree.item(sel[0], "values")
        sev_str, rule_name, location, snippet = vals

        # Find matching Finding
        for f in self._current_report.findings:
            if f.rule == rule_name and f.location == location and f.text == snippet:
                self._show_detail(f)
                self._status_var.set(f"[{f.severity.value}] {f.rule} — {f.location}")
                break

    def _show_detail(self, f: Finding) -> None:
        detail = (
            f"Rule:       {f.rule}\n"
            f"Severity:   {f.severity.value}\n"
            f"Location:   {f.location}\n"
            f"Snippet:    {f.text!r}\n\n"
            f"Suggestion:\n{f.suggestion}\n"
        )
        self._set_detail(detail)
        self._right_nb.select(0)

    # ------------------------------------------------------------------
    # Report helpers
    # ------------------------------------------------------------------

    def _refresh_report(self) -> None:
        if self._current_report is None:
            return
        fmt = self._fmt_var.get()
        if fmt == "json":
            content = self._current_report.to_json()
        elif fmt == "markdown":
            content = self._current_report.to_markdown()
        else:
            content = self._current_report.to_text()
        self._set_report(content)

    def _set_detail(self, text: str) -> None:
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert("1.0", text)
        self._detail_text.config(state=tk.DISABLED)

    def _set_report(self, text: str) -> None:
        self._report_text.config(state=tk.NORMAL)
        self._report_text.delete("1.0", tk.END)
        self._report_text.insert("1.0", text)
        self._report_text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _export(self, ext: str, content_fn) -> None:
        if self._current_report is None:
            messagebox.showinfo("No report", "Run an audit first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(ext.lstrip(".").upper(), f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            pathlib.Path(path).write_text(content_fn(), encoding="utf-8")
            self._status_var.set(f"Exported: {path}")
        except OSError as exc:
            messagebox.showerror("Export error", str(exc))

    def _export_markdown(self) -> None:
        self._export(".md",   lambda: self._current_report.to_markdown())

    def _export_json(self) -> None:
        self._export(".json", lambda: self._current_report.to_json())

    def _export_text(self) -> None:
        self._export(".txt",  lambda: self._current_report.to_text())

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _show_rules(self) -> None:
        _RulesDialog(self.root)

    def _show_about(self) -> None:
        from stataudit import __version__
        messagebox.showinfo(
            "About stataudit",
            f"stataudit  v{__version__}\n\n"
            "Automated statistical reporting auditor for academic manuscripts.\n\n"
            "Detects missing confidence intervals, incomplete significance-test\n"
            "reporting, over-precise p-values, and other common errors.\n\n"
            "MIT License — Vaibhav Deshmukh",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the stataudit GUI."""
    root = tk.Tk()

    # Apply a modern ttk theme when available
    style = ttk.Style(root)
    for theme in ("clam", "alt", "default"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    app = StatAuditApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
