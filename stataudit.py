"""
stataudit: Automated statistical reporting auditor for scientific manuscripts.

Scans plain-text or Markdown documents for common statistical reporting patterns
(p-values, confidence intervals, t-tests, chi-square, ANOVA, correlations, effect
sizes) and flags deviations from APA/reporting-standards best practices.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# p-value patterns: p = .03, p < .001, p=0.045, p > .05, p-value = 0.032
_P_PATTERN = re.compile(
    r"\bp(?:-value)?\s*[=<>]\s*(\d*\.\d+)",
    re.IGNORECASE,
)

# Confidence interval: 95% CI [0.12, 0.45], 95% CI (0.12, 0.45)
_CI_PATTERN = re.compile(
    r"(\d+)%\s*CI\s*[\[\(]\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*[\]\)]",
    re.IGNORECASE,
)

# t-test: t(34) = 2.45
_T_PATTERN = re.compile(
    r"\bt\s*\((\d+)\)\s*=\s*(-?[\d.]+)",
    re.IGNORECASE,
)

# chi-square: chi-square(2) = 8.34, X2(3) = 12.1
_CHI_PATTERN = re.compile(
    r"(?:chi[- ]?square|x2|\u03c72)\s*\((\d+)\)\s*=\s*([\d.]+)",
    re.IGNORECASE,
)

# F-statistic: F(2, 45) = 3.21
_F_PATTERN = re.compile(
    r"\bF\s*\((\d+)\s*,\s*(\d+)\)\s*=\s*([\d.]+)",
)

# Correlation: r(45) = 0.32, r = .45
_R_PATTERN = re.compile(
    r"\br\s*(?:\((\d+)\))?\s*=\s*(-?[.\d]+)",
    re.IGNORECASE,
)

# Effect size: d = 0.45, eta2 = .12, Cohen's d = .80
_EFFECT_PATTERN = re.compile(
    r"(?:Cohen'?s\s+)?(?:d|eta[\s_]?2|omega[\s_]?2|f2|partial\s+eta2?)\s*=\s*([\d.]+)",
    re.IGNORECASE,
)

# Sample size: N = 120, n = 45
_N_PATTERN = re.compile(r"\b[Nn]\s*=\s*(\d+)")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single extracted statistical finding."""
    stat_type: str
    raw_text: str
    line_number: int
    value: Optional[float] = None
    df: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


