#!/usr/bin/env python3
"""
stataudit.py — Statistical Reporting Auditor (zero-dependency standalone script).

Scans academic text for common statistical reporting errors and incomplete
disclosures following APA and ML-reproducibility-checklist guidelines.

Usage
-----
    python stataudit.py manuscript.txt
    python stataudit.py manuscript.txt --format markdown
    python stataudit.py --list-rules
    echo "Results were ns." | python stataudit.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


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


_RULES: List[Tuple[str, "re.Pattern[str]", Severity, str]] = [
    (
        "pvalue_exact",
        re.compile(r"\bp\s*[=<>]\s*[\d.]+(?:e[-+]?\d+)?\b", re.IGNORECASE),
        Severity.INFO,
        "Report exact p-value with appropriate precision (e.g., p = .034 or p < .001).",
    ),
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "pvalue_over_precision",
        re.compile(r"\bp\s*=\s*0?\.0{3,}\d+", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "pvalue_impossible",
        re.compile(r"\bp\s*[=<>]\s*(?:1\.[1-9]\d*|[2-9]\d*\.|\d{2,}\.)", re.IGNORECASE),
        Severity.ERROR,
        "p-value cannot exceed 1.0 — verify the reported value.",
    ),
    (
        "ci_level_missing",
        re.compile(r"(?<!%)(?<!% )\b(?:CI|confidence interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI).",
    ),
    (
        "t_test_df_missing",
        re.compile(r"\bt\s*=\s*[-+]?[\d.]+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom: t(df) = value.",
    ),
    (
        "anova_missing_df",
        re.compile(r"\bF\s*=\s*[-+]?[\d.]+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom: F(df_between, df_within) = value.",
    ),
    (
        "chi_square_df_missing",
        re.compile(
            r"(?:χ²?|chi[- ]?square?)\s*=\s*[-+]?[\d.]+(?!\s*\()",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Include degrees of freedom and N: χ²(df, N = n) = value.",
    ),
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power and report it.",
    ),
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — round to 2–3 significant decimal places.",
    ),
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification; state the rationale.",
    ),
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and confidence intervals.",
    ),
    (
        "effect_size_missing",
        re.compile(
            r"\bstatistically significant\b(?![^.]*(?:Cohen|η[²2]|ω[²2]|\bd\b|r\s*=|R[²2]))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report an effect size (Cohen's d, η², r) alongside significance statements.",
    ),
    (
        "outlier_handling",
        re.compile(r"\boutlier\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and the number of excluded cases.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report the proportion of missing data and the imputation or exclusion strategy.",
    ),
    (
        "regression_r2_missing",
        re.compile(r"\bregress(?:ed|ion|ing)\b(?![^.]*R[²2])", re.IGNORECASE),
        Severity.WARNING,
        "Report R² (and adjusted R²) alongside regression results.",
    ),
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false discovery|holm|benjamini|hochberg)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "State the correction method and the resulting adjusted alpha level.",
    ),
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size alongside the correlation coefficient.",
    ),
    (
        "sem_vs_sd",
        re.compile(r"\bSEM\b|\bstandard error of the mean\b", re.IGNORECASE),
        Severity.INFO,
        "Clarify whether spread measures and error bars represent SD, SE, or CI.",
    ),
    (
        "post_hoc_test",
        re.compile(r"\bpost[- ]?hoc\b", re.IGNORECASE),
        Severity.INFO,
        "Name the post-hoc test used and report corrected p-values.",
    ),
]

_SEV_COLOR = {"ERROR": "#c0392b", "WARNING": "#e67e22", "INFO": "#2980b9"}


def _split_sentences(text: str) -> List[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Return findings for statistical issues in *text*."""
    if not text:
        return []
    findings: List[Finding] = []
    sentences = _split_sentences(text)
    for sent_idx, sentence in enumerate(sentences):
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


def audit_file(path: Path, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a text file; findings include line numbers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = audit_text(text, min_severity)
    lines = text.splitlines()
    for finding in findings:
        snippet = finding.text[:20]
        for i, line in enumerate(lines, 1):
            if snippet in line:
                finding.location = f"line {i}"
                break
    return findings


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

    def to_html(self) -> str:
        s = self.summary["by_severity"]
        rows = ""
        for f in self.findings:
            color = _SEV_COLOR.get(f.severity.value, "#333")
            text_esc = f.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sug_esc = (
                f.suggestion.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            rows += (
                f"<tr>"
                f"<td style='color:{color};font-weight:bold'>{f.severity.value}</td>"
                f"<td>{f.rule}</td><td>{f.location}</td>"
                f"<td><code>{text_esc}</code></td><td>{sug_esc}</td>"
                f"</tr>\n"
            )
        no_findings = (
            "" if rows else "<tr><td colspan='5'><em>No findings.</em></td></tr>\n"
        )
        return (
            f"<!DOCTYPE html>\n<html lang='en'>\n<head><meta charset='utf-8'>"
            f"<title>stataudit — {self.source}</title>\n"
            "<style>body{font-family:sans-serif;max-width:1100px;margin:2em auto}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ccc;padding:.4em .7em;text-align:left;vertical-align:top}"
            "th{background:#eee}tr:nth-child(even){background:#f9f9f9}"
            "code{background:#f4f4f4;padding:.1em .3em;border-radius:2px}</style>"
            "</head>\n<body>\n"
            "<h1>Statistical Audit Report</h1>\n"
            f"<p><strong>Source:</strong> {self.source}</p>\n"
            f"<p>ERROR&nbsp;{s['ERROR']} &nbsp;WARNING&nbsp;{s['WARNING']} "
            f"&nbsp;INFO&nbsp;{s['INFO']}</p>\n"
            "<table><thead><tr>"
            "<th>Severity</th><th>Rule</th><th>Location</th><th>Snippet</th><th>Suggestion</th>"
            "</tr></thead>\n<tbody>\n"
            f"{rows}{no_findings}"
            "</tbody></table>\n</body></html>"
        )

    def save_html(self, path: str) -> None:
        Path(path).write_text(self.to_html(), encoding="utf-8")


class StatAuditor:
    """High-level auditor: accepts a file path or a raw text string."""

    def __init__(self, source: str, min_severity: Severity = Severity.INFO) -> None:
        self.source = source
        self.min_severity = min_severity

    def run(self) -> AuditReport:
        path = Path(self.source)
        if path.is_file():
            findings = audit_file(path, self.min_severity)
        else:
            findings = audit_text(self.source, self.min_severity)
        return AuditReport(source=self.source, findings=findings)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic text.",
    )
    p.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json", "html"],
        default="text",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity to report.",
    )
    p.add_argument("--output", "-o", help="Write report to this file.")
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="List all detection rules and exit.",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    if args.list_rules:
        for name, _, sev, suggestion in _RULES:
            print(f"{name:35s}  [{sev.value}]  {suggestion[:60]}")
        return 0

    min_sev = Severity(args.severity)

    if args.input:
        path = Path(args.input)
        if not path.is_file():
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            return 1
        report = AuditReport(source=str(path), findings=audit_file(path, min_sev))
    else:
        if sys.stdin.isatty():
            print("stataudit: reading from stdin (Ctrl-D to finish)…", file=sys.stderr)
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    formatters = {
        "json": report.to_json,
        "markdown": report.to_markdown,
        "html": report.to_html,
        "text": report.to_text,
    }
    output = formatters[args.format]()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0


# Entry-point alias used by pyproject.toml console_scripts.
_cli = main


if __name__ == "__main__":
    sys.exit(main())
