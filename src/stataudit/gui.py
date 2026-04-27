"""
Graphical user interface for stataudit.

Launch with the ``stataudit-gui`` command (after installation) or via::

    python -m stataudit.gui

Requires :mod:`tkinter`, which is bundled with standard CPython installers.
On Debian/Ubuntu it can be installed separately with
``sudo apt-get install python3-tk``.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List, Optional

from .core import AuditReport, Finding, Severity, audit_file, audit_text

# Severity → foreground / background colours for the findings table.
_FG: dict = {"ERROR": "#b71c1c", "WARNING": "#e65100", "INFO": "#0d47a1"}
_BG: dict = {"ERROR": "#ffebee", "WARNING": "#fff8e1", "INFO": "#e8f5e9"}


class _DetailWindow(tk.Toplevel):
    """Pop-up showing the full details of one finding."""

    def __init__(self, parent: tk.Widget, finding_vals: tuple) -> None:
        super().__init__(parent)
        sev, rule, loc, text, suggestion = finding_vals
        self.title(f"Finding — {rule}")
        self.resizable(True, True)
        self.minsize(480, 280)

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        def _row(label: str, value: str, wrap: bool = True) -> None:
            ttk.Label(outer, text=label, font=("TkDefaultFont", 10, "bold")).pack(
                anchor="w", pady=(6, 0)
            )
            if wrap:
                ttk.Label(outer, text=value, wraplength=460).pack(
                    anchor="w", padx=10, pady=(0, 2)
                )
            else:
                box = scrolledtext.ScrolledText(
                    outer, height=3, wrap=tk.WORD, font=("Courier", 10)
                )
                box.insert("1.0", value)
                box.configure(state="disabled")
                box.pack(fill="x", padx=10, pady=(0, 4))

        _row("Rule:", rule)
        _row("Severity:", sev)
        _row("Location:", loc)
        _row("Matched text:", text, wrap=False)
        _row("Suggestion:", suggestion)

        ttk.Button(outer, text="Close", command=self.destroy).pack(pady=(10, 0))


class StatAuditApp(tk.Tk):
    """Main application window for the stataudit GUI.

    Provides:

    * File-browser or paste-text input
    * Minimum-severity selector
    * Colour-coded, sortable findings table
    * Double-click detail pop-up
    * Export to plain text, JSON, or Markdown
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("StatAudit — Statistical Reporting Auditor")
        self.minsize(960, 580)
        self._report: Optional[AuditReport] = None
        self._sort_reverse: dict = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)  # findings table expands

        # Row 0 — file input bar
        top = ttk.Frame(self, padding=(8, 8, 8, 4))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Input file:").grid(row=0, column=0, sticky="w")
        self._file_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._file_var).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(top, text="Browse…", command=self._browse).grid(row=0, column=2)
        ttk.Label(top, text="Min. severity:").grid(
            row=0, column=3, padx=(14, 4), sticky="w"
        )
        self._sev_var = tk.StringVar(value="INFO")
        ttk.Combobox(
            top,
            textvariable=self._sev_var,
            values=["INFO", "WARNING", "ERROR"],
            width=10,
            state="readonly",
        ).grid(row=0, column=4)
        ttk.Button(top, text="Run Audit ▶", command=self._run).grid(
            row=0, column=5, padx=(14, 0)
        )

        # Row 1 — paste-text toggle
        toggle_bar = ttk.Frame(self, padding=(8, 0, 8, 2))
        toggle_bar.grid(row=1, column=0, sticky="ew")
        self._use_paste = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toggle_bar,
            text="Paste text directly instead of selecting a file",
            variable=self._use_paste,
            command=self._toggle_paste,
        ).pack(side="left")

        # Row 2 — paste text area (hidden by default)
        self._paste_frame = ttk.LabelFrame(self, text="Text to audit", padding=4)
        self._paste_frame.grid(
            row=2, column=0, sticky="nsew", padx=8, pady=(0, 4)
        )
        self._paste_frame.columnconfigure(0, weight=1)
        self._paste_area = scrolledtext.ScrolledText(
            self._paste_frame, height=7, wrap=tk.WORD, font=("Courier", 10)
        )
        self._paste_area.pack(fill="both", expand=True)
        self._paste_frame.grid_remove()

        # Row 3 — summary bar
        self._summary_var = tk.StringVar(value="No audit run yet.")
        summary_bar = ttk.Frame(self, padding=(8, 4))
        summary_bar.grid(row=3, column=0, sticky="ew")
        ttk.Label(
            summary_bar,
            textvariable=self._summary_var,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")

        # Row 4 — findings table
        tbl_frame = ttk.Frame(self, padding=(8, 0, 8, 0))
        tbl_frame.grid(row=4, column=0, sticky="nsew")
        tbl_frame.columnconfigure(0, weight=1)
        tbl_frame.rowconfigure(0, weight=1)

        cols = ("Severity", "Rule", "Location", "Text", "Suggestion")
        self._tree = ttk.Treeview(
            tbl_frame, columns=cols, show="headings", selectmode="browse"
        )
        widths = {"Severity": 80, "Rule": 170, "Location": 90, "Text": 260, "Suggestion": 340}
        for col in cols:
            self._tree.heading(
                col, text=col, command=lambda c=col: self._sort_column(c)
            )
            self._tree.column(
                col,
                width=widths[col],
                anchor="center" if col in ("Severity", "Location") else "w",
            )

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for sev in ("ERROR", "WARNING", "INFO"):
            self._tree.tag_configure(sev, foreground=_FG[sev], background=_BG[sev])

        self._tree.bind("<Double-1>", self._show_detail)

        # Row 5 — export / clear bar
        export_bar = ttk.Frame(self, padding=(8, 6, 8, 8))
        export_bar.grid(row=5, column=0, sticky="ew")
        ttk.Label(export_bar, text="Export:").pack(side="left")
        for fmt in ("Text", "JSON", "Markdown"):
            ttk.Button(
                export_bar,
                text=fmt,
                command=lambda f=fmt.lower(): self._export(f),
            ).pack(side="left", padx=4)
        ttk.Button(export_bar, text="Clear", command=self._clear).pack(side="right")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _toggle_paste(self) -> None:
        if self._use_paste.get():
            self._paste_frame.grid()
        else:
            self._paste_frame.grid_remove()

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a text file to audit",
            filetypes=[
                ("Text / LaTeX / Markdown", "*.txt *.tex *.md *.rst"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._file_var.set(path)
            self._use_paste.set(False)
            self._toggle_paste()

    def _run(self) -> None:
        min_sev = Severity(self._sev_var.get())

        if self._use_paste.get():
            text = self._paste_area.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning(
                    "No input", "Paste some text before running the audit."
                )
                return
            report = AuditReport(
                source="<pasted text>",
                findings=audit_text(text, min_sev),
            )
        else:
            path_str = self._file_var.get().strip()
            if not path_str:
                messagebox.showwarning(
                    "No input",
                    "Select a file or enable 'Paste text' mode before running.",
                )
                return
            try:
                findings = audit_file(Path(path_str), min_sev)
            except FileNotFoundError as exc:
                messagebox.showerror("File not found", str(exc))
                return
            report = AuditReport(source=path_str, findings=findings)

        self._report = report
        self._populate_table(report.findings)
        s = report.summary["by_severity"]
        self._summary_var.set(
            f"Source: {report.source}  │  "
            f"Total: {len(report.findings)}  "
            f"(ERROR {s['ERROR']}  WARNING {s['WARNING']}  INFO {s['INFO']})"
        )

    def _populate_table(self, findings: List[Finding]) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        for f in findings:
            self._tree.insert(
                "",
                "end",
                values=(f.severity.value, f.rule, f.location, f.text, f.suggestion),
                tags=(f.severity.value,),
            )

    def _sort_column(self, col: str) -> None:
        reverse = self._sort_reverse.get(col, False)
        rows = [
            (self._tree.set(iid, col), iid)
            for iid in self._tree.get_children("")
        ]
        rows.sort(reverse=reverse)
        for idx, (_, iid) in enumerate(rows):
            self._tree.move(iid, "", idx)
        self._sort_reverse[col] = not reverse

    def _show_detail(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0], "values")
        if vals:
            _DetailWindow(self, vals)

    def _export(self, fmt: str) -> None:
        if self._report is None:
            messagebox.showinfo("Nothing to export", "Run an audit first.")
            return
        ext = {"text": ".txt", "json": ".json", "markdown": ".md"}[fmt]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(fmt.capitalize(), f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return
        content = (
            self._report.to_json()
            if fmt == "json"
            else self._report.to_markdown()
            if fmt == "markdown"
            else self._report.to_text()
        )
        Path(path).write_text(content, encoding="utf-8")
        messagebox.showinfo("Saved", f"Report saved to:\n{path}")

    def _clear(self) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._report = None
        self._summary_var.set("No audit run yet.")
        self._file_var.set("")
        self._paste_area.delete("1.0", "end")


def main() -> None:
    """Launch the stataudit graphical user interface.

    Exits with a helpful message if :mod:`tkinter` is not available.
    """
    try:
        import tkinter  # noqa: F401  – validate availability
    except ImportError:
        print(
            "tkinter is required for the GUI but could not be imported.\n"
            "  Debian/Ubuntu : sudo apt-get install python3-tk\n"
            "  macOS/Windows : tkinter is bundled with standard Python.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app = StatAuditApp()
    app.mainloop()


if __name__ == "__main__":
    main()
