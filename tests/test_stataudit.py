"""
Tests for the stataudit package.

Run with:  pytest tests/ -v
"""
import json
import sys
import pathlib
import tempfile

# Ensure the package in src/ is importable when running without installation.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import stataudit as sa
from stataudit import (
    AuditReport,
    Finding,
    Severity,
    StatAuditor,
    audit_file,
    audit_text,
    RULES,
)


# ---------------------------------------------------------------------------
# Basic import / API surface
# ---------------------------------------------------------------------------

def test_import():
    assert hasattr(sa, "AuditReport")


def test_finding():
    assert hasattr(sa, "Finding")


def test_audit_text():
    assert callable(sa.audit_text)


def test_audit_text_empty():
    r = audit_text("")
    assert r == []


def test_rules_non_empty():
    assert len(RULES) >= 15


def test_severity_ordering():
    assert Severity.INFO < Severity.WARNING < Severity.ERROR
    assert Severity.ERROR > Severity.WARNING > Severity.INFO
    assert Severity.WARNING <= Severity.WARNING
    assert Severity.INFO <= Severity.ERROR


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

def test_finding_str():
    f = Finding(
        rule="test_rule",
        text="some text",
        location="sentence 1",
        severity=Severity.WARNING,
        suggestion="Do better.",
    )
    s = str(f)
    assert "WARNING" in s
    assert "test_rule" in s
    assert "Do better." in s


def test_finding_to_dict():
    f = Finding(
        rule="r", text="t", location="l", severity=Severity.ERROR, suggestion="s"
    )
    d = f.to_dict()
    assert d["severity"] == "ERROR"
    assert d["rule"] == "r"


# ---------------------------------------------------------------------------
# Rule detection
# ---------------------------------------------------------------------------

def test_pvalue_ns_detected():
    findings = audit_text("Results were ns for the control group.")
    rules = [f.rule for f in findings]
    assert "pvalue_ns" in rules


def test_pvalue_over_precision():
    findings = audit_text("We found p = 0.000123 in the analysis.")
    rules = [f.rule for f in findings]
    assert "pvalue_over_precision" in rules


def test_pvalue_impossible():
    findings = audit_text("The result was p = 1.5 which is odd.")
    rules = [f.rule for f in findings]
    assert "pvalue_impossible" in rules


def test_t_test_df_missing():
    findings = audit_text("The t-test showed t = 3.21.")
    rules = [f.rule for f in findings]
    assert "t_test_df_missing" in rules


def test_t_test_with_df_not_flagged():
    findings = audit_text("The analysis revealed t(28) = 3.21.")
    rules = [f.rule for f in findings]
    assert "t_test_df_missing" not in rules


def test_anova_missing_df():
    findings = audit_text("We found F = 12.3 in the ANOVA.")
    rules = [f.rule for f in findings]
    assert "anova_missing_df" in rules


def test_chi_square_df_missing():
    findings = audit_text("The chi-square = 5.6 was significant.")
    rules = [f.rule for f in findings]
    assert "chi_square_df_missing" in rules


def test_sample_size_small():
    findings = audit_text("A total of N = 12 participants were recruited.")
    rules = [f.rule for f in findings]
    assert "sample_size_small" in rules


def test_sample_size_large_not_flagged():
    findings = audit_text("N = 120 participants completed the study.")
    rules = [f.rule for f in findings]
    assert "sample_size_small" not in rules


def test_ci_level_missing():
    findings = audit_text("The CI was [0.12, 0.45].")
    rules = [f.rule for f in findings]
    assert "ci_level_missing" in rules


def test_ci_with_level_not_flagged():
    findings = audit_text("The 95% CI was [0.12, 0.45].")
    rules = [f.rule for f in findings]
    assert "ci_level_missing" not in rules


def test_over_precision():
    findings = audit_text("The mean was 3.141593652.")
    rules = [f.rule for f in findings]
    assert "over_precision" in rules


def test_one_tailed():
    findings = audit_text("A one-tailed test was applied.")
    rules = [f.rule for f in findings]
    assert "one_tailed" in rules


def test_nhst_only():
    findings = audit_text("The difference was significant at α = .05.")
    rules = [f.rule for f in findings]
    assert "nhst_only" in rules


def test_effect_size_missing():
    findings = audit_text("The result was statistically significant at α = .05.")
    rules = [f.rule for f in findings]
    assert "effect_size_missing" in rules


def test_outlier_handling():
    findings = audit_text("Three outlier cases were removed before analysis.")
    rules = [f.rule for f in findings]
    assert "outlier_handling" in rules


def test_missing_data():
    findings = audit_text("Missing data were handled by listwise deletion.")
    rules = [f.rule for f in findings]
    assert "missing_data" in rules


def test_regression_r2_missing():
    findings = audit_text("We regressed income on education level.")
    rules = [f.rule for f in findings]
    assert "regression_r2_missing" in rules


def test_correlation_missing_n():
    findings = audit_text("We observed r = 0.45 between the variables.")
    rules = [f.rule for f in findings]
    assert "correlation_missing_n" in rules


def test_sem_vs_sd():
    findings = audit_text("Error bars represent the SEM across trials.")
    rules = [f.rule for f in findings]
    assert "sem_vs_sd" in rules


