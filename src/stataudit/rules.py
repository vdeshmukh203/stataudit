"""
Detection rules for statistical reporting errors.

Each rule is a 4-tuple: (name, compiled_pattern, severity, suggestion).
Patterns are matched against individual sentences of the manuscript.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import Severity

# Type alias for a single rule entry
Rule = Tuple[str, re.Pattern, Severity, str]

_RULES: List[Rule] = [
    # ── p-value reporting ──────────────────────────────────────────────────
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
        # Matches p = .0001, p = 0.0001, p = 0.00001, etc. (≥3 leading zeros after decimal)
        re.compile(r"\bp\s*=\s*0?\.0{3,}\d", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    # ── confidence intervals ───────────────────────────────────────────────
    (
        "ci_level_missing",
        # Flag "CI" or "confidence interval" NOT preceded by a digit (e.g., "95% CI" is OK)
        re.compile(r"(?<!\d\s)(?<!\d%\s)\b(?:CI|confidence interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI).",
    ),
    # ── test statistics ────────────────────────────────────────────────────
    (
        "t_test_df_missing",
        # t = value without (df) before the equals sign
        re.compile(r"\bt\s*=\s*[-+]?[\d.]+(?!\s*[,)]|\s*\()"),
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
        "effect_size_missing",
        # t(df)= or F(df,df)= present but no effect-size notation nearby
        re.compile(
            r"\b(?:t\(\d+\)|F\(\d+,\s*\d+\))\s*=\s*[-+]?[\d.]+"
            r"(?![^.]*?(?:cohen|effect\s*size|η²|η\s*2|d\s*=\s*[\d.]|r\s*=\s*[\d.]))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report an effect size (Cohen's d, η², etc.) alongside the test statistic.",
    ),
    # ── sample size ────────────────────────────────────────────────────────
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power.",
    ),
    # ── numeric precision ──────────────────────────────────────────────────
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 significant decimal places.",
    ),
    # ── test type ──────────────────────────────────────────────────────────
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification; report the justification.",
    ),
    # ── language / NHST ───────────────────────────────────────────────────
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and confidence intervals.",
    ),
    # ── data quality ───────────────────────────────────────────────────────
    (
        "outlier_handling",
        re.compile(r"\boutlier\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and proportion of points removed.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report proportion of missing data and the imputation or exclusion strategy.",
    ),
    # ── regression ─────────────────────────────────────────────────────────
    (
        "regression_r2_missing",
        # "regress*" not followed (within the sentence) by an R² notation
        re.compile(
            r"\bregress(?:ion|ed|es|ing)?\b"
            r"(?![^.]*?(?:R\s*[²^2]|R[-\s]?squared|adjusted\s+R))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report R² (and adjusted R² for multiple regression) alongside regression results.",
    ),
    # ── multiple comparisons ───────────────────────────────────────────────
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false\s+discovery|holm|benjamini|tukey|scheff[eé])\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Verify the multiple-comparisons correction method and adjusted threshold are stated.",
    ),
    # ── correlation ────────────────────────────────────────────────────────
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size alongside each correlation coefficient.",
    ),
    # ── reproducibility ────────────────────────────────────────────────────
    (
        "seed_unreported",
        re.compile(r"\brandom\s+seed\b", re.IGNORECASE),
        Severity.INFO,
        "Report the exact random seed value used for reproducibility.",
    ),
    (
        "mean_without_variance",
        re.compile(
            r"\bmean\s*(?:=|of|was|is)\s*[-+]?\d+(?:\.\d+)?"
            r"(?!\s*(?:±|\+/-|SD|SE|SEM|standard\s+deviation|\[))",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Report a variance measure (SD, SE, or 95% CI) alongside every mean.",
    ),
]
