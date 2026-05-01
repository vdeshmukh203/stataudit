# stataudit

Statistical reporting audit tool for scientific manuscripts.

Checks reported statistical results — p-values, confidence intervals, effect
sizes, sample sizes, and degrees of freedom — for common omissions and
formatting errors.  Detects issues including imprecise p-values, missing
degrees of freedom, unreported confidence-interval levels, absent effect sizes,
and more.

**Stdlib-only.** No external dependencies required.

## Installation

```bash
pip install stataudit
```

Or run directly from the repository:

```bash
python stataudit.py manuscript.txt
```

## Quick Start

### Command-line interface

```bash
# Audit a text file (plain text output)
stataudit manuscript.txt

# Filter to WARNING and above; write HTML report
stataudit manuscript.txt --severity WARNING --format html --output report.html

# Pipe from stdin
cat manuscript.txt | stataudit --format markdown

# List all detection rules
stataudit --list-rules
```

Available `--format` values: `text` (default), `markdown`, `json`, `html`.

### Python API

```python
from stataudit import StatAuditor, AuditReport, Severity

# Audit a file
auditor = StatAuditor("manuscript.txt")
report: AuditReport = auditor.run()

for finding in report.findings:
    print(finding.severity, finding.rule, finding.location)
    print("  →", finding.suggestion)

# Export formats
report.save_html("audit_report.html")
print(report.to_markdown())
print(report.to_json())

# Audit a raw text string directly
from stataudit import audit_text, Severity

findings = audit_text(
    "The result was significant (ns), t = 3.14, p < .05.",
    min_severity=Severity.WARNING,
)
```

### Graphical user interface

```bash
# Launch the Tkinter desktop GUI
stataudit-gui
# or
python stataudit_gui.py
```

The GUI provides:
- File open dialog and in-app text editor
- Color-coded findings table (sortable by column)
- Severity filter drop-down
- Suggestion panel for the selected finding
- Export to text / Markdown / JSON / HTML

## Features

| Rule | Severity | What it checks |
|------|----------|----------------|
| `pvalue_exact` | INFO | p-value precision and APA formatting |
| `pvalue_ns` | WARNING | Replace "ns" with an exact p-value |
| `pvalue_over_precision` | INFO | p = .00001 should be p < .001 |
| `ci_level_missing` | WARNING | CI mentioned without confidence level |
| `t_test_df_missing` | WARNING | t = X without degrees of freedom |
| `anova_missing_df` | WARNING | F = X without degrees of freedom |
| `sample_size_small` | WARNING | N < 30 — check statistical power |
| `over_precision` | INFO | More than 4 decimal places |
| `one_tailed` | WARNING | One-tailed tests need justification |
| `nhst_only` | INFO | Add effect sizes alongside significance |
| `outlier_handling` | INFO | Describe outlier-detection criterion |
| `missing_data` | INFO | Report proportion and imputation strategy |
| `regression_r2_missing` | WARNING | Report R² with regression results |
| `multiple_comparisons` | INFO | Verify correction is fully specified |
| `correlation_missing_n` | INFO | Report N with correlation coefficients |

## Citation

If you use `stataudit` in your research, please cite the associated JOSS paper
(under review).

## License

MIT — see [LICENSE](LICENSE) for details.
