"""Tests for the stataudit package."""
import json
import sys
from pathlib import Path

import pytest

# Ensure the src layout is importable without a prior pip install.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import stataudit as sa
from stataudit.core import (
    AuditReport,
    Finding,
    Severity,
    _RULES,
    _split_sentences,
    audit_file,
    audit_text,
)
from stataudit.cli import main as cli_main


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------


def test_severity_order_lt():
    assert Severity.INFO < Severity.WARNING < Severity.ERROR


def test_severity_order_gt():
    assert Severity.ERROR > Severity.WARNING > Severity.INFO


def test_severity_order_le_ge_equal():
    assert Severity.WARNING <= Severity.WARNING
    assert Severity.WARNING >= Severity.WARNING


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


def test_package_exports_audit_report():
    assert hasattr(sa, "AuditReport")


def test_package_exports_finding():
    assert hasattr(sa, "Finding")


def test_package_exports_audit_text():
    assert callable(sa.audit_text)


def test_package_exports_audit_file():
    assert callable(sa.audit_file)


def test_package_exports_version():
    assert hasattr(sa, "__version__")
    assert isinstance(sa.__version__, str)


# ---------------------------------------------------------------------------
# audit_text — basics
# ---------------------------------------------------------------------------


def test_audit_text_empty_string():
    assert audit_text("") == []


def test_audit_text_whitespace_only():
    assert audit_text("   \n  ") == []


def test_audit_text_returns_findings():
    result = audit_text("The result was significant.")
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(f, Finding) for f in result)


def test_finding_fields_populated():
    f = audit_text("The result was significant.")[0]
    assert isinstance(f.rule, str) and f.rule
    assert isinstance(f.text, str) and f.text
    assert isinstance(f.location, str) and f.location
    assert isinstance(f.severity, Severity)
    assert isinstance(f.suggestion, str) and f.suggestion


def test_finding_to_dict_serialisable():
    f = audit_text("The result was significant.")[0]
    d = f.to_dict()
    assert isinstance(d["severity"], str)  # enum must be serialised
    json.dumps(d)  # must not raise


def test_finding_str_contains_severity():
    f = audit_text("The result was significant.")[0]
    assert f.severity.value in str(f)


# ---------------------------------------------------------------------------
# audit_text — severity filter
# ---------------------------------------------------------------------------


def test_severity_filter_info_ge_warning_ge_error():
    text = "The result was significant (t = 3.2, ns)."
    all_f = audit_text(text, Severity.INFO)
    warn_f = audit_text(text, Severity.WARNING)
    err_f = audit_text(text, Severity.ERROR)
    assert len(all_f) >= len(warn_f) >= len(err_f)


def test_severity_filter_warning_excludes_info():
    text = "The result was significant."
    info_f = audit_text(text, Severity.INFO)
    warn_f = audit_text(text, Severity.WARNING)
    # nhst_only is INFO; filtering at WARNING should reduce the count
    assert len(info_f) > len(warn_f)


# ---------------------------------------------------------------------------
# Rule-level detection tests
# ---------------------------------------------------------------------------


def test_rule_pvalue_exact():
    hits = [f for f in audit_text("p = .034") if f.rule == "pvalue_exact"]
    assert hits


def test_rule_pvalue_ns():
    hits = [f for f in audit_text("The difference was (ns).") if f.rule == "pvalue_ns"]
    assert hits


def test_rule_pvalue_over_precision_dot():
    hits = [f for f in audit_text("p = .000012") if f.rule == "pvalue_over_precision"]
    assert hits


def test_rule_pvalue_over_precision_zero_dot():
    hits = [f for f in audit_text("p = 0.000012") if f.rule == "pvalue_over_precision"]
    assert hits


def test_rule_ci_level_missing():
    hits = [f for f in audit_text("The CI was [1.2, 3.4].") if f.rule == "ci_level_missing"]
    assert hits


def test_rule_t_test_df_missing():
    hits = [f for f in audit_text("We found t = 3.21.") if f.rule == "t_test_df_missing"]
    assert hits


def test_rule_t_test_df_present_no_hit():
    hits = [f for f in audit_text("We found t(48) = 3.21.") if f.rule == "t_test_df_missing"]
    assert not hits


def test_rule_anova_missing_df():
    hits = [f for f in audit_text("F = 4.50 was significant.") if f.rule == "anova_missing_df"]
    assert hits


def test_rule_sample_size_small():
    hits = [f for f in audit_text("We recruited N = 12 participants.") if f.rule == "sample_size_small"]
    assert hits


def test_rule_sample_size_adequate_no_hit():
    hits = [f for f in audit_text("We recruited N = 120 participants.") if f.rule == "sample_size_small"]
    assert not hits


def test_rule_over_precision():
    hits = [f for f in audit_text("The mean was 0.123456.") if f.rule == "over_precision"]
    assert hits


