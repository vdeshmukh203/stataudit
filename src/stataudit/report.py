"""AuditReport: container for findings with multi-format export."""
from __future__ import annotations

import html as _html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .models import Finding, Severity

# ── HTML template ─────────────────────────────────────────────────────────────

_HTML_TMPL = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>stataudit Report</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,sans-serif;background:#f8f9fa;color:#212529;line-height:1.5}}
  header{{background:#1a1a2e;color:#fff;padding:1rem 2rem}}
  header h1{{font-size:1.4rem;font-family:monospace}}
  header p{{color:#aaa;font-size:.85rem}}
  main{{max-width:960px;margin:1.5rem auto;padding:0 1rem}}
  .summary{{display:flex;gap:1rem;align-items:center;background:#fff;border:1px solid #dee2e6;
            border-radius:8px;padding:1rem;margin-bottom:1.25rem;flex-wrap:wrap}}
  .summary-title{{font-weight:600;flex:1}}
  .badge{{display:inline-block;padding:.2rem .65rem;border-radius:12px;font-size:.8rem;
          font-weight:700;color:#fff;white-space:nowrap}}
  .ERROR{{background:#dc3545}}.WARNING{{background:#fd7e14}}.INFO{{background:#0d6efd}}
  table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dee2e6;
         border-radius:8px;overflow:hidden}}
  th{{background:#f5f5f5;text-align:left;padding:.6rem .75rem;border-bottom:2px solid #dee2e6;
      font-size:.85rem}}
  td{{padding:.55rem .75rem;border-bottom:1px solid #f0f0f0;font-size:.85rem;vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
  tr.ERROR td{{background:#fff5f5}} tr.WARNING td{{background:#fff8f0}} tr.INFO td{{background:#f0f5ff}}
  code{{font-family:monospace;background:#f5f5f5;padding:.05rem .3rem;border-radius:3px;font-size:.82rem}}
  .no-findings{{text-align:center;padding:2rem;color:#28a745;font-size:1.1rem}}
</style>
</head>
<body>
<header><h1>stataudit</h1><p>Statistical Reporting Auditor — {source}</p></header>
<main>
<div class="summary">
  <span class="summary-title">Total findings: {total}</span>
  <span class="badge ERROR">ERROR&nbsp;{n_error}</span>
  <span class="badge WARNING">WARNING&nbsp;{n_warn}</span>
  <span class="badge INFO">INFO&nbsp;{n_info}</span>
</div>
{body}
</main>
</body>
</html>
"""

_TABLE_OPEN = (
    '<table><thead><tr>'
    '<th>Rule</th><th>Severity</th><th>Location</th>'
    '<th>Text snippet</th><th>Suggestion</th>'
    '</tr></thead><tbody>'
)

_TABLE_CLOSE = "</tbody></table>"


@dataclass
class AuditReport:
    """
    Container for a complete audit run.

    Attributes
    ----------
    source:
        Human-readable name of the audited source (file path or ``<stdin>``).
    findings:
        Ordered list of :class:`Finding` objects produced by the audit.
    """

    source: str
    findings: List[Finding] = field(default_factory=list)

    # ── summary ───────────────────────────────────────────────────────────

    @property
    def summary(self) -> dict:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {
            "source": self.source,
            "total": len(self.findings),
            "by_severity": counts,
        }

    # ── export helpers ────────────────────────────────────────────────────

    def to_text(self) -> str:
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
            {
                "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings],
            },
            indent=indent,
            ensure_ascii=False,
        )

    def to_html(self) -> str:
        s = self.summary["by_severity"]
        if not self.findings:
            body = '<p class="no-findings">&#10003; No findings.</p>'
        else:
            rows = [_TABLE_OPEN]
            for f in self.findings:
                rows.append(
                    f'<tr class="{f.severity.value}">'
                    f'<td><code>{_html.escape(f.rule)}</code></td>'
                    f'<td><span class="badge {f.severity.value}">{f.severity.value}</span></td>'
                    f'<td>{_html.escape(f.location)}</td>'
                    f'<td><code>{_html.escape(f.text)}</code></td>'
                    f'<td>{_html.escape(f.suggestion)}</td>'
                    f'</tr>'
                )
            rows.append(_TABLE_CLOSE)
            body = "\n".join(rows)
        return _HTML_TMPL.format(
            source=_html.escape(self.source),
            total=len(self.findings),
            n_error=s["ERROR"],
            n_warn=s["WARNING"],
            n_info=s["INFO"],
            body=body,
        )

    def save_html(self, path: str) -> None:
        """Write an HTML report to *path*."""
        Path(path).write_text(self.to_html(), encoding="utf-8")

    def save(self, path: str, fmt: str = "text") -> None:
        """Write the report to *path* in the requested format.

        Parameters
        ----------
        path:
            Output file path.
        fmt:
            One of ``"text"``, ``"markdown"``, ``"json"``, ``"html"``.
        """
        renderers = {
            "text": self.to_text,
            "markdown": self.to_markdown,
            "json": self.to_json,
            "html": self.to_html,
        }
        content = renderers.get(fmt, self.to_text)()
        Path(path).write_text(content, encoding="utf-8")
