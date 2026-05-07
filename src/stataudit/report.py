"""Data classes for audit findings and reports."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import List


class Severity(str, Enum):
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
            f"  Text      : {self.text!r}\n"
            f"  Location  : {self.location}\n"
            f"  Suggestion: {self.suggestion}"
        )


_SEV_COLOR = {"ERROR": "#c0392b", "WARNING": "#e67e22", "INFO": "#2980b9"}


@dataclass
class AuditReport:
    source: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {"source": self.source, "total": len(self.findings), "by_severity": counts}

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------

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
        return json.dumps(
            {"summary": self.summary, "findings": [f.to_dict() for f in self.findings]},
            indent=indent,
            ensure_ascii=False,
        )

    def to_html(self) -> str:
        s = self.summary["by_severity"]
        rows = ""
        for f in self.findings:
            color = _SEV_COLOR.get(f.severity.value, "#333")
            text_esc = f.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sug_esc = f.suggestion.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            rows += (
                f"<tr>"
                f"<td style='color:{color};font-weight:bold'>{f.severity.value}</td>"
                f"<td>{f.rule}</td>"
                f"<td>{f.location}</td>"
                f"<td><code>{text_esc}</code></td>"
                f"<td>{sug_esc}</td>"
                f"</tr>\n"
            )
        no_findings_row = (
            "" if rows else "<tr><td colspan='5'><em>No findings.</em></td></tr>\n"
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>stataudit report — {self.source}</title>
  <style>
    body {{font-family:sans-serif;max-width:1100px;margin:2em auto;color:#222;padding:0 1em}}
    h1 {{color:#1a252f}}
    table {{border-collapse:collapse;width:100%}}
    th,td {{border:1px solid #ccc;padding:.5em .8em;text-align:left;vertical-align:top}}
    th {{background:#eee}}
    tr:nth-child(even) {{background:#f9f9f9}}
    .badge {{display:inline-block;padding:.2em .6em;border-radius:3px;color:#fff;font-size:.85em;margin-right:.3em}}
    .err {{background:#c0392b}} .warn {{background:#e67e22}} .info {{background:#2980b9}}
    code {{background:#f4f4f4;padding:.1em .3em;border-radius:3px;font-size:.9em}}
  </style>
</head>
<body>
<h1>Statistical Audit Report</h1>
<p><strong>Source:</strong> {self.source}</p>
<p>
  <span class="badge err">ERROR&nbsp;{s['ERROR']}</span>
  <span class="badge warn">WARNING&nbsp;{s['WARNING']}</span>
  <span class="badge info">INFO&nbsp;{s['INFO']}</span>
</p>
<table>
  <thead>
    <tr>
      <th>Severity</th><th>Rule</th><th>Location</th>
      <th>Snippet</th><th>Suggestion</th>
    </tr>
  </thead>
  <tbody>
{rows}{no_findings_row}  </tbody>
</table>
</body>
</html>"""

    def save_html(self, path: str) -> None:
        from pathlib import Path
        Path(path).write_text(self.to_html(), encoding="utf-8")
