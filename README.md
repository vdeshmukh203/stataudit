# stataudit

Statistical reporting audit tool for scientific manuscripts.

Checks reported statistical results — p-values, confidence intervals, effect
sizes, sample sizes, and degrees of freedom — against common best-practice
guidelines. Detects issues such as missing confidence-level specifications,
t-tests or F-tests reported without degrees of freedom, over-precise p-values,
underpowered samples, and NHST language without effect sizes.

## Installation

```bash
pip install stataudit
```

## Quick Start

### Command line

```bash
# Audit a plain-text or LaTeX manuscript
stataudit manuscript.txt

# Save a Markdown report
stataudit manuscript.txt --format markdown -o report.md

# Only show WARNING-level and above
stataudit --severity WARNING manuscript.txt

# Pipe text directly
echo "The result was significant (t = 3.2, ns)." | stataudit

# List all built-in detection rules
stataudit --list-rules
```

### Python API

```python
from stataudit import audit_text, audit_file, AuditReport

# Audit a string
findings = audit_text("The result was significant (t = 3.2, ns).")
report = AuditReport(source="example", findings=findings)

print(report.to_text())      # plain text
print(report.to_markdown())  # GitHub-flavoured Markdown
print(report.to_json())      # machine-readable JSON

# Audit a file
from pathlib import Path
findings = audit_file(Path("manuscript.txt"))
report = AuditReport(source="manuscript.txt", findings=findings)
```

### Graphical interface

```bash
stataudit-gui
```

The GUI lets you browse for a file (or paste text directly), choose a minimum
severity, run the audit, browse colour-coded results in a sortable table, and
export reports to text, JSON, or Markdown.

## Features

- Detects 15 categories of statistical reporting issues (p-values, CIs, effect
  sizes, degrees of freedom, sample size, precision, multiple comparisons, …)
- Three severity levels: INFO, WARNING, ERROR
- Output formats: plain text, Markdown, JSON
- Graphical interface (requires `tkinter`, bundled with standard Python)
- Stdlib-only — zero runtime dependencies
- Fully typed, documented, and tested

## Detection rules

| Rule | Severity | Description |
|------|----------|-------------|
| `pvalue_exact` | INFO | p-value reported (check precision) |
| `pvalue_ns` | WARNING | "ns" instead of exact p-value |
| `pvalue_over_precision` | INFO | p < .0001 should be p < .001 |
| `ci_level_missing` | WARNING | CI without confidence level |
| `t_test_df_missing` | WARNING | t-test without degrees of freedom |
| `anova_missing_df` | WARNING | F-test without degrees of freedom |
| `sample_size_small` | WARNING | N < 30 |
| `over_precision` | INFO | More than 4 decimal places |
| `one_tailed` | WARNING | One-tailed test without justification |
| `nhst_only` | INFO | Significance language without effect sizes |
| `outlier_handling` | INFO | Outliers mentioned without criterion |
| `missing_data` | INFO | Missing data without strategy |
| `regression_r2_missing` | WARNING | Regression without R² |
| `multiple_comparisons` | INFO | Correction method mentioned |
| `correlation_missing_n` | INFO | Correlation without sample size |

## Citation

If you use `stataudit` in your research, please cite the associated JOSS paper
(under review).

## License

MIT — see [LICENSE](LICENSE) for details.
