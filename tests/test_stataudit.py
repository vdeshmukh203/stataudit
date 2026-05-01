"""
Comprehensive test suite for stataudit.

Covers:
  - Public API surface (imports, classes, callables)
  - Severity ordering and equality
  - Finding serialisation
  - All 15 detection rules (positive and negative cases)
  - AuditReport output formats (text, markdown, json, html)
  - StatAuditor convenience class
  - audit_file with a temporary file
  - Severity filter propagation
  - CLI (--list-rules, stdin, --format, error handling)
"""

from __future__ import annotations

import io
import json
import sys
import pathlib
import tempfile

# Make the repo root importable when running with plain pytest from any cwd.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import stataudit as sa


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

def test_public_names():
    for name in ("AuditReport", "Finding", "Severity", "StatAuditor",
                 "audit_text", "audit_file", "main"):
        assert hasattr(sa, name), f"missing public name: {name}"


def test_version_present():
    assert hasattr(sa, "__version__")
    assert isinstance(sa.__version__, str)


def test_callables():
    assert callable(sa.audit_text)
    assert callable(sa.audit_file)
    assert callable(sa.main)


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

def test_severity_ordering():
    assert sa.Severity.INFO < sa.Severity.WARNING
    assert sa.Severity.WARNING < sa.Severity.ERROR
    assert sa.Severity.ERROR > sa.Severity.INFO
    assert sa.Severity.INFO <= sa.Severity.INFO
    assert sa.Severity.WARNING >= sa.Severity.WARNING
    assert not (sa.Severity.ERROR < sa.Severity.WARNING)


def test_severity_equality():
    assert sa.Severity.INFO == sa.Severity.INFO
    assert sa.Severity.WARNING != sa.Severity.ERROR


def test_severity_hashable():
    s = {sa.Severity.INFO, sa.Severity.WARNING, sa.Severity.ERROR}
    assert len(s) == 3


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

def _make_finding(**kwargs) -> sa.Finding:
    defaults = dict(rule="test", text="snippet", location="line 1",
                    severity=sa.Severity.WARNING, suggestion="Fix it.")
    defaults.update(kwargs)
    return sa.Finding(**defaults)


def test_finding_str_contains_severity():
    f = _make_finding(severity=sa.Severity.ERROR)
    assert "ERROR" in str(f)


def test_finding_str_contains_rule():
    f = _make_finding(rule="my_rule")
    assert "my_rule" in str(f)


def test_finding_to_dict_severity_is_string():
    f = _make_finding(severity=sa.Severity.INFO)
    d = f.to_dict()
    assert d["severity"] == "INFO"
    assert isinstance(d["severity"], str)


def test_finding_to_dict_fields():
    f = _make_finding()
    d = f.to_dict()
    for key in ("rule", "text", "location", "severity", "suggestion"):
        assert key in d


# ---------------------------------------------------------------------------
# audit_text — basic behaviour
# ---------------------------------------------------------------------------

def test_audit_text_empty_string():
    assert sa.audit_text("") == []


def test_audit_text_whitespace_only():
    assert sa.audit_text("   \n  ") == []


def test_audit_text_returns_list():
    result = sa.audit_text("The p-value was significant.")
    assert isinstance(result, list)


def test_audit_text_location_format():
    findings = sa.audit_text("The effect was ns.")
    assert findings, "expected at least one finding"
    assert findings[0].location.startswith("sentence ")


# ---------------------------------------------------------------------------
# Rule: pvalue_exact (INFO)
# ---------------------------------------------------------------------------

def test_rule_pvalue_exact_detected():
    rules = {f.rule for f in sa.audit_text("We found p = .034.")}
    assert "pvalue_exact" in rules


def test_rule_pvalue_less_than_detected():
    rules = {f.rule for f in sa.audit_text("The result was p < .001.")}
    assert "pvalue_exact" in rules


# ---------------------------------------------------------------------------
# Rule: pvalue_ns (WARNING)
# ---------------------------------------------------------------------------

def test_rule_pvalue_ns_bare():
    rules = {f.rule for f in sa.audit_text("The difference was ns.")}
    assert "pvalue_ns" in rules


def test_rule_pvalue_ns_parenthesised():
    rules = {f.rule for f in sa.audit_text("The result was not significant (ns).")}
    assert "pvalue_ns" in rules