@dataclass
class AuditReport:
    """Aggregated audit results for a document."""
    source: str
    findings: List[Finding] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)

    @property
    def issue_count(self) -> int:
        return sum(1 for f in self.findings if f.has_issues)

    @property
    def total_stats(self) -> int:
        return len(self.findings)

    def to_markdown(self) -> str:
        lines = [
            f"# StatAudit Report: {self.source}",
            "",
            f"**Total statistical reports found:** {self.total_stats}  ",
            f"**Reports with issues:** {self.issue_count}",
            "",
        ]
        if self.summary:
            lines += ["## Finding Counts by Type", ""]
            for k, v in sorted(self.summary.items()):
                lines.append(f"- {k}: {v}")
            lines.append("")

        issues_only = [f for f in self.findings if f.has_issues]
        if not issues_only:
            lines += ["## Issues", "", "_No issues found._", ""]
        else:
            lines += ["## Issues", ""]
            for f in issues_only:
                lines += [
                    f"### Line {f.line_number}: [{f.stat_type}] {f.raw_text}",
                    "",
                ]
                for issue in f.issues:
                    lines.append(f"- **Issue**: {issue}")
                for sug in f.suggestions:
                    lines.append(f"- **Suggestion**: {sug}")
                lines.append("")

        all_findings = [f for f in self.findings if not f.has_issues]
        if all_findings:
            lines += ["## Passing Reports", ""]
            for f in all_findings:
                lines.append(f"- Line {f.line_number} [{f.stat_type}]: {f.raw_text}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def _check_pvalue(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    val = float(m.group(1))
    finding = Finding(stat_type="p-value", raw_text=raw, line_number=line_no, value=val)

    # APA: exact p-values preferred; do not report "p = .000"
    if val == 0.0:
        finding.issues.append("p reported as exactly 0. Use p < .001 instead.")
        finding.suggestions.append("Replace with p < .001")

    # Marginal significance language check (done at document level, skip here)

    # Check for leading zero: APA requires no leading zero for p-values
    raw_val = m.group(1)
    if raw_val.startswith("0."):
        finding.issues.append(
            "APA style: p-values should not have a leading zero (use '.05' not '0.05')."
        )
        finding.suggestions.append(f"Change to p {m.group(0)[1:].split(raw_val)[0]}{raw_val[1:]}")

    # p > 1 is impossible
    if val > 1.0:
        finding.issues.append(f"p-value {val} > 1.0 is impossible.")

    return finding


def _check_ci(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    level = int(m.group(1))
    lo = float(m.group(2))
    hi = float(m.group(3))
    finding = Finding(stat_type="confidence_interval", raw_text=raw, line_number=line_no)

    if level not in (90, 95, 99):
        finding.issues.append(f"Unusual CI level: {level}%. Common levels are 90, 95, 99.")

    if lo >= hi:
        finding.issues.append(
            f"CI lower bound ({lo}) >= upper bound ({hi}). Bounds appear reversed."
        )
        finding.suggestions.append("Check that lower bound < upper bound.")

    return finding


def _check_t(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    df = m.group(1)
    t = float(m.group(2))
    finding = Finding(stat_type="t-statistic", raw_text=raw, line_number=line_no,
                      value=t, df=df)
    if int(df) < 1:
        finding.issues.append(f"Degrees of freedom ({df}) must be >= 1.")
    return finding


def _check_chi(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    df = m.group(1)
    chi = float(m.group(2))
    finding = Finding(stat_type="chi-square", raw_text=raw, line_number=line_no,
                      value=chi, df=df)
    if chi < 0:
        finding.issues.append(f"Chi-square value ({chi}) cannot be negative.")
    if int(df) < 1:
        finding.issues.append(f"Degrees of freedom ({df}) must be >= 1.")
    return finding


def _check_f(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    df1, df2 = m.group(1), m.group(2)
    f_val = float(m.group(3))
    finding = Finding(stat_type="F-statistic", raw_text=raw, line_number=line_no,
                      value=f_val, df=f"{df1},{df2}")
    if f_val < 0:
        finding.issues.append(f"F-statistic ({f_val}) cannot be negative.")
    return finding


def _check_r(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    r_val = float(m.group(2))
    finding = Finding(stat_type="correlation", raw_text=raw, line_number=line_no, value=r_val)
    if abs(r_val) > 1.0:
        finding.issues.append(f"Correlation r = {r_val} is outside [-1, 1].")
        finding.suggestions.append("Check for typo; Pearson r must be in [-1, 1].")
    return finding


def _check_effect(m: re.Match, line_no: int) -> Finding:
    raw = m.group(0)
    val = float(m.group(1))
    finding = Finding(stat_type="effect_size", raw_text=raw, line_number=line_no, value=val)
    if val < 0:
        finding.issues.append(
            "Effect size is negative. Cohen's d can be negative but eta-squared cannot."
        )
    return finding


# ---------------------------------------------------------------------------
# Audit engine
# ---------------------------------------------------------------------------

_CHECKERS = [
    (_P_PATTERN, _check_pvalue),
    (_CI_PATTERN, _check_ci),
    (_T_PATTERN, _check_t),
    (_CHI_PATTERN, _check_chi),
    (_F_PATTERN, _check_f),
    (_R_PATTERN, _check_r),
    (_EFFECT_PATTERN, _check_effect),
]


def audit_text(text: str, source: str = "<string>") -> AuditReport:
    """
    Audit a string of text for statistical reporting issues.

    Parameters
    ----------
    text : str
        The full text to audit.
    source : str
        Label for the source (e.g. filename) in the report.

    Returns
    -------
    AuditReport
    """
    report = AuditReport(source=source)
    summary: Dict[str, int] = {}
    lines = text.splitlines()

    for line_no, line in enumerate(lines, start=1):
        for pattern, checker in _CHECKERS:
            for m in pattern.finditer(line):
                finding = checker(m, line_no)
                report.findings.append(finding)
                summary[finding.stat_type] = summary.get(finding.stat_type, 0) + 1

    report.summary = summary

    # Document-level checks
    full_lower = text.lower()
    marginal_phrases = [
        "marginally significant", "trend toward significance",
        "approaching significance", "nearly significant", "borderline significant",
    ]
    for phrase in marginal_phrases:
        if phrase in full_lower:
            finding = Finding(
                stat_type="language_warning",
                raw_text=phrase,
                line_number=0,
                issues=[f"Avoid vague significance language: '{phrase}'."],
                suggestions=["Report exact p-value and confidence interval instead."],
            )
            report.findings.append(finding)

    return report


def audit_file(path: str) -> AuditReport:
    """
    Audit a plain-text or Markdown file.

    Parameters
    ----------
    path : str
        Path to the file to audit.

    Returns
    -------
    AuditReport
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    return audit_text(text, source=p.name)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in scientific manuscripts.",
    )
    parser.add_argument("input", help="Path to text or Markdown file to audit.")
    parser.add_argument("-o", "--output", default=None,
                        help="Write Markdown report to this path.")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print issues, not passing reports.")
    args = parser.parse_args()
    report = audit_file(args.input)
    md = report.to_markdown()
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(md)
    if report.issue_count:
        raise SystemExit(1)


if __name__ == "__main__":
    _cli()
