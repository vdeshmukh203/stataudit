# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- GRIM/SPRITE test for integer-constrained means
- `.docx` manuscript input support
- APA-formatted HTML report output

## [0.1.0] — 2026-04-23

### Added
- Core `audit_text` and `audit_file` API for scanning manuscripts
- 18 rule-based checks across six categories: p-value reporting, confidence
  intervals, test statistics, effect sizes, methodology, and data disclosures
- Three-tier severity scheme: INFO, WARNING, ERROR
- `AuditReport` class with `to_text()`, `to_markdown()`, and `to_json()` output
- `stataudit` CLI with `--format`, `--severity`, `--output`, `--strict`,
  `--list-rules`, and `--version` flags
- `stataudit-gui` desktop application built on `tkinter` with file browser,
  pasted-text input, colour-coded findings panel, and report export
- Accurate line-number location tracking in `audit_file`
- New rules: `pvalue_zero`, `apa_p_format`, `seed_unreported`
- `__all__` public API declaration and `__version__` string
- `--strict` flag (exit code 1 on WARNING+ findings for CI use)
- 78-test suite covering every rule and all report formats
- MIT License, `CITATION.cff`, and JOSS `paper.md`
