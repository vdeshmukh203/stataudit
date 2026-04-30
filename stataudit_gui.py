#!/usr/bin/env python3
"""
stataudit_gui.py — Graphical interface for the stataudit statistical auditor.

Requires only the Python standard library (tkinter + stataudit.py in the
same directory or on PYTHONPATH).

Launch:
    python stataudit_gui.py
    stataudit-gui           # after pip install
"""
from __future__ import annotations

import pathlib
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Ensure stataudit.py is importable from the same directory as this file.
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from stataudit import (  # noqa: E402
    AuditReport,
    Finding,
    Severity,
    __version__,
    audit_text,
)

# ---------------------------------------------------------------------------
# Colour palette (foreground, background) per severity
# ---------------------------------------------------------------------------
_SEV_STYLE = {
    "ERROR":   {"fg": "#922b21", "bg": "#fadbd8"},
    "WARNING": {"fg": "#784212", "bg": "#fef9e7"},
    "INFO":    {"fg": "#1a5276", "bg": "#d6eaf8"},
}

_FILETYPES = [
    ("Text files", "*.txt"),
    ("Markdown", "*.md"),
    ("All files", "*.*"),
]


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class StatAuditApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"stataudit {__version__} — Statistical Reporting Auditor")
        self.geometry("960x700")
        self.minsize(720, 520)
        self._last_report: AuditReport | None = None
        self._build_menu()
        self._build_toolbar()
        self._build_panes()
        self._build_statusbar()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = tk.Menu(self)

        fm = tk.Menu(mb, tearoff=False)
        fm.add_command(label="Open File…",   command=self._open_file,    accelerator="Ctrl+O")
        fm.add_separator()
        fm.add_command(label="Save Report…", command=self._save_report,  accelerator="Ctrl+S")
        fm.add_separator()
        fm.add_command(label="Quit",          command=self.quit,          accelerator="Ctrl+Q")
        mb.add_cascade(label="File", menu=fm)

        em = tk.Menu(mb, tearoff=False)
        em.add_command(label="Copy findings", command=self._copy_findings, accelerator="Ctrl+C")
        em.add_command(label="Clear all",     command=self._clear,         accelerator="Ctrl+L")
        mb.add_cascade(label="Edit", menu=em)

        hm = tk.Menu(mb, tearoff=False)
        hm.add_command(label="List rules",  command=self._show_rules)
        hm.add_separator()
        hm.add_command(label="About",       command=self._show_about)
        mb.add_cascade(label="Help", menu=hm)

        self.configure(menu=mb)
        self.bind_all("<Control-o>", lambda _e: self._open_file())
        self.bind_all("<Control-s>", lambda _e: self._save_report())
        self.bind_all("<Control-q>", lambda _e: self.quit())
        self.bind_all("<Control-l>", lambda _e: self._clear())
        self.bind_all("<Return>",    lambda _e: None)   # prevent accidental trigger

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self, padding=(6, 4))
        bar.pack(fill="x")

        ttk.Button(bar, text="Open File…", command=self._open_file).pack(side="left", padx=2)

        self._filepath_var = tk.StringVar()
        ttk.Entry(
            bar, textvariable=self._filepath_var, width=38, state="readonly"
        ).pack(side="left", padx=4)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Label(bar, text="Min severity:").pack(side="left")
        self._sev_var = tk.StringVar(value="INFO")
        ttk.Combobox(
            bar,
            textvariable=self._sev_var,
            values=["INFO", "WARNING", "ERROR"],
            width=9,
            state="readonly",
        ).pack(side="left", padx=4)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(bar, text="▶  Audit", command=self._run_audit).pack(side="left", padx=2)
        ttk.Button(bar, text="Clear",   command=self._clear).pack(side="left", padx=2)
        ttk.Button(bar, text="Save Report…", command=self._save_report).pack(side="left", padx=2)

    def _build_panes(self) -> None:
        pw = ttk.PanedWindow(self, orient="vertical")
        pw.pack(fill="both", expand=True, padx=6, pady=4)

        # Input panel
        top = ttk.LabelFrame(pw, text="Input (paste text, or open a file above)", padding=4)
        self._input = scrolledtext.ScrolledText(
            top, height=10, wrap="word", font=("TkFixedFont", 10), undo=True
        )
        self._input.pack(fill="both", expand=True)
        pw.add(top, weight=1)

        # Results panel
        bot = ttk.LabelFrame(pw, text="Audit findings", padding=4)
        self._results = scrolledtext.ScrolledText(
            bot, height=18, wrap="word", font=("TkFixedFont", 10), state="disabled"
        )
        self._results.tag_configure("HEADER",  font=("TkFixedFont", 11, "bold"))
        self._results.tag_configure("SECTION", font=("TkFixedFont", 10, "bold"))
        self._results.tag_configure("RULE",    font=("TkFixedFont", 10, "bold underline"))
        self._results.tag_configure("OK",      foreground="#1d8348")
        for sev, styles in _SEV_STYLE.items():
            self._results.tag_configure(sev, foreground=styles["fg"], background=styles["bg"])
        self._results.pack(fill="both", expand=True)
        pw.add(bot, weight=2)

    def _build_statusbar(self) -> None:
        self._status = tk.StringVar(value="Ready — paste text or open a file, then click Audit.")
        ttk.Label(
            self,
            textvariable=self._status,
            anchor="w",
            relief="sunken",
            padding=(6, 2),
        ).pack(fill="x", side="bottom")

    # ── Actions ───────────────────────────────────────────────────────────

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(title="Open manuscript", filetypes=_FILETYPES)
        if not path:
            return
        try:
            content = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Cannot read file", str(exc))
            return
        self._input.delete("1.0", "end")
        self._input.insert("1.0", content)
        self._filepath_var.set(path)
        self._status.set(f"Loaded: {path}")

    def _run_audit(self) -> None:
        text = self._input.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No input", "Paste text or load a file before auditing.")
            return

        min_sev = Severity(self._sev_var.get())
        self._status.set("Auditing…")
        self.update_idletasks()

        source = self._filepath_var.get() or "<pasted text>"
        findings = audit_text(text, min_sev)
        report = AuditReport(source=source, findings=findings)
        self._last_report = report
        self._render_report(report)

        s = report.summary["by_severity"]
        self._status.set(
            f"Done — {len(findings)} finding(s): "
            f"{s['ERROR']} error  ·  {s['WARNING']} warning  ·  {s['INFO']} info"
        )

    def _render_report(self, report: AuditReport) -> None:
        w = self._results
        w.configure(state="normal")
        w.delete("1.0", "end")

        s = report.summary["by_severity"]
        w.insert("end", "Statistical Audit Report\n", "HEADER")
        w.insert("end", f"Source  : {report.source}\n")
        w.insert(
            "end",
            f"Totals  : {len(report.findings)} finding(s)   "
            f"[{s['ERROR']} ERROR  ·  {s['WARNING']} WARNING  ·  {s['INFO']} INFO]\n\n",
        )

        if not report.findings:
            w.insert("end", "✓  No findings — all checked rules passed.\n", "OK")
        else:
            for sev in ("ERROR", "WARNING", "INFO"):
                group = [f for f in report.findings if f.severity.value == sev]
                if not group:
                    continue
                bar = "─" * 44
                w.insert("end", f"── {sev} ({len(group)}) {bar}\n", sev)
                for finding in group:
                    w.insert("end", f"\n  Rule       : {finding.rule}\n", "RULE")
                    w.insert("end", f"  Location   : {finding.location}\n")
                    w.insert("end", f"  Text       : {finding.text!r}\n")
                    w.insert("end", f"  Suggestion : {finding.suggestion}\n")
                w.insert("end", "\n")

        w.configure(state="disabled")

    def _save_report(self) -> None:
        if self._last_report is None:
            messagebox.showinfo("Nothing to save", "Run an audit first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save report",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("Markdown", "*.md"), ("JSON", "*.json")],
        )
        if not path:
            return
        p = pathlib.Path(path)
        ext = p.suffix.lower()
        if ext == ".json":
            content = self._last_report.to_json()
        elif ext == ".md":
            content = self._last_report.to_markdown()
        else:
            content = self._last_report.to_text()
        try:
            p.write_text(content, encoding="utf-8")
            self._status.set(f"Report saved: {path}")
        except OSError as exc:
            messagebox.showerror("Cannot save file", str(exc))

    def _copy_findings(self) -> None:
        if self._last_report is None:
            return
        self.clipboard_clear()
        self.clipboard_append(self._last_report.to_text())
        self._status.set("Findings copied to clipboard.")

    def _clear(self) -> None:
        self._input.delete("1.0", "end")
        self._results.configure(state="normal")
        self._results.delete("1.0", "end")
        self._results.configure(state="disabled")
        self._filepath_var.set("")
        self._last_report = None
        self._status.set("Cleared — ready for new input.")

    def _show_rules(self) -> None:
        from stataudit import _RULES

        win = tk.Toplevel(self)
        win.title("Detection rules")
        win.geometry("780x460")

        cols = ("Rule", "Severity", "Suggestion")
        tv = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
        tv.heading("Rule",       text="Rule",       anchor="w")
        tv.heading("Severity",   text="Severity",   anchor="w")
        tv.heading("Suggestion", text="Suggestion", anchor="w")
        tv.column("Rule",       width=200, stretch=False)
        tv.column("Severity",   width=80,  stretch=False)
        tv.column("Suggestion", width=480)

        for sev, styles in _SEV_STYLE.items():
            tv.tag_configure(sev, foreground=styles["fg"], background=styles["bg"])

        for name, _pat, sev, suggestion in _RULES:
            tv.insert("", "end", values=(name, sev.value, suggestion), tags=(sev.value,))

        sb = ttk.Scrollbar(win, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About stataudit",
            f"stataudit  {__version__}\n\n"
            "Automated statistical reporting auditor for scientific manuscripts.\n\n"
            "Checks p-values, confidence intervals, effect sizes, degrees of\n"
            "freedom, sample size, and other reporting quality indicators\n"
            "against APA and reproducibility-checklist guidelines.\n\n"
            "MIT License — Vaibhav Deshmukh",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the stataudit GUI application."""
    app = StatAuditApp()
    app.mainloop()


if __name__ == "__main__":
    main()