def test_rule_one_tailed():
    hits = [f for f in audit_text("We used a one-tailed test.") if f.rule == "one_tailed"]
    assert hits


def test_rule_nhst_only():
    hits = [f for f in audit_text("The result was significant.") if f.rule == "nhst_only"]
    assert hits


def test_rule_outlier_handling():
    hits = [f for f in audit_text("We removed outliers before analysis.") if f.rule == "outlier_handling"]
    assert hits


def test_rule_missing_data():
    hits = [f for f in audit_text("Missing data were handled via imputation.") if f.rule == "missing_data"]
    assert hits


def test_rule_regression_r2_missing():
    hits = [f for f in audit_text("A regression was performed.") if f.rule == "regression_r2_missing"]
    assert hits


def test_rule_multiple_comparisons():
    hits = [f for f in audit_text("We applied Bonferroni correction.") if f.rule == "multiple_comparisons"]
    assert hits


def test_rule_correlation_missing_n():
    hits = [f for f in audit_text("The correlation was r = 0.45.") if f.rule == "correlation_missing_n"]
    assert hits


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------


def test_report_summary_empty():
    report = AuditReport(source="test", findings=[])
    s = report.summary
    assert s["total"] == 0
    assert s["by_severity"]["ERROR"] == 0
    assert s["source"] == "test"


def test_report_summary_counts():
    findings = audit_text("The result was significant (t = 3.2).")
    report = AuditReport(source="test", findings=findings)
    s = report.summary
    assert s["total"] == len(findings)
    total = sum(s["by_severity"].values())
    assert total == s["total"]


def test_report_to_text_no_findings():
    report = AuditReport(source="test", findings=[])
    assert "No findings" in report.to_text()


def test_report_to_text_with_findings():
    report = AuditReport(source="test", findings=audit_text("significant t = 3.2"))
    out = report.to_text()
    assert "Audit report for: test" in out


def test_report_to_markdown_structure():
    report = AuditReport(source="test", findings=audit_text("significant t = 3.2"))
    md = report.to_markdown()
    assert "# Statistical Audit Report" in md
    assert "**Source:** test" in md


def test_report_to_json_parseable():
    report = AuditReport(source="test", findings=audit_text("significant t = 3.2"))
    data = json.loads(report.to_json())
    assert "summary" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)


def test_report_to_json_severity_is_string():
    report = AuditReport(source="test", findings=audit_text("significant"))
    data = json.loads(report.to_json())
    for item in data["findings"]:
        assert isinstance(item["severity"], str)


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------


def test_audit_file_returns_findings(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("The result was significant (t = 3.21, ns).", encoding="utf-8")
    findings = audit_file(f)
    assert isinstance(findings, list)
    assert len(findings) > 0


def test_audit_file_location_is_line(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("The result was significant.\n", encoding="utf-8")
    findings = audit_file(f)
    assert any("line" in fi.location for fi in findings)


def test_audit_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        audit_file(Path("/nonexistent/does_not_exist.txt"))


def test_audit_file_accepts_str_path(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("significant", encoding="utf-8")
    findings = audit_file(str(f))
    assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_list_rules(capsys):
    rc = cli_main(["--list-rules"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "pvalue_exact" in out
    assert len(out.splitlines()) == len(_RULES)


def test_cli_file_text_format(tmp_path, capsys):
    f = tmp_path / "sample.txt"
    f.write_text("The result was significant.", encoding="utf-8")
    rc = cli_main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "nhst_only" in out


def test_cli_file_not_found_exits_1(capsys):
    rc = cli_main(["/nonexistent/file.txt"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Error" in err


def test_cli_format_json(tmp_path, capsys):
    f = tmp_path / "sample.txt"
    f.write_text("The result was significant.", encoding="utf-8")
    rc = cli_main([str(f), "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert "findings" in data


def test_cli_format_markdown(tmp_path, capsys):
    f = tmp_path / "sample.txt"
    f.write_text("The result was significant.", encoding="utf-8")
    cli_main([str(f), "--format", "markdown"])
    out = capsys.readouterr().out
    assert "# Statistical Audit Report" in out


def test_cli_severity_warning_fewer_findings(tmp_path, capsys):
    f = tmp_path / "sample.txt"
    f.write_text("The result was significant.", encoding="utf-8")
    cli_main([str(f), "--severity", "INFO"])
    out_info = capsys.readouterr().out
    cli_main([str(f), "--severity", "ERROR"])
    out_error = capsys.readouterr().out
    assert len(out_info) >= len(out_error)


def test_cli_output_file(tmp_path, capsys):
    src = tmp_path / "sample.txt"
    src.write_text("The result was significant.", encoding="utf-8")
    out_file = tmp_path / "report.txt"
    rc = cli_main([str(src), "--output", str(out_file)])
    assert rc == 0
    assert out_file.exists()
    assert "nhst_only" in out_file.read_text()