def test_post_hoc():
    findings = audit_text("Post-hoc comparisons revealed group differences.")
    rules = [f.rule for f in findings]
    assert "post_hoc_test" in rules


# ---------------------------------------------------------------------------
# Severity filtering
# ---------------------------------------------------------------------------

def test_min_severity_warning_excludes_info():
    findings = audit_text(
        "Error bars represent the SEM.",  # triggers sem_vs_sd (INFO)
        min_severity=Severity.WARNING,
    )
    for f in findings:
        assert f.severity >= Severity.WARNING


def test_min_severity_error_only():
    findings = audit_text(
        "The p-value was p = 2.5.",  # pvalue_impossible = ERROR
        min_severity=Severity.ERROR,
    )
    for f in findings:
        assert f.severity == Severity.ERROR


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------

def test_audit_report_summary():
    findings = audit_text("Results were ns. The confidence interval was [0.1, 0.9].")
    report = AuditReport(source="test", findings=findings)
    s = report.summary
    assert s["total"] == len(findings)
    assert "by_severity" in s
    assert set(s["by_severity"].keys()) == {"INFO", "WARNING", "ERROR"}


def test_audit_report_to_text_no_findings():
    report = AuditReport(source="clean.txt", findings=[])
    assert "No findings" in report.to_text()


def test_audit_report_to_text():
    findings = audit_text("Results were ns.")
    report = AuditReport(source="paper.txt", findings=findings)
    txt = report.to_text()
    assert "pvalue_ns" in txt


def test_audit_report_to_markdown():
    findings = audit_text("Results were ns.")
    report = AuditReport(source="paper.txt", findings=findings)
    md = report.to_markdown()
    assert "# Statistical Audit Report" in md
    assert "pvalue_ns" in md


def test_audit_report_to_json():
    findings = audit_text("Results were ns.")
    report = AuditReport(source="test", findings=findings)
    data = json.loads(report.to_json())
    assert "summary" in data
    assert "findings" in data
    assert data["summary"]["total"] == len(findings)
    for f in data["findings"]:
        assert f["severity"] in ("INFO", "WARNING", "ERROR")


def test_audit_report_to_html():
    findings = audit_text("Results were ns.")
    report = AuditReport(source="test", findings=findings)
    html = report.to_html()
    assert "<!DOCTYPE html>" in html
    assert "pvalue_ns" in html


def test_audit_report_to_html_no_findings():
    report = AuditReport(source="clean.txt", findings=[])
    html = report.to_html()
    assert "No findings" in html


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------

def test_audit_file_basic():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("Results were ns.  The t = 2.5 was significant.\n")
        fh_name = fh.name
    findings = audit_file(pathlib.Path(fh_name))
    rules = [f.rule for f in findings]
    assert "pvalue_ns" in rules
    assert "t_test_df_missing" in rules
    # Locations should be line-based
    for f in findings:
        assert f.location.startswith("line")


def test_audit_file_missing_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        audit_file(pathlib.Path("/nonexistent/path/manuscript.txt"))


# ---------------------------------------------------------------------------
# StatAuditor
# ---------------------------------------------------------------------------

def test_stat_auditor_text():
    auditor = StatAuditor("Results were ns.  The CI was [0.1, 0.9].")
    report = auditor.run()
    assert isinstance(report, AuditReport)
    assert len(report.findings) > 0


def test_stat_auditor_file():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("We found t = 3.4 and p = .0000012.\n")
        fh_name = fh.name
    auditor = StatAuditor(fh_name)
    report = auditor.run()
    assert isinstance(report, AuditReport)
    assert len(report.findings) > 0


def test_stat_auditor_min_severity():
    auditor = StatAuditor(
        "Results were ns. The SEM is shown.",
        min_severity=Severity.WARNING,
    )
    report = auditor.run()
    for f in report.findings:
        assert f.severity >= Severity.WARNING


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_list_rules(capsys):
    from stataudit._cli import main
    rc = main(["list-rules"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "pvalue_ns" in captured.out


def test_cli_check_file(capsys, tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("Results were ns.\n", encoding="utf-8")
    from stataudit._cli import main
    rc = main(["check", str(manuscript)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "pvalue_ns" in captured.out


def test_cli_check_file_json(capsys, tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("Results were ns.\n", encoding="utf-8")
    from stataudit._cli import main
    main(["check", str(manuscript), "--format", "json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "findings" in data


def test_cli_check_file_html(capsys, tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("Results were ns.\n", encoding="utf-8")
    from stataudit._cli import main
    main(["check", str(manuscript), "--format", "html"])
    captured = capsys.readouterr()
    assert "<!DOCTYPE html>" in captured.out


def test_cli_missing_file(capsys):
    from stataudit._cli import main
    rc = main(["check", "/no/such/file.txt"])
    assert rc == 1


def test_cli_error_exit_code(capsys, tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("The p-value was p = 2.5.\n", encoding="utf-8")
    from stataudit._cli import main
    rc = main(["check", str(manuscript)])
    assert rc == 1  # ERROR finding → exit 1


def test_cli_output_file(tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("Results were ns.\n", encoding="utf-8")
    out_file = tmp_path / "report.md"
    from stataudit._cli import main
    main(["check", str(manuscript), "--format", "markdown", "-o", str(out_file)])
    content = out_file.read_text(encoding="utf-8")
    assert "# Statistical Audit Report" in content