def test_rule_pvalue_ns_no_false_positive_on_exact():
    # A properly reported p-value should not trigger pvalue_ns
    rules = {f.rule for f in sa.audit_text("We found p = .12, which was not significant.")}
    assert "pvalue_ns" not in rules


# ---------------------------------------------------------------------------
# Rule: pvalue_over_precision (INFO)
# ---------------------------------------------------------------------------

def test_rule_pvalue_over_precision_detected():
    rules = {f.rule for f in sa.audit_text("We found p = .000012.")}
    assert "pvalue_over_precision" in rules


def test_rule_pvalue_over_precision_no_false_positive():
    rules = {f.rule for f in sa.audit_text("We found p = .034.")}
    assert "pvalue_over_precision" not in rules


# ---------------------------------------------------------------------------
# Rule: ci_level_missing (WARNING)
# ---------------------------------------------------------------------------

def test_rule_ci_level_missing_bare_ci():
    rules = {f.rule for f in sa.audit_text("The CI was very wide.")}
    assert "ci_level_missing" in rules


def test_rule_ci_level_missing_bare_confidence_interval():
    rules = {f.rule for f in sa.audit_text("A confidence interval was not reported.")}
    assert "ci_level_missing" in rules


def test_rule_ci_level_missing_not_flagged_when_level_present():
    rules = {f.rule for f in sa.audit_text("The 95% CI was [0.5, 1.5].")}
    assert "ci_level_missing" not in rules


# ---------------------------------------------------------------------------
# Rule: t_test_df_missing (WARNING)
# ---------------------------------------------------------------------------

def test_rule_t_test_df_missing_detected():
    rules = {f.rule for f in sa.audit_text("We found t = 3.14, p < .05.")}
    assert "t_test_df_missing" in rules


def test_rule_t_test_df_missing_not_flagged_when_df_present():
    rules = {f.rule for f in sa.audit_text("We found t(29) = 3.14, p < .05.")}
    assert "t_test_df_missing" not in rules


# ---------------------------------------------------------------------------
# Rule: anova_missing_df (WARNING)
# ---------------------------------------------------------------------------

def test_rule_anova_missing_df_detected():
    rules = {f.rule for f in sa.audit_text("The ANOVA showed F = 5.43, p < .001.")}
    assert "anova_missing_df" in rules


def test_rule_anova_missing_df_not_flagged_when_df_present():
    rules = {f.rule for f in sa.audit_text("The ANOVA showed F(2, 47) = 5.43, p < .001.")}
    assert "anova_missing_df" not in rules


# ---------------------------------------------------------------------------
# Rule: sample_size_small (WARNING)
# ---------------------------------------------------------------------------

def test_rule_sample_size_small_detected():
    rules = {f.rule for f in sa.audit_text("We recruited N = 15 participants.")}
    assert "sample_size_small" in rules


def test_rule_sample_size_small_not_flagged_large_n():
    rules = {f.rule for f in sa.audit_text("We recruited N = 120 participants.")}
    assert "sample_size_small" not in rules


# ---------------------------------------------------------------------------
# Rule: over_precision (INFO)
# ---------------------------------------------------------------------------

def test_rule_over_precision_detected():
    rules = {f.rule for f in sa.audit_text("The mean was 3.141592 seconds.")}
    assert "over_precision" in rules


def test_rule_over_precision_not_flagged_short():
    rules = {f.rule for f in sa.audit_text("The mean was 3.14 seconds.")}
    assert "over_precision" not in rules


# ---------------------------------------------------------------------------
# Rule: one_tailed (WARNING)
# ---------------------------------------------------------------------------

def test_rule_one_tailed_hyphen():
    rules = {f.rule for f in sa.audit_text("We used a one-tailed test.")}
    assert "one_tailed" in rules


def test_rule_one_tailed_no_hyphen():
    rules = {f.rule for f in sa.audit_text("A one tailed test was applied.")}
    assert "one_tailed" in rules


# ---------------------------------------------------------------------------
# Rule: nhst_only (INFO)
# ---------------------------------------------------------------------------

def test_rule_nhst_only_significant():
    rules = {f.rule for f in sa.audit_text("The effect was significant.")}
    assert "nhst_only" in rules


def test_rule_nhst_only_insignificant():
    rules = {f.rule for f in sa.audit_text("The result was insignificant.")}
    assert "nhst_only" in rules


