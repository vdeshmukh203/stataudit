"""AuditReport: container for a completed stataudit run."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from ._core import Finding, Severity


@dataclass
class AuditReport:
    """Container for audit findings produced by :class:`~stataudit.StatAuditor`.

    Attributes
    ----------
    source:
        Human-readable label for the audited input (file path or ``"<stdin>"``).
    findings:
        Ordered list of :class:`~stataudit._core.Finding` objects.
    """

    source: str
    findings: List[Finding] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    @property
    def summary(self) -> dict:
        """Return a counts dict keyed by severity and totals."""
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {
            "source": self.source,
            "total": len(self.findings),
            "by_severity": counts,
        }

    # ------------------------------------------------------------------
    # Output formatters
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        """Plain-text representation suitable for terminal output."""
        if not self.findings:
            return f"No findings for {self.source}."
        lines = [
            f"Audit report for: {self.source}",
            f"Total findings  : {len(self.findings)}",
            "",
        ]
        for f in self.findings:
            lines.append(str(f))
            lines.append("")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """GitHub-flavoured Markdown report."""
        s = self.summary["by_severity"]
        lines: List[str] = [
            "# Statistical Audit Report",
            "",
            f"**Source:** {self.source}",
            f"**Total findings:** {len(self.findings)}",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| ERROR    | {s['ERROR']} |",
            f"| WARNING  | {s['WARNING']} |",
            f"| INFO     | {s['INFO']} |",
            "",
        ]
        if not self.findings:
            lines.append("_No findings._")
            return "\n".join(lines)

        by_sev: dict = {"ERROR": [], "WARNING": [], "INFO": []}
        for f in self.findings:
            by_sev[f.severity.value].append(f)
        for sev in ("ERROR", "WARNING", "INFO"):
            group = by_sev[sev]
            if not group:
                continue
            lines += [f"## {sev}", ""]
            for f in group:
                lines += [
                    f"### `{f.rule}`",
                    f"- **Location:** {f.location}",
                    f"- **Text:** `{f.text}`",
                    f"- **Suggestion:** {f.suggestion}",
                    "",
                ]
        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """JSON representation of the full report."""
        return json.dumps(
            {
                "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings],
            },
            indent=indent,
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path, fmt: str = "text") -> None:
        """Write the report to *path* in the requested format.

        Parameters
        ----------
        path:
            Destination file.
        fmt:
            One of ``"text"``, ``"markdown"``, or ``"json"``.
        """
        formatters = {
            "text": self.to_text,
            "markdown": self.to_markdown,
            "json": self.to_json,
        }
        if fmt not in formatters:
            raise ValueError(f"Unknown format {fmt!r}; choose from {list(formatters)}")
        path = Path(path)
        path.write_text(formatters[fmt](), encoding="utf-8")

    def save_html(self, path: Path) -> None:
        """Write a styled HTML version of the report to *path*.

        This method generates a self-contained HTML file that can be opened
        in any browser without additional dependencies.
        """
        path = Path(path)
        path.write_text(self._to_html(), encoding="utf-8")

    def _to_html(self) -> str:
        s = self.summary["by_severity"]

        def _row(f: Finding) -> str:
            colour = {"ERROR": "#c0392b", "WARNING": "#e67e22", "INFO": "#2980b9"}[
                f.severity.value
            ]
            return (
                f"<tr>"
                f"<td style='color:{colour};font-weight:bold'>{f.severity.value}</td>"
                f"<td><code>{f.rule}</code></td>"
                f"<td>{f.location}</td>"
                f"<td><code>{f.text}</code></td>"
                f"<td>{f.suggestion}</td>"
                f"</tr>"
            )

        rows = "\n".join(_row(f) for f in self.findings) if self.findings else (
            "<tr><td colspan='5' style='text-align:center;color:#555'>No findings.</td></tr>"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>stataudit — {self.source}</title>
<style>
  body{{font-family:sans-serif;margin:2em;background:#fafafa;color:#222}}
  h1{{border-bottom:2px solid #333;padding-bottom:.3em}}
  .summary{{display:flex;gap:1.5em;margin:1em 0}}
  .badge{{padding:.4em .8em;border-radius:4px;font-weight:bold;color:#fff}}
  .ERROR{{background:#c0392b}}.WARNING{{background:#e67e22}}.INFO{{background:#2980b9}}
  table{{border-collapse:collapse;width:100%;margin-top:1em}}
  th{{background:#333;color:#fff;padding:.5em .8em;text-align:left}}
  td{{border:1px solid #ddd;padding:.5em .8em;vertical-align:top}}
  tr:nth-child(even){{background:#f0f0f0}}
</style>
</head>
<body>
<h1>Statistical Audit Report</h1>
<p><strong>Source:</strong> {self.source}</p>
<div class="summary">
  <span class="badge ERROR">ERROR: {s['ERROR']}</span>
  <span class="badge WARNING">WARNING: {s['WARNING']}</span>
  <span class="badge INFO">INFO: {s['INFO']}</span>
  <span>Total: {len(self.findings)}</span>
</div>
<table>
<thead><tr>
  <th>Severity</th><th>Rule</th><th>Location</th><th>Text</th><th>Suggestion</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>"""
