#!/usr/bin/env python3
"""
stataudit — Statistical Reporting Auditor

Scans academic text for common statistical reporting errors and incomplete
disclosures following APA and ML reproducibility best-practice guidelines.
Stdlib-only; zero external dependencies.

Public API
----------
audit_text(text, min_severity) -> List[Finding]
audit_file(path, min_severity) -> List[Finding]
AuditReport(source, findings)
Finding(rule, text, location, severity, suggestion)
Severity   (INFO | WARNING | ERROR)
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
__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "audit_text",
    "audit_file",
]


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single audit finding produced by one detection rule."""

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


# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------
# Each entry: (rule_name, compiled_pattern, severity, suggestion)
# Patterns are applied sentence-by-sentence; each match yields one Finding.

_RULES: List[tuple] = [
    # Exact p-value present — informational, verify precision
    (
        "pvalue_exact",
        re.compile(r"\bp\s*[=<>]\s*[\d.]+(?:e[-+]?\d+)?\b", re.IGNORECASE),
        Severity.INFO,
        "Verify the p-value is reported to appropriate precision (e.g., p = .034 or p < .001).",
    ),
    # "ns" used instead of exact p-value
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    # p-value with excessive leading zeros (should be p < .001)
    # Handles both .00001 and 0.00001 forms.
    (
        "pvalue_over_precision",
        re.compile(r"\bp\s*=\s*0?\.0{4,}\d*", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    # CI mentioned without a level percentage before it
    # Lookbehinds prevent flagging "95% CI" and "95%CI".
    (
        "ci_level_missing",
        re.compile(r"(?<![0-9]%)(?<!% )\b(?:CI|confidence interval)\b", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI).",
    ),
    # t-value without parenthesised degrees of freedom: t(df) = value
    (
        "t_test_df_missing",
        re.compile(r"\bt\s*=\s*[-+]?[\d.]+"),
        Severity.WARNING,
        "Include degrees of freedom: t(df) = value.",
    ),
    # F-value without parenthesised degrees of freedom: F(df1, df2) = value
    (
        "anova_missing_df",
        re.compile(r"\bF\s*=\s*[-+]?[\d.]+"),
        Severity.WARNING,
        "Include degrees of freedom: F(df_between, df_within) = value.",
    ),
    # Very small sample size (N < 30)
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power.",
    ),
    # Excessive decimal places (> 4)
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 significant decimal places.",
    ),
    # One-tailed test flagged for justification
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification.",
    ),
    # NHST-only language without effect sizes
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and confidence intervals.",
    ),
    # Outlier mention without criterion
    (
        "outlier_handling",
        re.compile(r"\boutliers?\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and number of cases removed.",
    ),
    # Missing data mentioned without rate/strategy
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report proportion of missing data and the imputation or exclusion strategy.",
    ),
    # Regression without R² — handles R-squared, R², R^2, R2
    (
        "regression_r2_missing",
        re.compile(
            r"\bregress(?:ed|ion)\b(?![^.]*(?:[Rr][\s_^-]?(?:squared|[²2])|[Rr]²))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report R² (coefficient of determination) alongside regression results.",
    ),
    # Multiple-comparisons correction named but method verification
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false\s+discovery|holm|benjamini[- ]hochberg)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Verify the multiple-comparisons correction method is explicitly stated.",
    ),
    # Correlation reported without sample size
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report the sample size (N) when stating a Pearson correlation coefficient.",
    ),
    # Effect size reported — check unit/type is named (Cohen's d, η², etc.)
    (
        "effect_size_check",
        re.compile(
            r"\b(?:cohen'?s?\s*d|eta[- ]?squared|omega[- ]?squared|"
            r"hedges'?\s*g|glass'?\s*delta|cramer'?s?\s*v|"
            r"partial\s+eta|effect\s+size)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Confirm the effect size measure and its magnitude interpretation are clearly described.",
    ),
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences on sentence-ending punctuation.

    Simple heuristic splitter; does not attempt to resolve abbreviations.
    """
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(
    text: str,
    min_severity: Severity = Severity.INFO,
) -> List[Finding]:
    """Scan *text* and return a list of :class:`Finding` objects.

    Parameters
    ----------
    text:
        Plain text to audit (may be multi-paragraph).
    min_severity:
        Only findings at or above this severity are returned.

    Returns
    -------
    List[Finding]
        Findings ordered by sentence occurrence.
    """
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


def audit_file(
    path: Path,
    min_severity: Severity = Severity.INFO,
) -> List[Finding]:
    """Audit the plain-text file at *path*.

    Identical to :func:`audit_text` but enriches each finding with a
    ``line N`` location by scanning the source file.

    Parameters
    ----------
    path:
        Path to the text file to audit.
    min_severity:
        Only findings at or above this severity are returned.

    Returns
    -------
    List[Finding]
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    findings = audit_text(text, min_severity)
    lines = text.splitlines()
    for finding in findings:
        snippet = finding.text[:20]
        for i, line in enumerate(lines, 1):
            if snippet in line:
                finding.location = f"line {i}"
                break
    return findings


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------

@dataclass
class AuditReport:
    """Container for audit findings with multiple output formatters."""

    source: str
    findings: List[Finding] = field(default_factory=list)

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

    def to_text(self) -> str:
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic text.",
    )
    p.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        metavar="FORMAT",
        help="Output format: text (default), markdown, or json.",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        metavar="LEVEL",
        help="Minimum severity to report: INFO (default), WARNING, or ERROR.",
    )
    p.add_argument("--output", "-o", help="Write report to this file.")
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="List all detection rules and exit.",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    """CLI entry point. Returns exit code 0 (clean) or 1 (ERROR findings)."""
    args = _parse_args(argv)

    if args.list_rules:
        print(f"{'Rule':<35}  {'Sev':<8}  Suggestion")
        print("-" * 80)
        for name, _, sev, suggestion in _RULES:
            print(f"{name:<35}  [{sev.value:<7}]  {suggestion[:55]}")
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
            print("Reading from stdin — press Ctrl-D (EOF) when done.", file=sys.stderr)
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


# Alias used by the installed console_scripts entry point
_cli = main


if __name__ == "__main__":
    sys.exit(main())
