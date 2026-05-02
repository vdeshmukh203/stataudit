# stataudit

Statistical reporting audit tool for academic manuscripts.

Scans plain-text documents for common statistical reporting errors — missing
confidence intervals, absent degrees of freedom, over-precise p-values,
undisclosed outlier handling, and more — and produces structured reports in
plain text, Markdown, or JSON.

Zero external dependencies (stdlib only).

## Installation

```bash
pip install stataudit
```

Or directly from source:

```bash
git clone https://github.com/vdeshmukh203/stataudit.git
cd stataudit
pip install -e .
```

## Quick Start

### Command line

```bash
# Audit a manuscript
stataudit paper.txt

# Filter to warnings and above, output Markdown
stataudit paper.txt --severity WARNING --format markdown

# Write report to file
stataudit paper.txt --format json --output audit.json

# List all detection rules
stataudit --list-rules
```

### Graphical interface

```bash
stataudit-gui
# or
python stataudit_gui.py
```

The GUI provides:
- Text editor with file-open and clipboard support
- Colour-coded findings table (sortable by column)
- Per-finding detail and suggestion panel
- Full formatted report (text / Markdown / JSON)
- One-click export of reports

### Python API

```python
from stataudit import audit_text, audit_file, AuditReport, Severity

# Audit a string
findings = audit_text("The result was ns. We found t = 2.5.")

for f in findings:
    print(f.severity.value, f.rule, f.suggestion)

# Build a structured report
report = AuditReport(source="paper.txt", findings=findings)
print(report.to_markdown())
print(report.to_json())

# Audit a file, report only warnings and errors
from pathlib import Path
findings = audit_file(Path("paper.txt"), min_severity=Severity.WARNING)
```

## Detection rules

| Rule | Severity | What it flags |
|------|----------|---------------|
| `pvalue_exact` | INFO | Exact p-values — verify precision |
| `pvalue_ns` | WARNING | "ns" instead of exact p-value |
| `pvalue_over_precision` | INFO | p-values with ≥ 4 leading zeros (use p < .001) |
| `ci_level_missing` | WARNING | CI/confidence interval without a % level |
| `t_test_df_missing` | WARNING | `t = value` without degrees of freedom |
| `anova_missing_df` | WARNING | `F = value` without degrees of freedom |
| `sample_size_small` | WARNING | N < 30 |
| `over_precision` | INFO | Numbers with > 4 decimal places |
| `one_tailed` | WARNING | One-tailed tests (require justification) |
| `nhst_only` | INFO | Significance language without effect sizes |
| `outlier_handling` | INFO | Outlier mentions without detection criterion |
| `missing_data` | INFO | Missing-data mentions without rate/strategy |
| `regression_r2_missing` | WARNING | Regression without R² |
| `multiple_comparisons` | INFO | Multiple-comparison corrections |
| `correlation_missing_n` | INFO | Correlation coefficient without sample size |
| `effect_size_check` | INFO | Effect size measures — verify labelling |

Run `stataudit --list-rules` for the full list with suggestions.

## Output formats

`--format text` (default) — plain-text report, one finding per block.  
`--format markdown` — Markdown with severity sections; paste into GitHub Issues.  
`--format json` — machine-readable; use for downstream processing or CI gates.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Audit complete; no ERROR-level findings |
| `1` | One or more ERROR-level findings detected |

## Citation

If you use stataudit in published research, please cite the associated JOSS
paper (under review):

```
Deshmukh, V. (2026). stataudit: A Python tool for automated statistical
reporting audits in machine learning papers. Journal of Open Source Software.
```

## License

MIT — see [LICENSE](LICENSE) for details.
