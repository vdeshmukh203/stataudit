"""
Tkinter GUI for stataudit.

Launch via:
    stataudit gui
    python -m stataudit.gui
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from typing import List, Optional

from .auditor import audit_text, audit_file
from .report import AuditReport, Finding, Severity
from .rules import RULES

_SEV_FG = {
    Severity.ERROR: "#c0392b",
    Severity.WARNING: "#d35400",
    Severity.INFO: "#2471a3",
}

_SAMPLE = (
    "The treatment group showed statistically significant improvement "
    "(t = 3.45, p = .0000234).  Results were ns for the control condition.  "
    "We performed a regression analysis.  N = 12 participants completed all "
    "sessions.  The confidence interval was [0.12, 0.45].  One-tailed tests "
    "were used for the primary hypothesis.  Outliers were removed prior to "
    "analysis.  Missing data were handled via listwise deletion."
)


class _App:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("stataudit — Statistical Reporting Auditor")
        root.geometry("1150x700")
        root.minsize(820, 520)

        self._report: Optional[AuditReport] = None
        self._all_findings: List[Finding] = []

        self._build_menu()
        self._build_toolbar()
        self._build_panes()
        self._build_statusbar()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=False)
        fm.add_command(label="Open file…\tCtrl+O", command=self._open_file)
        fm.add_separator()
        fm.add_command(label="Export report…", command=self._export)
        fm.add_separator()
        fm.add_command(label="Quit\tCtrl+Q", command=self.root.quit)
        mb.add_cascade(label="File", menu=fm)

        hm = tk.Menu(mb, tearoff=False)
        hm.add_command(label="List all rules", command=self._show_rules)
        hm.add_command(label="About", command=self._show_about)
        mb.add_cascade(label="Help", menu=hm)

        self.root.config(menu=mb)
        self.root.bind_all("<Control-o>", lambda _e: self._open_file())
        self.root.bind_all("<Control-q>", lambda _e: self.root.quit())

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(4, 3))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(bar, text="Open File…", command=self._open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="▶ Run Audit", command=self._run).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Export…", command=self._export).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)

        ttk.Label(bar, text="Min severity:").pack(side=tk.LEFT)
        self._sev_var = tk.StringVar(value="INFO")
        ttk.Combobox(
            bar,
            textvariable=self._sev_var,
            values=["INFO", "WARNING", "ERROR"],
            width=9,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)

    def _build_panes(self) -> None:
        pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ---- Left: text editor -----------------------------------------
        left = ttk.LabelFrame(pw, text="Input Text", padding=4)
        pw.add(left, weight=1)

        self._editor = scrolledtext.ScrolledText(
            left, wrap=tk.WORD, font=("Courier", 11), undo=True,
        )
        self._editor.pack(fill=tk.BOTH, expand=True)
        self._editor.insert(tk.END, _SAMPLE)

        # ---- Right: findings panel -------------------------------------
        right = ttk.LabelFrame(pw, text="Findings", padding=4)
        pw.add(right, weight=1)
        self._build_findings_panel(right)

    def _build_findings_panel(self, parent: ttk.LabelFrame) -> None:
        # Summary label
        self._summary_var = tk.StringVar(value="")
        ttk.Label(
            parent, textvariable=self._summary_var, font=("TkDefaultFont", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 2))

        # Filter radio buttons
        fbar = ttk.Frame(parent)
        fbar.pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(fbar, text="Show:").pack(side=tk.LEFT)
        self._filter_var = tk.StringVar(value="ALL")
        for val in ("ALL", "ERROR", "WARNING", "INFO"):
            ttk.Radiobutton(
                fbar,
                text=val,
                variable=self._filter_var,
                value=val,
                command=self._apply_filter,
            ).pack(side=tk.LEFT, padx=3)

        # Treeview + scrollbar
        cols = ("severity", "rule", "location", "snippet")
        self._tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")

        col_cfg = [
            ("severity", "Severity", 80, False),
            ("rule", "Rule", 190, True),
            ("location", "Location", 80, False),
            ("snippet", "Snippet", 260, True),
        ]
        for cid, heading, width, stretch in col_cfg:
            self._tree.heading(cid, text=heading, command=lambda c=cid: self._sort(c))
            self._tree.column(cid, width=width, minwidth=60, stretch=stretch)

        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        for sev in Severity:
            self._tree.tag_configure(sev.value, foreground=_SEV_FG[sev])

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail / suggestion box
        detail_frame = ttk.LabelFrame(parent, text="Suggestion", padding=4)
        detail_frame.pack(fill=tk.X, pady=(4, 0))
        self._detail = tk.Text(
            detail_frame, height=3, wrap=tk.WORD, state=tk.DISABLED,
            font=("TkDefaultFont", 10),
        )
        self._detail.pack(fill=tk.X)

    def _build_statusbar(self) -> None:
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self.root,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(4, 1),
        ).pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open manuscript",
            filetypes=[
                ("Text / Markdown", "*.txt *.md *.rst"),
                ("All files", "*"),
            ],
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Error", str(exc))
            return
        self._editor.delete("1.0", tk.END)
        self._editor.insert(tk.END, content)
        self._run(source=path)

    def _run(self, source: str = "<editor>") -> None:
        text = self._editor.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("stataudit", "Enter or open some text first.")
            return
        min_sev = Severity(self._sev_var.get())
        findings = audit_text(text, min_sev)
        self._all_findings = findings
        self._report = AuditReport(source=source, findings=findings)
        self._populate_tree(findings)
        s = self._report.summary["by_severity"]
        self._summary_var.set(
            f"Total: {len(findings)}  ·  "
            f"ERROR {s['ERROR']}  WARNING {s['WARNING']}  INFO {s['INFO']}"
        )
        self._status_var.set(f"Audit complete — {len(findings)} finding(s).")

    def _clear(self) -> None:
        self._editor.delete("1.0", tk.END)
        self._tree.delete(*self._tree.get_children())
        self._summary_var.set("")
        self._status_var.set("Ready.")
        self._report = None
        self._all_findings = []
        self._set_detail("")

    def _export(self) -> None:
        if not self._report:
            messagebox.showinfo("stataudit", "Run an audit first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save report",
            defaultextension=".html",
            filetypes=[
                ("HTML report", "*.html"),
                ("Markdown", "*.md"),
                ("JSON", "*.json"),
                ("Plain text", "*.txt"),
            ],
        )
        if not path:
            return
        ext = Path(path).suffix.lower()
        content = {
            ".html": self._report.to_html,
            ".md": self._report.to_markdown,
            ".json": self._report.to_json,
        }.get(ext, self._report.to_text)()
        try:
            Path(path).write_text(content, encoding="utf-8")
            self._status_var.set(f"Saved → {path}")
        except OSError as exc:
            messagebox.showerror("Error", str(exc))

    # ------------------------------------------------------------------
    # Tree helpers
    # ------------------------------------------------------------------

    def _populate_tree(self, findings: List[Finding]) -> None:
        self._tree.delete(*self._tree.get_children())
        flt = self._filter_var.get()
        for f in findings:
            if flt != "ALL" and f.severity.value != flt:
                continue
            self._tree.insert(
                "",
                tk.END,
                values=(f.severity.value, f.rule, f.location, f.text),
                tags=(f.severity.value,),
            )
        self._set_detail("")

    def _apply_filter(self) -> None:
        self._populate_tree(self._all_findings)

    def _sort(self, col: str) -> None:
        items = [(self._tree.set(k, col), k) for k in self._tree.get_children("")]
        items.sort()
        for idx, (_, k) in enumerate(items):
            self._tree.move(k, "", idx)

    def _on_select(self, _event: tk.Event) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        rule_name = self._tree.set(sel[0], "rule")
        suggestion = next((s for n, _, _, s in RULES if n == rule_name), "")
        self._set_detail(suggestion)

    def _set_detail(self, text: str) -> None:
        self._detail.config(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)
        self._detail.insert(tk.END, text)
        self._detail.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _show_rules(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Detection Rules")
        win.geometry("820x420")
        cols = ("name", "severity", "suggestion")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("name", text="Rule")
        tree.heading("severity", text="Severity")
        tree.heading("suggestion", text="Suggestion")
        tree.column("name", width=210)
        tree.column("severity", width=80, stretch=False)
        tree.column("suggestion", width=520)
        vsb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        for name, _, sev, suggestion in RULES:
            tree.insert("", tk.END, values=(name, sev.value, suggestion), tags=(sev.value,))
        for sev in Severity:
            tree.tag_configure(sev.value, foreground=_SEV_FG[sev])

    def _show_about(self) -> None:
        from . import __version__
        messagebox.showinfo(
            "About stataudit",
            (
                f"stataudit  v{__version__}\n\n"
                "Statistical reporting auditor for academic manuscripts.\n\n"
                "Checks p-values, confidence intervals, effect sizes,\n"
                "degrees of freedom, sample sizes, and more.\n\n"
                "© Vaibhav Deshmukh — MIT License"
            ),
        )


def run_gui() -> None:
    """Entry point for the GUI."""
    root = tk.Tk()
    _App(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
