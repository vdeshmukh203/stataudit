"""Data classes for audit findings and reports."""

from __future__ import annotations

import json
import html as html_module
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List


class Severity(str, Enum):
    """Ordered severity levels for audit findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def _order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.value]

    def __le__(self, other: "Severity") -> bool:
        return self._order() <= other._order()

    def __lt__(self, other: "Severity") -> bool:
        return self._order() < other._order()

    def __gt__(self, other: "Severity") -> bool:
        return self._order() > other._order()

    def __ge__(self, other: "Severity") -> bool:
        return self._order() >= other._order()


@dataclass
class Finding:
    """A single statistical reporting issue detected in the source text."""

    rule: str
    text: str
    location: str
    severity: Severity
    suggestion: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    def __str__(self) -> str:
        return (
            f"[{self.severity.value}] {self.rule}\n"
            f"  Location  : {self.location}\n"
            f"  Text      : {self.text!r}\n"
            f"  Suggestion: {self.suggestion}"
        )


_SEV_COLOR: Dict[str, str] = {
    "ERROR": "#c0392b",
    "WARNING": "#e67e22",
    "INFO": "#2980b9",
}


@dataclass
class AuditReport:
    """Aggregated results of an audit run on a single document."""

    source: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        counts: Dict[str, int] = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {"source": self.source, "total": len(self.findings), "by_severity": counts}

    # ── output formats ────────────────────────────────────────────────────────

    def to_text(self) -> str:
        if not self.findings:
            return f"No findings for {self.source}."
        lines = [f"Audit report for: {self.source}", f"Total findings: {len(self.findings)}", ""]
        for f in self.findings:
            lines.append(str(f))
            lines.append("")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        s = self.summary["by_severity"]
        lines = [
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
        by_sev: Dict[str, List[Finding]] = {"ERROR": [], "WARNING": [], "INFO": []}
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
        return json.dumps(
            {"summary": self.summary, "findings": [f.to_dict() for f in self.findings]},
            indent=indent,
            ensure_ascii=False,
        )

    def to_html(self) -> str:
        s = self.summary["by_severity"]
        finding_rows = "".join(
            "<tr>"
            f"<td><span style='color:{_SEV_COLOR[f.severity.value]};font-weight:bold'>"
            f"{html_module.escape(f.severity.value)}</span></td>"
            f"<td><code>{html_module.escape(f.rule)}</code></td>"
            f"<td>{html_module.escape(f.location)}</td>"
            f"<td><code>{html_module.escape(f.text)}</code></td>"
            f"<td>{html_module.escape(f.suggestion)}</td>"
            "</tr>\n"
            for f in self.findings
        )
        findings_block = (
            "<p><em>No findings.</em></p>"
            if not self.findings
            else (
                "<table class='findings'>"
                "<tr><th>Severity</th><th>Rule</th><th>Location</th>"
                "<th>Text</th><th>Suggestion</th></tr>\n"
                + finding_rows
                + "</table>"
            )
        )
        src_esc = html_module.escape(self.source)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>stataudit — {src_esc}</title>
<style>
  body{{font-family:sans-serif;max-width:960px;margin:2em auto;padding:0 1.2em;color:#222}}
  h1{{border-bottom:2px solid #ddd;padding-bottom:.3em}}
  table.summary,table.findings{{border-collapse:collapse;margin-bottom:1em}}
  table.summary td,table.summary th,
  table.findings td,table.findings th{{border:1px solid #ccc;padding:.35em .7em;vertical-align:top}}
  table.findings th{{background:#f5f5f5;font-weight:600}}
  code{{background:#f0f0f0;padding:.1em .3em;border-radius:3px;font-size:.9em}}
</style>
</head>
<body>
<h1>Statistical Audit Report</h1>
<p><strong>Source:</strong> {src_esc}<br>
<strong>Total findings:</strong> {len(self.findings)}</p>
<table class="summary">
  <tr><th>Severity</th><th>Count</th></tr>
  <tr><td style="color:{_SEV_COLOR['ERROR']};font-weight:bold">ERROR</td><td>{s['ERROR']}</td></tr>
  <tr><td style="color:{_SEV_COLOR['WARNING']};font-weight:bold">WARNING</td><td>{s['WARNING']}</td></tr>
  <tr><td style="color:{_SEV_COLOR['INFO']};font-weight:bold">INFO</td><td>{s['INFO']}</td></tr>
</table>
<h2>Findings</h2>
{findings_block}
</body>
</html>
"""

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str, fmt: str = "text") -> None:
        """Write the report to *path* in the requested format."""
        formatters = {
            "text": self.to_text,
            "markdown": self.to_markdown,
            "json": self.to_json,
            "html": self.to_html,
        }
        if fmt not in formatters:
            raise ValueError(f"Unknown format {fmt!r}. Choose from: {list(formatters)}")
        Path(path).write_text(formatters[fmt](), encoding="utf-8")

    def save_html(self, path: str) -> None:
        """Convenience wrapper: write an HTML report to *path*."""
        self.save(path, fmt="html")
