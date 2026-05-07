"""Detection rules for statistical reporting issues."""
from __future__ import annotations

import re
from typing import List, Tuple

from .report import Severity

# Each rule is (name, compiled_pattern, severity, suggestion).
Rule = Tuple[str, "re.Pattern[str]", Severity, str]

RULES: List[Rule] = [
    # ------------------------------------------------------------------ p-values
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
    # ------------------------------------------------------------------ confidence intervals
    (
        "ci_level_missing",
        re.compile(r"(?<!%)(?<!% )\b(?:CI|confidence interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI).",
    ),
    # ------------------------------------------------------------------ test statistics
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
    # ------------------------------------------------------------------ sample size
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power and report it.",
    ),
    # ------------------------------------------------------------------ precision / formatting
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — round to 2–3 significant decimal places.",
    ),
    # ------------------------------------------------------------------ test choice
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification; state the rationale.",
    ),
    # ------------------------------------------------------------------ language / NHST
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and confidence intervals.",
    ),
    (
        "effect_size_missing",
        re.compile(
            r"\bstatistically significant\b(?![^.]*(?:Cohen|η[²2]|ω[²2]|ε[²2]|\bd\b|r\s*=|R[²2]))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report an effect size (Cohen's d, η², r) alongside significance statements.",
    ),
    # ------------------------------------------------------------------ data handling
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
    # ------------------------------------------------------------------ regression
    (
        "regression_r2_missing",
        re.compile(r"\bregress(?:ed|ion|ing)\b(?![^.]*R[²2²])", re.IGNORECASE),
        Severity.WARNING,
        "Report R² (and adjusted R²) alongside regression results.",
    ),
    # ------------------------------------------------------------------ multiple comparisons
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false discovery|holm|benjamini|hochberg)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "State the correction method and the resulting adjusted alpha level.",
    ),
    # ------------------------------------------------------------------ correlation
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size alongside the correlation coefficient.",
    ),
    # ------------------------------------------------------------------ variance reporting
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
