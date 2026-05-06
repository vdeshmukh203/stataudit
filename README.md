# stataudit

Statistical reporting audit tool for scientific manuscripts.

Checks reported statistical results — p-values, confidence intervals, effect
sizes, sample sizes, and degrees of freedom — for common reporting errors and
omissions. Runs on plain text input with no external dependencies.

## Installation

```bash
pip install stataudit
```

Or install from source:

```bash
git clone https://github.com/vdeshmukh203/stataudit
cd stataudit
pip install -e .
```

## Quick Start

### Command line

```bash
# Audit a manuscript (plain text)
stataudit manuscript.txt

# Show only warnings and errors
stataudit manuscript.txt --severity WARNING

# Output a Markdown report
stataudit manuscript.txt --format markdown --output report.md

# Output machine-readable JSON
stataudit manuscript.txt --format json

# Pipe from stdin
cat manuscript.txt | stataudit

# List all detection rules
stataudit --list-rules

# Launch the graphical interface
stataudit --gui
# or
stataudit-gui
```

### Python API

```python
from stataudit import audit_text, audit_file, AuditReport, StatAuditor, Severity
from pathlib import Path

# Audit raw text
findings = audit_text("The result was significant (t = 3.14, p = .045).")
for f in findings:
    print(f.severity.value, f.rule, f.location, f.suggestion)

# Audit a file
findings = audit_file(Path("manuscript.txt"))

# Use AuditReport for formatted output
report = AuditReport(source="manuscript.txt", findings=findings)
print(report.to_text())      # plain text
print(report.to_markdown())  # Markdown
print(report.to_json())      # JSON

# High-level StatAuditor (auto-detects file vs. raw text)
auditor = StatAuditor("manuscript.txt", min_severity=Severity.WARNING)
report = auditor.run()
print(report.summary)
```

## Graphical Interface

Launch the GUI with:

```bash
stataudit --gui
# or
stataudit-gui
```

The GUI provides:
- Paste or open a manuscript text file
- Choose minimum severity threshold (INFO / WARNING / ERROR)
- Interactive findings table with colour-coded severity
- Detail pane with full suggestion text
- Export reports as plain text, Markdown, or JSON
- Rule reference browser (Help → Rule Reference)

## Detection Rules

| Severity | Rule | Description |
|----------|------|-------------|
| ERROR | `pvalue_impossible` | p-value > 1.0 (statistically impossible) |
| ERROR | `pvalue_negative` | Negative p-value (statistically impossible) |
| WARNING | `pvalue_ns` | `ns` used instead of an exact p-value |
| WARNING | `ci_level_missing` | CI reported without a confidence level (e.g. 95%) |
| WARNING | `t_test_df_missing` | t statistic reported without degrees of freedom |
| WARNING | `anova_missing_df` | F statistic reported without degrees of freedom |
| WARNING | `sample_size_small` | N < 30 — statistical power may be insufficient |
| WARNING | `one_tailed` | One-tailed test mentioned (requires a priori justification) |
| WARNING | `regression_r2_missing` | Regression mentioned without R² |
| INFO | `pvalue_exact` | Exact p-value present — verify precision |
| INFO | `pvalue_over_precision` | p-value reported with more than 3 decimal places |
| INFO | `over_precision` | Number with 5+ decimal places — excessive precision |
| INFO | `nhst_only` | Significance language without effect sizes or CIs |
| INFO | `outlier_handling` | Outlier mention — verify detection criterion stated |
| INFO | `missing_data` | Missing-data mention — verify imputation strategy stated |
| INFO | `multiple_comparisons` | Correction method mentioned — verify it is stated |
| INFO | `correlation_missing_n` | Correlation coefficient without sample size |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No ERROR-level findings |
| `1` | One or more ERROR-level findings, or input file not found |

## Citation

If you use `stataudit` in your research, please cite the associated JOSS paper
(under review).

## License

MIT — see [LICENSE](LICENSE) for details.
