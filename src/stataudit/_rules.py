"""Compiled rule definitions for statistical reporting checks."""
from __future__ import annotations

import re

from .report import Severity

# Each entry: (rule_name, compiled_pattern, severity, suggestion)
RULES = [
    # ------------------------------------------------------------------ p-values
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "pvalue_threshold",
        re.compile(r"\bp\s*[=<>]\s*0?\.0[15]\b", re.IGNORECASE),
        Severity.WARNING,
        "Round-number p-value (p = .05, p = .01) may indicate threshold anchoring — report exact value.",
    ),
    (
        "pvalue_over_precision",
        re.compile(r"\bp\s*[=<>]\s*0?\.0{4,}\d*\b", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "nhst_language",
        re.compile(r"\b(?:significant(?:ly)?|insignificant(?:ly)?|failed\s+to\s+reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with exact p-value, effect size, and CI.",
    ),
    # -------------------------------------------------- confidence intervals
    (
        "ci_level_missing",
        re.compile(r"\b(?:CI|confidence\s+interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level and bounds (e.g., 95% CI [2.1, 4.3]).",
    ),
    # --------------------------------------- test statistics — missing df
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
    (
        "chi_square_df_missing",
        re.compile(r"\b(?:chi.?square|χ²?)\s*=\s*[-+]?[\d.]+(?!\s*\()", re.IGNORECASE),
        Severity.WARNING,
        "Include degrees of freedom and N: χ²(df, N = n) = value.",
    ),
    # ------------------------------------------ effect sizes (reminder)
    (
        "effect_size_missing",
        re.compile(r"\bt\s*\(\d+\)\s*=|F\s*\(\d+\s*,\s*\d+\)\s*=", re.IGNORECASE),
        Severity.INFO,
        "Report effect size (Cohen's d, η², ω², or r) alongside the test statistic.",
    ),
    # ---------------------------------------------------- sample size
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power and justify sample size.",
    ),
    # ------------------------------------------------------- precision
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 significant decimal places.",
    ),
    # ------------------------------------------------ testing approach
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification — state it explicitly.",
    ),
    # ------------------------------------------------------- data quality
    (
        "outlier_handling",
        re.compile(r"\boutlier\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and number of cases excluded.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report the proportion of missing data and the imputation strategy.",
    ),
    # -------------------------------------------------------- regression
    (
        "regression_r2_missing",
        re.compile(
            r"\bregress(?:ed|ion)\b(?![^.]*(?:R[\-\s]?squared|R²|adj\w*\s+R))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report R² (and adjusted R²) alongside regression results.",
    ),
    # ------------------------------------------ multiple comparisons
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false\s+discovery|holm|benjamini)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Verify the multiple-comparisons correction method and α level are stated.",
    ),
    # ------------------------------------------------------- correlation
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size alongside the correlation coefficient.",
    ),
    # ---------------------------------------------- ML reproducibility
    (
        "missing_variance",
        re.compile(
            r"\b(?:mean|average|avg)\s+(?:accuracy|performance|score|AUC|F1|BLEU|ROUGE|mAP)\b"
            r"(?![^.]*(?:SD|std|±|\+/-|standard\s+deviation|confidence\s+interval|\bCI\b))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report variance (SD, 95% CI, or IQR) alongside mean performance metrics.",
    ),
    (
        "random_seed",
        re.compile(r"\b(?:random\s+seed|seed(?:ed)?)\b", re.IGNORECASE),
        Severity.INFO,
        "State the random seed value(s) and number of repetitions for reproducibility.",
    ),
]
