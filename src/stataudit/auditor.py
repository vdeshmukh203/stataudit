"""Audit rules, text scanning, and high-level StatAuditor interface."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from .report import AuditReport, Finding, Severity

# Each rule: (name, compiled pattern, severity, suggestion)
_Rule = Tuple[str, "re.Pattern[str]", Severity, str]

RULES: List[_Rule] = [
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
        re.compile(r"\bp\s*=\s*\.?0{4,}\d+", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "ci_level_missing",
        re.compile(r"(?<!%)(?<!%\s)\b(?:CI|confidence interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI [lower, upper]).",
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
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*([1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power and report power analysis.",
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
        "One-tailed tests require strong a priori justification; state the rationale explicitly.",
    ),
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and confidence intervals.",
    ),
    (
        "outlier_handling",
        re.compile(r"\boutlier\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and proportion of observations removed.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report the proportion of missing data and the imputation or exclusion strategy.",
    ),
    (
        "regression_r2_missing",
        re.compile(r"\bregress(?:ed|ion)\b(?![^.]*R.squared)", re.IGNORECASE),
        Severity.WARNING,
        "Report R² (and adjusted R² for multiple regression) alongside regression results.",
    ),
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false discovery|holm|benjamini)\b", re.IGNORECASE
        ),
        Severity.INFO,
        "Verify the multiple-comparisons correction method is explicitly stated.",
    ),
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size N and p-value when stating a correlation coefficient.",
    ),
    (
        "effect_size_missing",
        re.compile(
            r"\b(?:Cohen[\'s]*\s*d|eta.squared|omega.squared|Hedges[\'s]*\s*g|"
            r"partial\s+eta)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Confirm the effect size measure and its confidence interval are reported.",
    ),
    (
        "seed_unreported",
        re.compile(r"\brandom\s+seed\b|\bseed\s*=\s*\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report the exact random seed(s) used to ensure reproducibility.",
    ),
    (
        "variance_unreported",
        re.compile(
            r"\bmean\s*[=:]\s*[-+]?[\d.]+(?!\s*[±(]|\s*SD|\s*SE|\s*std|\s*\±)",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report variance alongside the mean (e.g., M = 3.2, SD = 0.8).",
    ),
]


def _split_sentences(text: str) -> List[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(
    text: str, min_severity: Severity = Severity.INFO
) -> List[Finding]:
    """Scan *text* and return one :class:`~stataudit.Finding` per rule match.

    Parameters
    ----------
    text:
        Plain-text content to audit.
    min_severity:
        Only return findings at or above this severity level.

    Returns
    -------
    list of Finding
    """
    findings: List[Finding] = []
    if not text.strip():
        return findings
    sentences = _split_sentences(text)
    for sent_idx, sentence in enumerate(sentences):
        location = f"sentence {sent_idx + 1}"
        for rule_name, pattern, severity, suggestion in RULES:
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
    path: Path, min_severity: Severity = Severity.INFO
) -> List[Finding]:
    """Read *path* and return findings with line-level location references.

    Parameters
    ----------
    path:
        Path to the text file to audit.
    min_severity:
        Only return findings at or above this severity level.

    Returns
    -------
    list of Finding
    """
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


class StatAuditor:
    """High-level auditing interface for a single document.

    Parameters
    ----------
    source:
        Either a file path (string or :class:`~pathlib.Path`) that exists on
        disk, or a raw text string to audit directly.
    min_severity:
        Filter findings below this level. Defaults to :attr:`Severity.INFO`
        (all findings).

    Examples
    --------
    >>> auditor = StatAuditor("manuscript.txt")
    >>> report = auditor.run()
    >>> for f in report.findings:
    ...     print(f.severity, f.rule, f.location)
    """

    def __init__(
        self,
        source: str,
        min_severity: Severity = Severity.INFO,
    ) -> None:
        self.source = source
        self.min_severity = min_severity

    def run(self) -> AuditReport:
        """Execute the audit and return an :class:`~stataudit.AuditReport`."""
        path = Path(self.source)
        if path.is_file():
            findings = audit_file(path, self.min_severity)
        else:
            findings = audit_text(self.source, self.min_severity)
        return AuditReport(source=self.source, findings=findings)