def test_rule_nhst_only_failed_to_reject():
    rules = {f.rule for f in sa.audit_text("We failed to reject the null hypothesis.")}
    assert "nhst_only" in rules


# ---------------------------------------------------------------------------
# Rule: outlier_handling (INFO)
# ---------------------------------------------------------------------------

def test_rule_outlier_handling_detected():
    rules = {f.rule for f in sa.audit_text("Three outliers were removed.")}
    assert "outlier_handling" in rules


# ---------------------------------------------------------------------------
# Rule: missing_data (INFO)
# ---------------------------------------------------------------------------

def test_rule_missing_data_detected():
    rules = {f.rule for f in sa.audit_text("There were missing values in the dataset.")}
    assert "missing_data" in rules


def test_rule_missing_data_cases():
    rules = {f.rule for f in sa.audit_text("Missing cases were excluded listwise.")}
    assert "missing_data" in rules


# ---------------------------------------------------------------------------
# Rule: regression_r2_missing (WARNING)
# ---------------------------------------------------------------------------

def test_rule_regression_r2_missing_detected():
    rules = {f.rule for f in sa.audit_text("We used regression to predict the outcome.")}
    assert "regression_r2_missing" in rules


def test_rule_regression_r2_missing_not_flagged_when_r2_present():
    rules = {f.rule for f in sa.audit_text(
        "We used regression to predict the outcome (R2 = .45)."
    )}
    assert "regression_r2_missing" not in rules


# ---------------------------------------------------------------------------
# Rule: multiple_comparisons (INFO)
# ---------------------------------------------------------------------------

def test_rule_multiple_comparisons_bonferroni():
    rules = {f.rule for f in sa.audit_text("We applied a Bonferroni correction.")}
    assert "multiple_comparisons" in rules


def test_rule_multiple_comparisons_fdr():
    rules = {f.rule for f in sa.audit_text("FDR correction was used.")}
    assert "multiple_comparisons" in rules


# ---------------------------------------------------------------------------
# Rule: correlation_missing_n (INFO)
# ---------------------------------------------------------------------------

def test_rule_correlation_missing_n_detected():
    rules = {f.rule for f in sa.audit_text("We found r = 0.45 between the variables.")}
    assert "correlation_missing_n" in rules


# ---------------------------------------------------------------------------
# Severity filter
# ---------------------------------------------------------------------------

def test_severity_filter_warning_excludes_info():
    findings = sa.audit_text(
        "The effect was significant. t = 3.14.",
        min_severity=sa.Severity.WARNING,
    )
    for f in findings:
        assert f.severity >= sa.Severity.WARNING


def test_severity_filter_error_returns_empty_for_typical_text():
    # Standard audit text produces at most WARNING; ERROR level is unused by current rules.
    findings = sa.audit_text("The result was ns.", min_severity=sa.Severity.ERROR)
    for f in findings:
        assert f.severity == sa.Severity.ERROR


# ---------------------------------------------------------------------------
# AuditReport output formats
# ---------------------------------------------------------------------------

def _sample_report() -> sa.AuditReport:
    findings = sa.audit_text("The effect was ns and t = 3.14.")
    return sa.AuditReport(source="test.txt", findings=findings)


def test_report_summary_keys():
    r = _sample_report()
    s = r.summary
    assert "total" in s
    assert "by_severity" in s
    assert s["total"] == len(r.findings)


def test_report_to_text_contains_rule():
    r = _sample_report()
    assert "pvalue_ns" in r.to_text()


def test_report_to_text_empty():
    r = sa.AuditReport(source="empty.txt", findings=[])
    assert "No findings" in r.to_text()


def test_report_to_markdown_header():
    r = _sample_report()
    md = r.to_markdown()
    assert "# Statistical Audit Report" in md


def test_report_to_markdown_empty():
    r = sa.AuditReport(source="empty.txt", findings=[])
    md = r.to_markdown()
    assert "_No findings._" in md


def test_report_to_json_parseable():
    r = _sample_report()
    data = json.loads(r.to_json())
    assert "findings" in data
    assert "summary" in data
    assert isinstance(data["findings"], list)


def test_report_to_json_severity_is_string():
    r = _sample_report()
    data = json.loads(r.to_json())
    for f in data["findings"]:
        assert isinstance(f["severity"], str)


def test_report_to_html_is_html():
    r = _sample_report()
    html = r.to_html()
    assert "<!DOCTYPE html>" in html
    assert "<table>" in html


