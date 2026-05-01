#!/usr/bin/env python3
"""
stataudit — Statistical Reporting Auditor

Scans academic text for common statistical reporting errors and incomplete
disclosures.  Stdlib-only; no external dependencies required.
"""

from __future__ import annotations

__version__ = "0.2.0"
__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "StatAuditor",
    "audit_text",
    "audit_file",
    "main",
]

import argparse
import html as _html
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Three-level severity scale for audit findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def _order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.value]

    def __lt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() < other._order()

    def __le__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() <= other._order()

    def __gt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() > other._order()

    def __ge__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() >= other._order()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Severity):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single statistical reporting issue detected in the source text."""

    rule: str
    text: str
    location: str
    severity: Severity
    suggestion: str

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary representation."""
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


# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------

#: List of ``(rule_name, compiled_pattern, severity, suggestion)`` tuples
#: applied sequentially by :func:`audit_text` and :func:`audit_file`.
_RULES: List[tuple] = [
    (
        "pvalue_exact",
        re.compile(r"\bp\s*[=<>]\s*\.?\d+(?:\.\d+)?(?:e[-+]?\d+)?\b", re.IGNORECASE),
        Severity.INFO,
        "Verify this p-value meets precision guidelines: report to 2–3 decimal places "
        "and use p < .001 for very small values (APA 7th ed.).",
    ),
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "pvalue_over_precision",
        re.compile(r"\bp\s*=\s*0?\.0{4,}\d+", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "ci_level_missing",
        # Matches CI / confidence interval NOT preceded by "95% " or similar
        # and NOT followed by a digit or opening bracket (which implies a level).
        re.compile(
            r"(?<![\d%] )\b(?:CI|confidence interval)s?\b(?![\s=,]*[\d\[])",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI [lower, upper]).",
    ),
    (
        "t_test_df_missing",
        # Matches "t = 3.14" but not "t(29) = 3.14".
        re.compile(r"\bt\s*=\s*[-+]?\d+\.?\d*(?![\d(])"),
        Severity.WARNING,
        "Include degrees of freedom: t(df) = value, p = .xxx.",
    ),
    (
        "anova_missing_df",
        # Matches "F = 5.43" but not "F(2, 47) = 5.43".
        re.compile(r"\bF\s*=\s*[-+]?\d+\.?\d*(?![\d(])"),
        Severity.WARNING,
        "Include degrees of freedom: F(df_between, df_within) = value.",
    ),
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*([1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify adequate statistical power.",
    ),
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 significant decimal places.",
    ),
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require a strong, pre-registered a priori justification.",
    ),
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes (e.g., Cohen's d) and confidence intervals.",
    ),
    (
        "outlier_handling",
        re.compile(r"\boutliers?\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and state whether exclusion was pre-registered.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?|observations?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report the proportion of missing data and the imputation strategy (if any).",
    ),
    (
        "regression_r2_missing",
        # Matches regression/regressed not followed by R²/R2/R-squared in the same sentence.
        re.compile(
            r"\bregress(?:ion|ed|ions|ing)\b(?![^.!?]*\bR[\s_-]?(?:squared|2|²|\^2)\b)",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report R² (and adjusted R²) alongside regression results.",
    ),
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false discovery|holm|benjamini)\b", re.IGNORECASE
        ),
        Severity.INFO,
        "A multiple-comparisons correction is referenced here — verify it is applied "
        "consistently and that the correction method is fully specified.",
    ),
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report the sample size alongside the correlation coefficient.",
    ),
]


