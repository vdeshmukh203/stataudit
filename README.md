# stataudit

Automated statistical reporting auditor for scientific manuscripts.

Scans plain-text or Markdown manuscripts for common statistical reporting
errors and incomplete disclosures: missing confidence-interval levels,
unreported degrees of freedom, absent effect sizes, informal significance
notation, APA formatting violations, and reproducibility gaps.

## Installation

```bash
pip install stataudit
```

Requires Python ≥ 3.8.  No third-party dependencies.

## Quick Start

### Command line

```bash
# Audit a manuscript and print a plain-text report
stataudit manuscript.txt

# Markdown report saved to file
stataudit manuscript.txt --format markdown --output report.md

# JSON output for downstream tooling
stataudit manuscript.txt --format json

# Read from stdin
cat abstract.txt | stataudit

# Show only warnings and above; return exit code 1 if any are found
stataudit manuscript.txt --severity WARNING --strict

# List all available detection rules
stataudit --list-rules
```

### Python API

```python
from stataudit import audit_text, audit_file, AuditReport, Severity
from pathlib import Path

# Audit a string directly
findings = audit_text("The result was significant (ns, t = 2.3).")
for f in findings:
    print(f.severity.value, f.rule, f.location)
    print(" ", f.suggestion)

# Audit a file (findings include line numbers)
findings = audit_file(Path("manuscript.txt"))
report = AuditReport(source="manuscript.txt", findings=findings)

print(report.to_text())      # plain text
print(report.to_markdown())  # Markdown
print(report.to_json())      # JSON
```

### Graphical interface

```bash
stataudit-gui
```

Opens a desktop window where you can paste text or load a file, apply
severity filters, view colour-coded findings, and export reports.

## Detection rules

| Rule | Severity | Description |
|------|----------|-------------|
| `pvalue_exact` | INFO | Verify APA format for exact p-values |
| `pvalue_ns` | WARNING | Replace informal "ns" with an exact p-value |
| `pvalue_zero` | WARNING | `p = 0` is impossible; use `p < .001` |
| `pvalue_over_precision` | INFO | Extremely small p-values should use `p < .001` |
| `apa_p_format` | INFO | Omit leading zero: `p = .034` not `p = 0.034` |
| `ci_level_missing` | WARNING | Specify the confidence level (e.g., 95% CI) |
| `t_test_df_missing` | WARNING | Include degrees of freedom: `t(df) = value` |
| `anova_missing_df` | WARNING | Include both df: `F(df1, df2) = value` |
| `sample_size_small` | WARNING | N < 30 — verify statistical power |
| `nhst_only` | INFO | Supplement significance language with effect sizes |
| `correlation_missing_n` | INFO | Report N alongside correlation coefficient |
| `regression_r2_missing` | WARNING | Report R² alongside regression results |
| `over_precision` | INFO | Excessive decimal places (≥ 5) |
| `one_tailed` | WARNING | One-tailed tests require explicit justification |
| `multiple_comparisons` | INFO | Confirm correction method is stated |
| `outlier_handling` | INFO | Describe the outlier detection criterion |
| `missing_data` | INFO | Report proportion and imputation strategy |
| `seed_unreported` | INFO | Report random seed for reproducibility |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | No ERROR-level findings (or no WARNING+ with `--strict`) |
| 1 | ERROR-level findings present (or WARNING+ with `--strict`) |
| 2 | Input file not found |

## Continuous integration

```yaml
# .github/workflows/stataudit.yml
- name: Audit manuscript
  run: stataudit paper.txt --severity WARNING --strict
```

## Citation

If you use `stataudit` in your research, please cite the associated JOSS paper
(under review).  See `CITATION.cff` for machine-readable citation metadata.

## License

MIT — see [LICENSE](LICENSE) for details.
