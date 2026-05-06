#!/usr/bin/env python3
"""
stataudit — Statistical Reporting Auditor

Scans academic text for common statistical reporting errors and incomplete
disclosures. Stdlib-only — no external dependencies required.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import List, Optional


__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"


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
    """Represents a single statistical-reporting issue found in a manuscript."""

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


# Rules: (name, compiled_regex, severity, suggestion)
_RULES = [
    # ── ERROR ────────────────────────────────────────────────────────────────
    (
        "pvalue_impossible",
        re.compile(r'\bp\s*=\s*(?:[2-9]\d*\.\d*|\d{2,}\.\d*|1\.[1-9]\d*)\b', re.IGNORECASE),
        Severity.ERROR,
        "p-value greater than 1.0 is statistically impossible — check the reported value.",
    ),
    (
        "pvalue_negative",
        re.compile(r'\bp\s*=\s*-\s*[\d.]+', re.IGNORECASE),
        Severity.ERROR,
        "Negative p-value is statistically impossible — check the reported value.",
    ),
    # ── WARNING ──────────────────────────────────────────────────────────────
    (
        "pvalue_ns",
        re.compile(r'\bns\b|\(ns\)', re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "ci_level_missing",
        # Matches CI/confidence interval NOT preceded by a percentage (e.g. "95% CI" is fine)
        # and NOT followed by a digit. Variable-length lookbehind not supported, so we
        # chain fixed-width lookbehinds covering the most common spacing variants.
        re.compile(r'(?<!\%\s)(?<!\%)\b(?:CI|confidence interval)\b(?!\s*\d)', re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI).",
    ),
    (
        "t_test_df_missing",
        re.compile(r'\bt\s*=\s*[-+]?[\d.]+(?!\s*\()'),
        Severity.WARNING,
        "Include degrees of freedom: t(df) = value.",
    ),
    (
        "anova_missing_df",
        re.compile(r'\bF\s*=\s*[-+]?[\d.]+(?!\s*\()'),
        Severity.WARNING,
        "Include degrees of freedom: F(df_between, df_within) = value.",
    ),
    (
        "sample_size_small",
        re.compile(r'\b[nN]\s*=\s*([1-9]|[12]\d)\b'),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power.",
    ),
    (
        "one_tailed",
        re.compile(r'\bone[- ]?tailed\b', re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification.",
    ),
    (
        "regression_r2_missing",
        re.compile(r'\bregress(?:ed|ion)\b(?![^.]*R.squared)', re.IGNORECASE),
        Severity.WARNING,
        "Report R² alongside regression results.",
    ),
    # ── INFO ─────────────────────────────────────────────────────────────────
    (
        "pvalue_exact",
        re.compile(r'\bp\s*[=<>]\s*[\d.]+(?:e[-+]?\d+)?\b', re.IGNORECASE),
        Severity.INFO,
        "Report exact p-value with appropriate precision (e.g., p = .034 or p < .001).",
    ),
    (
        "pvalue_over_precision",
        re.compile(r'\bp\s*=\s*\.?0{4,}\d+', re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "over_precision",
        re.compile(r'\b\d+\.\d{5,}\b'),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 significant decimal places.",
    ),
    (
        "nhst_only",
        re.compile(r'\b(?:significant|insignificant|failed to reject)\b', re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and CIs.",
    ),
    (
        "outlier_handling",
        re.compile(r'\boutlier\b', re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion.",
    ),
    (
        "missing_data",
        re.compile(r'\bmissing\s+(?:data|values?|cases?)\b', re.IGNORECASE),
        Severity.INFO,
        "Report proportion of missing data and imputation strategy.",
    ),
    (
        "multiple_comparisons",
        re.compile(r'\b(?:bonferroni|FDR|false discovery|holm|benjamini)\b', re.IGNORECASE),
        Severity.INFO,
        "Verify the multiple-comparisons correction method is stated.",
    ),
    (
        "correlation_missing_n",
        re.compile(r'(?<!\w)r\s*=\s*[-+]?(?:0?\.\d+|1\.0*)\b'),
        Severity.INFO,
        "Report sample size when stating a correlation coefficient.",
    ),
]


def _split_sentences(text: str) -> List[str]:
    return re.split(r'(?<=[.!?])\s+', text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a string of manuscript text and return a list of :class:`Finding` objects."""
    findings: List[Finding] = []
    sentences = _split_sentences(text)
    for sent_idx, sentence in enumerate(sentences):
        location = f"sentence {sent_idx + 1}"
        for rule_name, pattern, severity, suggestion in _RULES:
            if severity < min_severity:
                continue
            for m in pattern.finditer(sentence):
                start = max(0, m.start() - 20)
                snippet = sentence[start: m.end() + 20].strip()
                findings.append(Finding(
                    rule=rule_name,
                    text=snippet,
                    location=location,
                    severity=severity,
                    suggestion=suggestion,
                ))
    return findings


def audit_file(path: Path, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a text file and return a list of :class:`Finding` objects."""
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
    """Aggregates audit findings and renders them in multiple output formats."""

    source: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {"source": self.source, "total": len(self.findings), "by_severity": counts}

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
        for sev in ["ERROR", "WARNING", "INFO"]:
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

    def to_text(self) -> str:
        if not self.findings:
            return f"No findings for {self.source}."
        lines = [f"Audit report for: {self.source}", f"Total findings: {len(self.findings)}", ""]
        for f in self.findings:
            lines.append(str(f))
            lines.append("")
        return "\n".join(lines)


class StatAuditor:
    """High-level auditor: accepts a file path or raw text string and returns an :class:`AuditReport`."""

    def __init__(self, source: str, min_severity: Severity = Severity.INFO) -> None:
        self.source = source
        self.min_severity = min_severity

    def run(self) -> AuditReport:
        """Run the audit and return an :class:`AuditReport`."""
        path = Path(self.source)
        if path.is_file():
            findings = audit_file(path, self.min_severity)
        else:
            findings = audit_text(self.source, self.min_severity)
        return AuditReport(source=self.source, findings=findings)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic text.",
    )
    p.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--severity", choices=["INFO", "WARNING", "ERROR"], default="INFO")
    p.add_argument("--output", "-o", help="Write report to this file.")
    p.add_argument("--list-rules", action="store_true", help="List all detection rules and exit.")
    p.add_argument("--gui", action="store_true", help="Launch the graphical user interface.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if args.gui:
        try:
            from stataudit_gui import launch
        except ImportError:
            print("Error: stataudit_gui.py not found — GUI unavailable.", file=sys.stderr)
            return 1
        launch()
        return 0

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
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    if args.format == "json":
        output = report.to_json()
    elif args.format == "markdown":
        output = report.to_markdown()
    else:
        output = report.to_text()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0


# Backwards-compatible alias used by the installed console script entry point
_cli = main

if __name__ == "__main__":
    sys.exit(main())
