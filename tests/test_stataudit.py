import json
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import stataudit as sa


# ── Public API presence ───────────────────────────────────────────────────────

def test_import():
    assert hasattr(sa, "AuditReport")

def test_finding_class():
    assert hasattr(sa, "Finding")

def test_audit_text_callable():
    assert callable(sa.audit_text)

def test_stat_auditor_class():
    assert hasattr(sa, "StatAuditor")

def test_severity_ordering():
    assert sa.Severity.INFO < sa.Severity.WARNING < sa.Severity.ERROR


# ── audit_text basic behaviour ────────────────────────────────────────────────

def test_audit_text_empty():
    assert sa.audit_text("") == []

def test_audit_text_returns_list():
    result = sa.audit_text("The result was significant (p = .03).")
    assert isinstance(result, list)

def test_audit_text_pvalue_info():
    findings = sa.audit_text("We found p = .045.")
    rules = [f.rule for f in findings]
    assert "pvalue_exact" in rules

def test_audit_text_pvalue_ns_warning():
    findings = sa.audit_text("The difference was ns.")
    assert any(f.rule == "pvalue_ns" and f.severity == sa.Severity.WARNING for f in findings)

def test_audit_text_ci_level_missing():
    findings = sa.audit_text("The 95% CI was reported.")
    # "95% CI" has a digit after CI so should NOT fire
    rules = [f.rule for f in findings]
    assert "ci_level_missing" not in rules

def test_audit_text_ci_level_missing_fires():
    findings = sa.audit_text("The CI was [1.2, 3.4].")
    assert any(f.rule == "ci_level_missing" for f in findings)

def test_audit_text_t_test_df_missing():
    findings = sa.audit_text("The t-test gave t = 3.14.")
    assert any(f.rule == "t_test_df_missing" for f in findings)

def test_audit_text_t_test_df_present_no_finding():
    # t(29) = 3.14 should NOT trigger the rule
    findings = sa.audit_text("We found t(29) = 3.14.")
    assert not any(f.rule == "t_test_df_missing" for f in findings)

def test_audit_text_sample_size_small():
    findings = sa.audit_text("The study included N = 15 participants.")
    assert any(f.rule == "sample_size_small" for f in findings)

def test_audit_text_nhst_only():
    findings = sa.audit_text("The effect was statistically significant.")
    assert any(f.rule == "nhst_only" for f in findings)

def test_audit_text_correlation():
    findings = sa.audit_text("We observed r = .72 between the variables.")
    assert any(f.rule == "correlation_missing_n" for f in findings)

def test_audit_text_min_severity_filter():
    # Only WARNING and above — INFO findings should be absent
    findings = sa.audit_text("The result was significant.", min_severity=sa.Severity.WARNING)
    for f in findings:
        assert f.severity >= sa.Severity.WARNING


# ── ERROR-level rules ─────────────────────────────────────────────────────────

def test_pvalue_impossible_detected():
    findings = sa.audit_text("We report p = 1.5 for the main effect.")
    assert any(f.rule == "pvalue_impossible" and f.severity == sa.Severity.ERROR for f in findings)

def test_pvalue_negative_detected():
    findings = sa.audit_text("Interestingly, p = -0.03 was observed.")
    assert any(f.rule == "pvalue_negative" and f.severity == sa.Severity.ERROR for f in findings)

def test_valid_pvalue_not_flagged_as_impossible():
    findings = sa.audit_text("The result was p = 0.04.")
    assert not any(f.rule == "pvalue_impossible" for f in findings)


# ── audit_file ────────────────────────────────────────────────────────────────

def test_audit_file_line_location():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("Line one is fine.\nThe difference was ns.\nLine three.\n")
        tmp = pathlib.Path(fh.name)
    try:
        findings = sa.audit_file(tmp)
        ns_findings = [f for f in findings if f.rule == "pvalue_ns"]
        assert ns_findings, "expected pvalue_ns finding"
        assert ns_findings[0].location == "line 2"
    finally:
        tmp.unlink()


# ── AuditReport output formats ────────────────────────────────────────────────

def _make_report():
    findings = sa.audit_text("The result was ns and t = 3.14.")
    return sa.AuditReport(source="test", findings=findings)

def test_report_summary_keys():
    r = _make_report()
    s = r.summary
    assert "total" in s and "by_severity" in s

def test_report_to_text():
    r = _make_report()
    out = r.to_text()
    assert "Audit report for: test" in out

def test_report_to_text_no_findings():
    r = sa.AuditReport(source="clean", findings=[])
    assert "No findings" in r.to_text()

def test_report_to_markdown():
    r = _make_report()
    md = r.to_markdown()
    assert "# Statistical Audit Report" in md
    assert "| Severity | Count |" in md

def test_report_to_json():
    r = _make_report()
    data = json.loads(r.to_json())
    assert "summary" in data and "findings" in data
    assert isinstance(data["findings"], list)

def test_report_json_severity_is_string():
    r = _make_report()
    data = json.loads(r.to_json())
    for item in data["findings"]:
        assert item["severity"] in ("INFO", "WARNING", "ERROR")


# ── StatAuditor class ─────────────────────────────────────────────────────────

def test_stat_auditor_text_mode():
    auditor = sa.StatAuditor("The result was ns.")
    report = auditor.run()
    assert isinstance(report, sa.AuditReport)
    assert len(report.findings) > 0

def test_stat_auditor_file_mode():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("The difference was ns.\n")
        tmp = pathlib.Path(fh.name)
    try:
        auditor = sa.StatAuditor(str(tmp))
        report = auditor.run()
        assert any(f.rule == "pvalue_ns" for f in report.findings)
    finally:
        tmp.unlink()


# ── main() CLI return codes ───────────────────────────────────────────────────

def test_main_list_rules():
    rc = sa.main(["--list-rules"])
    assert rc == 0

def test_main_returns_int():
    rc = sa.main(["--list-rules"])
    assert isinstance(rc, int)
