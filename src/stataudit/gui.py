"""Tkinter graphical interface for stataudit."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .auditor import RULES, audit_file, audit_text
from .report import AuditReport, Severity

_SEV_COLOR = {
    "ERROR": "#c0392b",
    "WARNING": "#e67e22",
    "INFO": "#2980b9",
}

_FONT_MONO = ("Courier New", 10)
_FONT_MONO_BOLD = ("Courier New", 10, "bold")


class _RulesWindow(tk.Toplevel):
    """Floating window listing all detection rules."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Detection Rules")
        self.geometry("780x460")
        self.resizable(True, True)

        cols = ("Rule", "Severity", "Suggestion")
        tree = ttk.Treeview(self, columns=cols, show="headings")
        tree.heading("Rule", text="Rule")
        tree.heading("Severity", text="Severity")
        tree.heading("Suggestion", text="Suggestion")
        tree.column("Rule", width=200, anchor="w")
        tree.column("Severity", width=80, anchor="center")
        tree.column("Suggestion", width=460, anchor="w")

        sb = ttk.Scrollbar(self, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)

        for name, _, sev, suggestion in RULES:
            tree.insert("", "end", values=(name, sev.value, suggestion))

        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")


class StatAuditApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("stataudit — Statistical Reporting Auditor")
        self.geometry("960x720")
        self.minsize(700, 500)
        self._current_file: str | None = None
        self._last_report: AuditReport | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_toolbar()
        self._build_panes()
        self._build_statusbar()

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self, padding=(4, 3))
        bar.pack(fill="x", side="top")

        ttk.Button(bar, text="Open File…", command=self._open_file).pack(side="left", padx=2)
        ttk.Button(bar, text="Run Audit", command=self._run_audit).pack(side="left", padx=2)
        ttk.Button(bar, text="Clear", command=self._clear).pack(side="left", padx=2)
        ttk.Button(bar, text="Save Report…", command=self._save_report).pack(side="left", padx=2)
        ttk.Button(bar, text="List Rules", command=self._show_rules).pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(bar, text="Min severity:").pack(side="left")
        self._min_sev = tk.StringVar(value="INFO")
        ttk.Combobox(
            bar,
            textvariable=self._min_sev,
            values=["INFO", "WARNING", "ERROR"],
            width=9,
            state="readonly",
        ).pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Format:").pack(side="left")
        self._fmt = tk.StringVar(value="text")
        ttk.Combobox(
            bar,
            textvariable=self._fmt,
            values=["text", "markdown", "json", "html"],
            width=9,
            state="readonly",
        ).pack(side="left", padx=2)

    def _build_panes(self) -> None:
        paned = ttk.PanedWindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        in_frame = ttk.LabelFrame(paned, text="Input text (paste or open a file)", padding=4)
        paned.add(in_frame, weight=1)
        self._input = scrolledtext.ScrolledText(in_frame, wrap="word", font=_FONT_MONO, undo=True)
        self._input.pack(fill="both", expand=True)

        out_frame = ttk.LabelFrame(paned, text="Audit results", padding=4)
        paned.add(out_frame, weight=1)
        self._output = scrolledtext.ScrolledText(
            out_frame, wrap="word", font=_FONT_MONO, state="disabled"
        )
        self._output.pack(fill="both", expand=True)

        for sev, col in _SEV_COLOR.items():
            self._output.tag_configure(sev, foreground=col, font=_FONT_MONO_BOLD)
        self._output.tag_configure("header", font=("Courier New", 10, "underline"))

    def _build_statusbar(self) -> None:
        self._status = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(self, textvariable=self._status, anchor="w", relief="sunken")
        status_bar.pack(fill="x", side="bottom", padx=0, pady=0)

    # ── actions ───────────────────────────────────────────────────────────────

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open text file",
            filetypes=[
                ("Text / Markdown / LaTeX", "*.txt *.md *.tex *.rst"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            messagebox.showerror("Cannot open file", str(exc))
            return
        self._current_file = path
        self._input.delete("1.0", "end")
        self._input.insert("1.0", text)
        self._status.set(f"Loaded: {path}")

    def _run_audit(self) -> None:
        text = self._input.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No input", "Paste or open a text file before running.")
            return

        min_sev = Severity(self._min_sev.get())

        if self._current_file and Path(self._current_file).is_file():
            findings = audit_file(Path(self._current_file), min_sev)
            source = self._current_file
        else:
            findings = audit_text(text, min_sev)
            source = "<pasted text>"

        self._last_report = AuditReport(source=source, findings=findings)
        self._display_report(self._last_report)
        n = len(findings)
        self._status.set(f"Audit complete — {n} finding{'s' if n != 1 else ''}.")

    def _display_report(self, report: AuditReport) -> None:
        self._output.config(state="normal")
        self._output.delete("1.0", "end")

        fmt = self._fmt.get()
        if fmt == "text":
            self._display_coloured(report)
        elif fmt == "json":
            self._output.insert("end", report.to_json())
        elif fmt == "markdown":
            self._output.insert("end", report.to_markdown())
        else:
            self._output.insert("end", report.to_html())

        self._output.config(state="disabled")

    def _display_coloured(self, report: AuditReport) -> None:
        s = report.summary["by_severity"]
        self._output.insert(
            "end",
            f"Source : {report.source}\n"
            f"Findings: {len(report.findings)}  "
            f"(ERROR {s['ERROR']}  WARNING {s['WARNING']}  INFO {s['INFO']})\n",
            "header",
        )
        self._output.insert("end", "\n")

        if not report.findings:
            self._output.insert("end", "No findings.\n")
            return

        for f in report.findings:
            self._output.insert("end", f"[{f.severity.value}] ", f.severity.value)
            self._output.insert(
                "end",
                f"{f.rule}\n"
                f"  Location  : {f.location}\n"
                f"  Text      : {f.text!r}\n"
                f"  Suggestion: {f.suggestion}\n\n",
            )

    def _save_report(self) -> None:
        if self._last_report is None:
            messagebox.showwarning("No report", "Run an audit first.")
            return
        fmt = self._fmt.get()
        ext = {"text": ".txt", "markdown": ".md", "json": ".json", "html": ".html"}[fmt]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{fmt.upper()} file", f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return
        self._last_report.save(path, fmt=fmt)
        self._status.set(f"Report saved: {path}")

    def _show_rules(self) -> None:
        _RulesWindow(self)

    def _clear(self) -> None:
        self._input.delete("1.0", "end")
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.config(state="disabled")
        self._current_file = None
        self._last_report = None
        self._status.set("Ready.")


def main() -> None:
    """Launch the stataudit graphical interface."""
    try:
        app = StatAuditApp()
        app.mainloop()
    except tk.TclError as exc:
        print(f"stataudit-gui: cannot start GUI: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
