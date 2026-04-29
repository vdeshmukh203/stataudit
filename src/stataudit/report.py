"""Data structures: Severity, Finding, AuditReport."""
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


_SEV_COLORS = {"ERROR": "#c0392b", "WARNING": "#e67e22", "INFO": "#2980b9"}


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

    def _to_html(self) -> str:
        s = self.summary["by_severity"]
        rows = ""
        for f in self.findings:
            color = _SEV_COLORS.get(f.severity.value, "#333")
            text_esc = f.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            rows += (
                f"<tr>"
                f"<td style='color:{color};font-weight:bold'>{f.severity.value}</td>"
                f"<td><code>{f.rule}</code></td>"
                f"<td>{f.location}</td>"
                f"<td><code>{text_esc}</code></td>"
                f"<td>{f.suggestion}</td>"
                f"</tr>\n"
            )
        if self.findings:
            body = (
                "<table>\n"
                "<tr><th>Severity</th><th>Rule</th><th>Location</th>"
                "<th>Matched Text</th><th>Suggestion</th></tr>\n"
                + rows
                + "</table>"
            )
        else:
            body = "<p><em>No findings.</em></p>"
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            f"<title>StatAudit Report — {self.source}</title>\n"
            "<style>\n"
            '  body {font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;\n'
            "         max-width: 1200px; margin: 2em auto; padding: 0 1em; color: #2c3e50;}\n"
            "  h1 {border-bottom: 2px solid #3498db; padding-bottom: 0.3em;}\n"
            "  .summary {background: #ecf0f1; border-radius: 6px; padding: 1em 1.5em;\n"
            "             margin-bottom: 1.5em; display: flex; gap: 2em; flex-wrap: wrap;}\n"
            "  .badge {font-weight: bold;}\n"
            "  .badge.error {color: #c0392b;}\n"
            "  .badge.warning {color: #e67e22;}\n"
            "  .badge.info {color: #2980b9;}\n"
            "  table {border-collapse: collapse; width: 100%;}\n"
            "  th, td {border: 1px solid #ddd; padding: 8px 10px; text-align: left; vertical-align: top;}\n"
            "  th {background: #34495e; color: white;}\n"
            "  tr:nth-child(even) {background: #f9f9f9;}\n"
            "  tr:hover {background: #eaf4fb;}\n"
            "  code {background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 0.9em;}\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            "<h1>Statistical Audit Report</h1>\n"
            '<div class="summary">\n'
            f"  <span><strong>Source:</strong> {self.source}</span>\n"
            f"  <span><strong>Total:</strong> {len(self.findings)}</span>\n"
            f"  <span class=\"badge error\">ERROR: {s['ERROR']}</span>\n"
            f"  <span class=\"badge warning\">WARNING: {s['WARNING']}</span>\n"
            f"  <span class=\"badge info\">INFO: {s['INFO']}</span>\n"
            "</div>\n"
            + body
            + "\n</body>\n</html>"
        )

    def save_html(self, path: str) -> None:
        from pathlib import Path
        Path(path).write_text(self._to_html(), encoding="utf-8")
