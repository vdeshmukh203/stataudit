# stataudit

Statistical reporting audit tool for scientific manuscripts.

Checks reported statistical results — p-values, confidence intervals, effect
sizes, sample sizes, and degrees of freedom — for internal consistency. Detects
common reporting errors including impossible p-values, mismatched degrees of
freedom, inconsistent sample sizes across tables, and violations of multiple
testing corrections.

## Installation

```bash
pip install stataudit
```

## Quick Start

```bash
# Audit a manuscript PDF
stataudit check manuscript.pdf

# Audit with HTML report output
stataudit check manuscript.txt --format apa --report audit_report.html
```

```python
from stataudit import StatAuditor, AuditReport

auditor = StatAuditor("manuscript.txt")
report: AuditReport = auditor.run()

for finding in report.findings:
    print(finding.severity, finding.message, finding.location)

report.save_html("audit_report.html")
```

## Features

- Extracts statistical values from plain text and PDF manuscripts
- Checks p-values against reported test statistics and degrees of freedom
- Detects GRIM and SPRITE violations for integer-constrained statistics
- Flags inconsistent sample sizes across tables and sections
- Outputs machine-readable JSON or human-readable HTML reports
- Supports APA, MLA, and Vancouver citation style contexts

## Documentation

See `docs/` for the full API reference and a catalogue of detectable error types.

## Citation

If you use `stataudit` in your research, please cite the associated JOSS paper
(under review).

## License

MIT — see [LICENSE](LICENSE) for details.
