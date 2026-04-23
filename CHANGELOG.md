# Changelog

## [Unreleased]
- GRIM test for between-subjects means (#1)
- .docx manuscript input support (#2)
- APA style output for flagged errors (#3)

## [0.1.0] - 2026-04-23
### Added
- Statistical reporting audit for scientific manuscripts
- p-value, confidence interval, and effect size consistency checks
- Degrees of freedom verification against reported test statistics
- GRIM/SPRITE detection for implausible means
- PDF and plain-text manuscript input
- CLI: `stataudit check manuscript.pdf`
- Python API: `StatAuditor`, `AuditReport`