# ---------------------------------------------------------------------------
# Core audit functions
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences on terminal punctuation followed by whitespace."""
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Scan *text* and return a list of :class:`Finding` objects.

    Locations are reported as ``"sentence N"`` (1-indexed).

    Parameters
    ----------
    text:
        Plain-text content to audit (any encoding accepted as a Python str).
    min_severity:
        Only findings at or above this severity level are returned.

    Returns
    -------
    list[Finding]
        Possibly empty list ordered by sentence position.

    Examples
    --------
    >>> findings = audit_text("The effect was significant (ns).")
    >>> findings[0].rule
    'nhst_only'
    """
    if not text or not text.strip():
        return []
    findings: List[Finding] = []
    for sent_idx, sentence in enumerate(_split_sentences(text)):
        location = f"sentence {sent_idx + 1}"
        for rule_name, pattern, severity, suggestion in _RULES:
            if severity < min_severity:
                continue
            for m in pattern.finditer(sentence):
                start = max(0, m.start() - 20)
                snippet = sentence[start : m.end() + 20].strip()
                findings.append(
                    Finding(
                        rule=rule_name,
                        text=snippet,
                        location=location,
                        severity=severity,
                        suggestion=suggestion,
                    )
                )
    return findings


def audit_file(path: "Path | str", min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a plain-text file and return findings with accurate line-level locations.

    The file is scanned in its entirety (not sentence-split), so each pattern
    match is mapped to an exact line number using ``text.count("\\n", 0, pos)``.

    Parameters
    ----------
    path:
        Path to the manuscript file (UTF-8 expected; encoding errors are replaced).
    min_severity:
        Only findings at or above this severity level are returned.

    Returns
    -------
    list[Finding]
        Findings ordered by line number.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")

    findings: List[Finding] = []
    for rule_name, pattern, severity, suggestion in _RULES:
        if severity < min_severity:
            continue
        for m in pattern.finditer(text):
            line_num = text.count("\n", 0, m.start()) + 1
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            snippet = text[start:end].strip()
            findings.append(
                Finding(
                    rule=rule_name,
                    text=snippet,
                    location=f"line {line_num}",
                    severity=severity,
                    suggestion=suggestion,
                )
            )

    findings.sort(key=lambda f: int(f.location.split()[-1]))
    return findings


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class AuditReport:
    """Container for all findings produced by an audit run.

    Parameters
    ----------
    source:
        Human-readable label for the audited source (filename or ``"<stdin>"``).
    findings:
        List of :class:`Finding` objects produced by :func:`audit_text` or
        :func:`audit_file`.
    """

    source: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        """Return a dict with total count and per-severity breakdown."""
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {
            "source": self.source,
            "total": len(self.findings),
            "by_severity": counts,
        }

    # ------------------------------------------------------------------
    # Output formats
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        """Return a plain-text report string."""
        if not self.findings:
            return f"No findings for {self.source}."
        lines = [
            f"Audit report for: {self.source}",
            f"Total findings: {len(self.findings)}",
            "",
        ]
        for f in self.findings:
            lines.append(str(f))
            lines.append("")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Return a GitHub-flavoured Markdown report string."""
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
        """Return a JSON report string."""
        return json.dumps(
            {
                "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings],
            },
            indent=indent,
            ensure_ascii=False,
        )

    def to_html(self) -> str:
        """Return a self-contained HTML report with inline CSS."""
        s = self.summary["by_severity"]
        _SEV_COLOR = {"ERROR": "#c0392b", "WARNING": "#e67e22", "INFO": "#27ae60"}
        esc = _html.escape

        rows: List[str] = []
        for f in self.findings:
            color = _SEV_COLOR.get(f.severity.value, "#333")
            rows.append(
                f'<tr>'
                f'<td style="color:{color};font-weight:bold;white-space:nowrap">'
                f'{esc(f.severity.value)}</td>'
                f'<td><code>{esc(f.rule)}</code></td>'
                f'<td style="white-space:nowrap">{esc(f.location)}</td>'
                f'<td><code>{esc(f.text)}</code></td>'
                f'<td>{esc(f.suggestion)}</td>'
                f'</tr>'
            )
        rows_html = (
            "\n".join(rows)
            if rows
            else '<tr><td colspan="5"><em>No findings.</em></td></tr>'
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>stataudit Report — {esc(self.source)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1100px;
           margin: 2em auto; padding: 0 1em; }}
    h1   {{ color: #2c3e50; }}
    .summary {{ display: flex; gap: 1.5em; margin: 1em 0; }}
    .badge {{ padding: .4em .9em; border-radius: 4px;
              font-weight: bold; color: #fff; }}
    .ERROR   {{ background: #c0392b; }}
    .WARNING {{ background: #e67e22; }}
    .INFO    {{ background: #27ae60; }}
    table {{ border-collapse: collapse; width: 100%; font-size: .9em; }}
    th  {{ background: #2c3e50; color: #fff; padding: .5em .8em;
           text-align: left; }}
    td  {{ padding: .45em .8em; vertical-align: top;
           border-bottom: 1px solid #eee; }}
    tr:hover td {{ background: #f5f5f5; }}
    code {{ background: #f0f0f0; padding: .1em .3em; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>Statistical Audit Report</h1>
  <p><strong>Source:</strong> {esc(self.source)}</p>
  <p><strong>Total findings:</strong> {len(self.findings)}</p>
  <div class="summary">
    <span class="badge ERROR">ERROR: {s['ERROR']}</span>
    <span class="badge WARNING">WARNING: {s['WARNING']}</span>
    <span class="badge INFO">INFO: {s['INFO']}</span>
  </div>
  <table>
    <thead>
      <tr>
        <th>Severity</th><th>Rule</th><th>Location</th>
        <th>Text</th><th>Suggestion</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
</body>
</html>"""

    def save_html(self, path: "str | Path") -> None:
        """Write an HTML report to *path*."""
        Path(path).write_text(self.to_html(), encoding="utf-8")


# ---------------------------------------------------------------------------
# High-level facade
# ---------------------------------------------------------------------------

class StatAuditor:
    """Convenience façade for auditing a file or raw text string.

    Parameters
    ----------
    source:
        A file-system path (str or :class:`pathlib.Path`) or a raw text string.
        If the value is an existing file path it is read from disk; otherwise
        it is treated as the text to audit directly.
    min_severity:
        Only include findings at or above this level in the returned report.

    Examples
    --------
    Audit a file:

    >>> auditor = StatAuditor("manuscript.txt")
    >>> report = auditor.run()
    >>> for finding in report.findings:
    ...     print(finding.severity, finding.rule, finding.location)

    Audit a text string directly:

    >>> auditor = StatAuditor("The effect was significant (p = .034).")
    >>> report = auditor.run()
    """

    def __init__(
        self,
        source: str,
        min_severity: Severity = Severity.INFO,
    ) -> None:
        self.source = source
        self.min_severity = min_severity

    def run(self) -> AuditReport:
        """Run the audit and return an :class:`AuditReport`."""
        path = Path(self.source)
        if path.is_file():
            findings = audit_file(path, self.min_severity)
            return AuditReport(source=str(path), findings=findings)
        findings = audit_text(self.source, self.min_severity)
        return AuditReport(source="<text>", findings=findings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic manuscripts.",
    )
    p.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json", "html"],
        default="text",
        help="Output format (default: text).",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity level to report (default: INFO).",
    )
    p.add_argument("--output", "-o", metavar="FILE",
                   help="Write report to FILE instead of stdout.")
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="Print all detection rules and exit.",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point.

    Returns
    -------
    int
        Exit code: ``0`` (clean or only INFO/WARNING), ``1`` (ERROR findings
        present), ``2`` (usage/IO error).
    """
    args = _parse_args(argv)

    if args.list_rules:
        for name, _, sev, suggestion in _RULES:
            print(f"{name:35s}  [{sev.value:7s}]  {suggestion[:65]}")
        return 0

    min_sev = Severity(args.severity)

    if args.input:
        path = Path(args.input)
        if not path.is_file():
            print(f"stataudit: error: file not found: {args.input}", file=sys.stderr)
            return 2
        report = AuditReport(source=str(path), findings=audit_file(path, min_sev))
    else:
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    _formats = {
        "text": report.to_text,
        "markdown": report.to_markdown,
        "json": report.to_json,
        "html": report.to_html,
    }
    output = _formats[args.format]()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0


if __name__ == "__main__":
    sys.exit(main())
