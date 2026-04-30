#!/usr/bin/env python3
"""
stataudit — Statistical Reporting Auditor
==========================================
Scans academic manuscripts for common statistical reporting errors and
incomplete disclosures.  Applies a configurable rule set drawn from
best-practice guidelines for empirical research (APA, Pineau et al. 2021,
Stodden et al. 2016) and returns structured findings with location,
severity, and actionable suggestions.

Stdlib-only — no third-party runtime dependencies.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "audit_text",
    "audit_file",
    "main",
]


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Three-level severity scheme for audit findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def _order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.value]

    def __le__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() <= other._order()

    def __lt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() < other._order()

    def __gt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() > other._order()

    def __ge__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() >= other._order()


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single audit finding produced by one rule."""

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
# Rule set
# ---------------------------------------------------------------------------

# Each rule is a 4-tuple: (name, compiled_pattern, severity, suggestion).
# Rules are evaluated in order; a single sentence can trigger multiple rules.

_RULES: List[Tuple[str, re.Pattern, Severity, str]] = [
    # ── p-value reporting ──────────────────────────────────────────────────
    (
        "pvalue_exact",
        re.compile(r"\bp\s*[=<>]\s*[\d.]+(?:e[-+]?\d+)?\b", re.IGNORECASE),
        Severity.INFO,
        "Verify APA format: omit leading zero (p = .034) and use p < .001 for "
        "values below .001.",
    ),
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "pvalue_zero",
        re.compile(r"\bp\s*=\s*0(?:\.0+)?\b", re.IGNORECASE),
        Severity.WARNING,
        "p = 0 is statistically impossible; report as p < .001.",
    ),
    (
        "pvalue_over_precision",
        re.compile(r"\bp\s*=\s*\.?0{4,}\d+", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "apa_p_format",
        re.compile(r"\bp\s*=\s*0\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "APA style omits the leading zero: write p = .034, not p = 0.034.",
    ),
    # ── Confidence intervals ───────────────────────────────────────────────
    (
        "ci_level_missing",
        # Negative lookbehind for "N% " (e.g. "95% CI") and negative lookahead
        # for a digit (e.g. "CI 95") so that properly labelled CIs are not flagged.
        re.compile(r"(?<!% )\b(?:CI|confidence interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI [lower, upper]).",
    ),
    # ── Test statistics ────────────────────────────────────────────────────
    (
        "t_test_df_missing",
        re.compile(r"\bt\s*=\s*[-+]?[\d.]+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom: t(df) = value, p = .xxx.",
    ),
    (
        "anova_missing_df",
        re.compile(r"\bF\s*=\s*[-+]?[\d.]+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom: F(df_between, df_within) = value.",
    ),
    # ── Effect sizes & sample size ─────────────────────────────────────────
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power.",
    ),
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes (e.g., Cohen's d, η²) and CIs.",
    ),
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size alongside the correlation coefficient.",
    ),
    (
        "regression_r2_missing",
        re.compile(
            r"\bregress(?:ed|ion|ions|ing)\b(?![^.!?\n]*(?:R[²2]|R-squared|R_squared))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report R² (and adjusted R² where appropriate) alongside regression results.",
    ),
    # ── Precision & formatting ─────────────────────────────────────────────
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 meaningful decimal places.",
    ),
    # ── Test methodology ───────────────────────────────────────────────────
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a-priori justification; state it explicitly.",
    ),
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false discovery|holm|benjamini|hochberg)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Confirm the multiple-comparisons correction method and threshold are stated.",
    ),
    # ── Data quality disclosures ───────────────────────────────────────────
    (
        "outlier_handling",
        re.compile(r"\boutlier\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and the number of cases removed.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report the proportion of missing data and the imputation/exclusion strategy.",
    ),
    # ── ML-specific ────────────────────────────────────────────────────────
    (
        "seed_unreported",
        re.compile(
            r"\b(?:random(?:ly)?|stochastic|initializ(?:ed?|ation)|shuffle[ds]?)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Report the random seed used for reproducibility.",
    ),
]


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences on sentence-terminal punctuation."""
    # Normalise line endings then split on end-of-sentence punctuation
    normalised = re.sub(r"\r\n?", "\n", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", normalised)
    return [p for p in parts if p.strip()]


def _build_line_index(text: str) -> List[int]:
    """Return a sorted list of character offsets where each line starts."""
    starts = [0]
    for i, ch in enumerate(text, 1):
        if ch == "\n":
            starts.append(i)
    return starts


def _offset_to_line(starts: List[int], offset: int) -> int:
    """Return the 1-based line number for a character *offset* in a text."""
    idx = bisect.bisect_right(starts, offset) - 1
    return max(1, idx + 1)


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit *text* and return a list of :class:`Finding` objects.

    Parameters
    ----------
    text:
        The manuscript or passage to audit.
    min_severity:
        Findings below this severity are suppressed.

    Returns
    -------
    list[Finding]
        Zero or more findings, one per rule match.
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


def audit_file(path: Path, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit the file at *path* and return findings with line-number locations.

    Parameters
    ----------
    path:
        Path to a plain-text or Markdown manuscript.
    min_severity:
        Findings below this severity are suppressed.

    Returns
    -------
    list[Finding]
        Zero or more findings with ``location`` set to ``"line N"``.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    line_starts = _build_line_index(text)
    sentences = _split_sentences(text)

    findings: List[Finding] = []
    search_from = 0
    for sentence in sentences:
        # Locate the sentence in the original text to get accurate line numbers.
        probe = sentence[:40]
        pos = text.find(probe, search_from)
        if pos == -1:
            pos = search_from
        else:
            search_from = pos

        line_num = _offset_to_line(line_starts, pos)
        location = f"line {line_num}"

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


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class AuditReport:
    """Aggregates findings from an audit run and renders them in several formats."""

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
            {"summary": self.summary, "findings": [f.to_dict() for f in self.findings]},
            indent=indent,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting quality in academic manuscripts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  stataudit manuscript.txt\n"
            "  stataudit manuscript.txt --format markdown --output report.md\n"
            "  echo 'We found significant results.' | stataudit\n"
            "  stataudit --list-rules\n"
        ),
    )
    p.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text).",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity to report (default: INFO).",
    )
    p.add_argument("--output", "-o", metavar="FILE", help="Write report to FILE.")
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="List all detection rules and exit.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any WARNING or ERROR findings are present.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the ``stataudit`` command-line tool.

    Returns 0 on success, 1 if ERROR-level findings are present (or if
    ``--strict`` is given and WARNING/ERROR findings are present).
    """
    args = _parse_args(argv)

    if args.list_rules:
        header = f"{'Rule':<35}  {'Sev':<8}  Suggestion"
        print(header)
        print("-" * len(header))
        for name, _, sev, suggestion in _RULES:
            print(f"{name:<35}  [{sev.value:<7}]  {suggestion[:60]}")
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

    has_errors = any(f.severity == Severity.ERROR for f in report.findings)
    has_warnings = any(f.severity >= Severity.WARNING for f in report.findings)
    if has_errors:
        return 1
    if args.strict and has_warnings:
        return 1
    return 0


# Backward-compatibility alias for the (now-fixed) pyproject.toml entry point.
_cli = main


if __name__ == "__main__":
    sys.exit(main())