def test_report_to_html_empty():
    r = sa.AuditReport(source="empty.txt", findings=[])
    html = r.to_html()
    assert "No findings" in html


def test_report_save_html(tmp_path):
    r = _sample_report()
    out = tmp_path / "report.html"
    r.save_html(out)
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


# ---------------------------------------------------------------------------
# StatAuditor facade
# ---------------------------------------------------------------------------

def test_stat_auditor_text_input():
    auditor = sa.StatAuditor("The effect was ns and t = 3.14.")
    report = auditor.run()
    assert isinstance(report, sa.AuditReport)
    assert len(report.findings) > 0
    assert report.source == "<text>"


def test_stat_auditor_file_input(tmp_path):
    f = tmp_path / "ms.txt"
    f.write_text("The result was ns and t = 2.99.", encoding="utf-8")
    auditor = sa.StatAuditor(str(f))
    report = auditor.run()
    assert isinstance(report, sa.AuditReport)
    assert len(report.findings) > 0
    assert report.source == str(f)


def test_stat_auditor_min_severity():
    auditor = sa.StatAuditor("The effect was ns.", min_severity=sa.Severity.WARNING)
    report = auditor.run()
    for finding in report.findings:
        assert finding.severity >= sa.Severity.WARNING


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------

def test_audit_file_returns_list(tmp_path):
    f = tmp_path / "ms.txt"
    f.write_text("The effect was ns. t = 3.14.", encoding="utf-8")
    findings = sa.audit_file(f)
    assert isinstance(findings, list)
    assert len(findings) > 0


def test_audit_file_location_is_line(tmp_path):
    f = tmp_path / "ms.txt"
    f.write_text("Line one.\nThe effect was ns.\nLine three.", encoding="utf-8")
    findings = sa.audit_file(f)
    for finding in findings:
        assert finding.location.startswith("line "), finding.location


def test_audit_file_accurate_line_number(tmp_path):
    f = tmp_path / "ms.txt"
    f.write_text("Line one.\nThe effect was ns.\nLine three.", encoding="utf-8")
    findings = sa.audit_file(f)
    ns_findings = [x for x in findings if x.rule == "pvalue_ns"]
    assert ns_findings, "expected pvalue_ns finding"
    assert ns_findings[0].location == "line 2"


def test_audit_file_sorted_by_line(tmp_path):
    f = tmp_path / "ms.txt"
    f.write_text("ns.\nt = 2.1.\n", encoding="utf-8")
    findings = sa.audit_file(f)
    line_nums = [int(x.location.split()[-1]) for x in findings]
    assert line_nums == sorted(line_nums)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_main_list_rules():
    rc = sa.main(["--list-rules"])
    assert rc == 0


def test_main_stdin_empty(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = sa.main([])
    assert rc == 0


def test_main_stdin_with_findings(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("The effect was ns."))
    rc = sa.main([])
    assert rc in (0, 1)


def test_main_file_not_found(tmp_path):
    rc = sa.main([str(tmp_path / "nonexistent.txt")])
    assert rc == 2


def test_main_format_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("The effect was ns."))
    sa.main(["--format", "json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "findings" in data


def test_main_format_markdown(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("The effect was ns."))
    sa.main(["--format", "markdown"])
    captured = capsys.readouterr()
    assert "# Statistical Audit Report" in captured.out


def test_main_format_html(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("The effect was ns."))
    sa.main(["--format", "html"])
    captured = capsys.readouterr()
    assert "<!DOCTYPE html>" in captured.out


def test_main_output_file(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.stdin", io.StringIO("The effect was ns."))
    out = tmp_path / "report.txt"
    rc = sa.main(["--output", str(out)])
    assert rc in (0, 1)
    assert out.exists()
    assert len(out.read_text()) > 0


def test_main_severity_warning(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("The effect was significant."))
    sa.main(["--severity", "WARNING"])
    captured = capsys.readouterr()
    # nhst_only is INFO, so with WARNING filter the output should not contain it
    assert "nhst_only" not in captured.out


def test_main_input_file(tmp_path, capsys):
    f = tmp_path / "ms.txt"
    f.write_text("The effect was ns.", encoding="utf-8")
    rc = sa.main([str(f)])
    assert rc in (0, 1)
    captured = capsys.readouterr()
    assert "pvalue_ns" in captured.out
