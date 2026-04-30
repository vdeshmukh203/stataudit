---
title: 'stataudit: A Python tool for automated statistical reporting audits in scientific manuscripts'
tags:
  - Python
  - statistics
  - reproducibility
  - scientific-writing
  - auditing
authors:
  - name: Vaibhav Deshmukh
    orcid: 0000-0001-6745-7062
    affiliation: 1
affiliations:
  - name: Independent Researcher, Nagpur, India
    index: 1
date: 23 April 2026
bibliography: paper.bib
---

# Summary

`stataudit` is an open-source Python command-line tool that automatically audits the statistical reporting quality of scientific manuscripts. Given a plain-text or Markdown input file, the tool applies a curated set of rule-based checks derived from established reporting guidelines for empirical research [@pineau2021improving; @stodden2016enhancing] and flags potential issues such as missing confidence intervals, unreported degrees of freedom, absent effect sizes, informal significance notation, violations of APA formatting conventions, and missing reproducibility disclosures. Each flagged item is returned with a precise location (line number for file input, sentence index for programmatic use), a three-tier severity level (INFO, WARNING, or ERROR), and an actionable suggestion. Reports can be emitted as plain text, Markdown, or machine-readable JSON to support integration into author workflows, peer-review checklists, and automated continuous-integration pipelines. A graphical desktop interface built on Python's standard `tkinter` library is also provided for interactive use.

# Statement of Need

Inadequate statistical reporting is a well-documented problem in empirical science, including machine learning research. Systematic surveys have identified high rates of missing variance estimates, absent confidence intervals, unreported random seeds, and the use of informal significance labels such as "ns" instead of exact p-values [@gundersen2018state]. Existing automated checking tools either require access to proprietary journal submission systems, focus on a narrow class of errors such as p-value recalculation [@nuijten2016prevalence], or impose heavy software dependencies that limit adoption in lightweight author workflows. `stataudit` fills this gap with a zero-dependency, stdlib-only Python tool that authors can run locally before submission or embed directly into a continuous-integration pipeline. By automating a first-pass review against a configurable rule checklist, `stataudit` lowers the cost of quality control for both individual researchers and large-scale meta-research studies of reporting practice.

# Implementation

`stataudit` is implemented in pure Python (≥ 3.8) with no third-party runtime dependencies. At its core, `audit_text` segments a manuscript into sentences using a regular-expression splitter, then matches each sentence against an ordered list of `(name, pattern, severity, suggestion)` rule tuples. Character-offset bookkeeping in `audit_file` maps each finding to an accurate line number in the source file. The public API is minimal: `audit_text` accepts a string and returns a list of `Finding` dataclass instances; `audit_file` accepts a `pathlib.Path` and does the same with line-level location metadata; `AuditReport` aggregates findings and serialises them to text, Markdown, or JSON.

The rule set covers 18 common reporting issues across six categories:

| Category | Rules |
|---|---|
| p-value reporting | `pvalue_exact`, `pvalue_ns`, `pvalue_zero`, `pvalue_over_precision`, `apa_p_format` |
| Confidence intervals | `ci_level_missing` |
| Test statistics | `t_test_df_missing`, `anova_missing_df` |
| Effect sizes & sample size | `sample_size_small`, `nhst_only`, `correlation_missing_n`, `regression_r2_missing` |
| Reporting precision & methodology | `over_precision`, `one_tailed`, `multiple_comparisons` |
| Data quality & reproducibility | `outlier_handling`, `missing_data`, `seed_unreported` |

Severity levels follow a three-tier scheme: INFO (advisory, e.g. verifying APA number formatting), WARNING (likely incomplete or non-standard report, e.g. missing confidence-interval level), and ERROR (reserved for future programmatic escalation). The `--strict` CLI flag treats WARNING-level findings as errors for use in automated gatekeeping.

The optional graphical interface (`stataudit-gui`) provides a file browser, inline text editor, severity filter, colour-coded findings panel, and report export in all supported formats, all built on the standard `tkinter` library.

# Acknowledgements

The author used Claude (Anthropic) for drafting portions of this manuscript and for software development assistance. All scientific claims and design decisions are the author's own.

# References
