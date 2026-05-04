"""Comprehensive test suite for stataudit (JOSS-level coverage)."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

import stataudit as sa
from stataudit import AuditReport, Finding, Severity, StatAuditor, audit_file, audit_text
from stataudit.auditor import RULES


# ── Severity ordering ─────────────────────────────────────────────────────────

class TestSeverityOrdering:
    def test_info_lt_warning(self):
        assert Severity.INFO < Severity.WARNING

    def test_warning_lt_error(self):
        assert Severity.WARNING < Severity.ERROR

    def test_info_lt_error(self):
        assert Severity.INFO < Severity.ERROR

    def test_error_gt_info(self):
        assert Severity.ERROR > Severity.INFO

    def test_le(self):
        assert Severity.INFO <= Severity.INFO
        assert Severity.INFO <= Severity.WARNING

    def test_ge(self):
        assert Severity.ERROR >= Severity.ERROR
        assert Severity.ERROR >= Severity.INFO

    def test_str_value(self):
        assert Severity.INFO.value == "INFO"
        assert Severity.WARNING.value == "WARNING"
        assert Severity.ERROR.value == "ERROR"


# ── Finding ───────────────────────────────────────────────────────────────────

class TestFinding:
    def _make(self, sev=Severity.INFO) -> Finding:
        return Finding(rule="test_rule", text="sample", location="line 1",
                       severity=sev, suggestion="Do better.")

    def test_to_dict_has_severity_string(self):
        d = self._make().to_dict()
        assert d["severity"] == "INFO"

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        assert set(d) == {"rule", "text", "location", "severity", "suggestion"}

    def test_str_contains_rule(self):
        f = self._make()
        assert "test_rule" in str(f)

    def test_str_contains_severity(self):
        f = self._make(Severity.WARNING)
        assert "WARNING" in str(f)


# ── Public API surface ────────────────────────────────────────────────────────

class TestPublicAPI:
    def test_module_has_audit_report(self):
        assert hasattr(sa, "AuditReport")

    def test_module_has_finding(self):
        assert hasattr(sa, "Finding")

    def test_module_has_audit_text(self):
        assert callable(sa.audit_text)

    def test_module_has_audit_file(self):
        assert callable(sa.audit_file)

    def test_module_has_stat_auditor(self):
        assert hasattr(sa, "StatAuditor")

    def test_module_has_severity(self):
        assert hasattr(sa, "Severity")

    def test_version_string(self):
        assert isinstance(sa.__version__, str)
        assert sa.__version__ >= "0.2.0"


# ── audit_text ────────────────────────────────────────────────────────────────

class TestAuditText:
    def test_empty_string_returns_empty_list(self):
        assert audit_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert audit_text("   \n  ") == []

    def test_clean_text_no_findings(self):
        findings = audit_text("The sky is blue and the grass is green.")
        assert findings == []

    def test_pvalue_ns_detected(self):
        findings = audit_text("The result was not significant (ns).")
        rules = {f.rule for f in findings}
        assert "pvalue_ns" in rules

    def test_t_test_df_missing(self):
        findings = audit_text("We found t = 2.34, p = .04.")
        rules = {f.rule for f in findings}
        assert "t_test_df_missing" in rules

    def test_anova_missing_df(self):
        findings = audit_text("The ANOVA was significant, F = 12.3.")
        rules = {f.rule for f in findings}
        assert "anova_missing_df" in rules

    def test_ci_level_missing(self):
        findings = audit_text("The 95% CI was [1.2, 3.4].")
        # 95% followed by CI — no flag expected
        ci_findings = [f for f in findings if f.rule == "ci_level_missing"]
        assert len(ci_findings) == 0

    def test_ci_missing_when_bare(self):
        findings = audit_text("The CI was [1.2, 3.4].")
        rules = {f.rule for f in findings}
        assert "ci_level_missing" in rules

    def test_small_sample_warning(self):
        findings = audit_text("Participants were recruited (N = 12).")
        rules = {f.rule for f in findings}
        assert "sample_size_small" in rules

    def test_large_sample_no_warning(self):
        findings = audit_text("The sample was (N = 120).")
        rules = {f.rule for f in findings}
        assert "sample_size_small" not in rules

    def test_over_precision(self):
        findings = audit_text("The mean was 3.123456.")
        rules = {f.rule for f in findings}
        assert "over_precision" in rules

    def test_one_tailed(self):
        findings = audit_text("A one-tailed test was used.")
        rules = {f.rule for f in findings}
        assert "one_tailed" in rules

    def test_nhst_language(self):
        findings = audit_text("The result was significant.")
        rules = {f.rule for f in findings}
        assert "nhst_only" in rules

    def test_outlier_flagged(self):
        findings = audit_text("Outlier removal improved fit.")
        rules = {f.rule for f in findings}
        assert "outlier_handling" in rules

    def test_missing_data_flagged(self):
        findings = audit_text("Missing data were handled by listwise deletion.")
        rules = {f.rule for f in findings}
        assert "missing_data" in rules

    def test_correlation_flagged(self):
        findings = audit_text("We found r = 0.45.")
        rules = {f.rule for f in findings}
        assert "correlation_missing_n" in rules

    def test_regression_r2_warning(self):
        findings = audit_text("We regressed outcome on predictors.")
        rules = {f.rule for f in findings}
        assert "regression_r2_missing" in rules

    def test_severity_filter_warning(self):
        findings = audit_text("The result was not significant (ns).", min_severity=Severity.WARNING)
        for f in findings:
            assert f.severity >= Severity.WARNING

    def test_severity_filter_error_no_info_warning(self):
        text = "We found t = 2.3 (ns), N = 5."
        all_findings = audit_text(text, Severity.INFO)
        err_findings = audit_text(text, Severity.ERROR)
        assert len(err_findings) <= len(all_findings)
        for f in err_findings:
            assert f.severity == Severity.ERROR

    def test_finding_has_snippet(self):
        findings = audit_text("The result was not significant (ns).")
        ns_finding = next(f for f in findings if f.rule == "pvalue_ns")
        assert len(ns_finding.text) > 0

    def test_finding_location_is_sentence(self):
        findings = audit_text("First sentence. The result was not significant (ns).")
        ns_finding = next(f for f in findings if f.rule == "pvalue_ns")
        assert "sentence" in ns_finding.location

    def test_multiple_findings_same_sentence(self):
        text = "t = 3.2, p = .04, N = 5."
        findings = audit_text(text)
        assert len(findings) >= 2

    def test_variance_unreported(self):
        findings = audit_text("The mean = 4.5 was computed.")
        rules = {f.rule for f in findings}
        assert "variance_unreported" in rules


# ── audit_file ────────────────────────────────────────────────────────────────

class TestAuditFile:
    def test_returns_list(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("We found t = 2.3, and the result was significant.", encoding="utf-8")
        findings = audit_file(f)
        assert isinstance(findings, list)

    def test_location_is_line(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("Line one.\nThe result was ns.\nLine three.", encoding="utf-8")
        findings = audit_file(f)
        ns_finding = next(f for f in findings if f.rule == "pvalue_ns")
        assert "line" in ns_finding.location

    def test_empty_file_no_findings(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert audit_file(f) == []

    def test_unicode_file(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("Résultats: t = 2.1 (ns), p = .09.", encoding="utf-8")
        findings = audit_file(f)
        assert any(fi.rule == "pvalue_ns" for fi in findings)


# ── StatAuditor ───────────────────────────────────────────────────────────────

class TestStatAuditor:
    def test_run_returns_audit_report(self):
        auditor = StatAuditor("The result was significant.")
        report = auditor.run()
        assert isinstance(report, AuditReport)

    def test_run_with_file(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("A one-tailed test was used.", encoding="utf-8")
        auditor = StatAuditor(str(f))
        report = auditor.run()
        assert any(fi.rule == "one_tailed" for fi in report.findings)

    def test_source_stored(self):
        auditor = StatAuditor("Some text.")
        assert auditor.source == "Some text."

    def test_min_severity_propagated(self):
        auditor = StatAuditor("t = 2.3 (ns).", min_severity=Severity.ERROR)
        report = auditor.run()
        for f in report.findings:
            assert f.severity == Severity.ERROR


# ── AuditReport ───────────────────────────────────────────────────────────────

class TestAuditReport:
    def _report(self, text="The result was ns, t = 3.2.") -> AuditReport:
        return AuditReport(source="test", findings=audit_text(text))

    # summary
    def test_summary_keys(self):
        s = self._report().summary
        assert "source" in s
        assert "total" in s
        assert "by_severity" in s

    def test_summary_total_matches_findings(self):
        r = self._report()
        assert r.summary["total"] == len(r.findings)

    def test_summary_counts_add_up(self):
        r = self._report()
        s = r.summary["by_severity"]
        assert s["INFO"] + s["WARNING"] + s["ERROR"] == r.summary["total"]

    def test_empty_report(self):
        r = AuditReport(source="x", findings=[])
        assert r.summary["total"] == 0

    # to_text
    def test_to_text_empty(self):
        r = AuditReport(source="x", findings=[])
        assert "No findings" in r.to_text()

    def test_to_text_contains_rule(self):
        r = self._report()
        assert any(f.rule in r.to_text() for f in r.findings)

    # to_markdown
    def test_to_markdown_contains_header(self):
        r = self._report()
        md = r.to_markdown()
        assert "# Statistical Audit Report" in md

    def test_to_markdown_empty(self):
        r = AuditReport(source="x", findings=[])
        assert "_No findings._" in r.to_markdown()

    def test_to_markdown_table(self):
        r = self._report()
        md = r.to_markdown()
        assert "|" in md

    # to_json
    def test_to_json_valid(self):
        r = self._report()
        data = json.loads(r.to_json())
        assert "summary" in data
        assert "findings" in data

    def test_to_json_severity_is_string(self):
        r = self._report()
        data = json.loads(r.to_json())
        for f in data["findings"]:
            assert isinstance(f["severity"], str)

    def test_to_json_empty(self):
        r = AuditReport(source="x", findings=[])
        data = json.loads(r.to_json())
        assert data["findings"] == []

    # to_html
    def test_to_html_is_string(self):
        r = self._report()
        assert isinstance(r.to_html(), str)

    def test_to_html_doctype(self):
        r = self._report()
        assert "<!DOCTYPE html>" in r.to_html()

    def test_to_html_no_xss(self):
        bad_text = '<script>alert(1)</script> The result was ns.'
        r = AuditReport(source="<evil>", findings=audit_text(bad_text))
        html = r.to_html()
        assert "<script>" not in html
        assert "&lt;evil&gt;" in html

    def test_to_html_empty(self):
        r = AuditReport(source="x", findings=[])
        assert "No findings" in r.to_html()

    # save
    def test_save_text(self, tmp_path):
        r = self._report()
        out = tmp_path / "report.txt"
        r.save(str(out), fmt="text")
        assert out.exists()
        assert out.read_text(encoding="utf-8")

    def test_save_json(self, tmp_path):
        r = self._report()
        out = tmp_path / "report.json"
        r.save(str(out), fmt="json")
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "findings" in data

    def test_save_html(self, tmp_path):
        r = self._report()
        out = tmp_path / "report.html"
        r.save_html(str(out))
        assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")

    def test_save_markdown(self, tmp_path):
        r = self._report()
        out = tmp_path / "report.md"
        r.save(str(out), fmt="markdown")
        assert "# Statistical Audit Report" in out.read_text(encoding="utf-8")

    def test_save_invalid_format_raises(self, tmp_path):
        r = self._report()
        with pytest.raises(ValueError):
            r.save(str(tmp_path / "x"), fmt="pdf")


# ── Rules catalogue ───────────────────────────────────────────────────────────

class TestRules:
    def test_rules_is_list(self):
        assert isinstance(RULES, list)

    def test_each_rule_has_four_elements(self):
        for rule in RULES:
            assert len(rule) == 4, f"Rule {rule[0]} has wrong length"

    def test_rule_names_unique(self):
        names = [r[0] for r in RULES]
        assert len(names) == len(set(names)), "Duplicate rule names found"

    def test_severities_are_severity_enum(self):
        for _, _, sev, _ in RULES:
            assert isinstance(sev, Severity)

    def test_suggestions_non_empty(self):
        for name, _, _, suggestion in RULES:
            assert suggestion.strip(), f"Rule {name} has empty suggestion"

    def test_at_least_ten_rules(self):
        assert len(RULES) >= 10


# ── CLI ───────────────────────────────────────────────────────────────────────

class TestCLI:
    def test_list_rules_exit_zero(self, capsys):
        from stataudit.cli import main
        rc = main(["--list-rules"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_file_not_found_exit_one(self):
        from stataudit.cli import main
        rc = main(["nonexistent_file_xyz.txt"])
        assert rc == 1

    def test_audit_file_text_output(self, tmp_path, capsys):
        from stataudit.cli import main
        f = tmp_path / "doc.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(f)])
        out = capsys.readouterr().out
        assert "pvalue_ns" in out
        assert rc == 0

    def test_audit_file_json_output(self, tmp_path, capsys):
        from stataudit.cli import main
        f = tmp_path / "doc.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(f), "--format", "json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "findings" in data

    def test_audit_file_markdown_output(self, tmp_path, capsys):
        from stataudit.cli import main
        f = tmp_path / "doc.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(f), "--format", "markdown"])
        out = capsys.readouterr().out
        assert "# Statistical Audit Report" in out

    def test_audit_file_save_output(self, tmp_path, capsys):
        from stataudit.cli import main
        f = tmp_path / "doc.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        out_path = tmp_path / "report.txt"
        main([str(f), "--output", str(out_path)])
        assert out_path.exists()

    def test_severity_filter_warning(self, tmp_path, capsys):
        from stataudit.cli import main
        f = tmp_path / "doc.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(f), "--severity", "WARNING"])
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_clean_text_reports_no_findings(self, tmp_path, capsys):
        from stataudit.cli import main
        f = tmp_path / "clean.txt"
        f.write_text("The sky is blue.", encoding="utf-8")
        rc = main([str(f)])
        out = capsys.readouterr().out
        assert "No findings" in out
        assert rc == 0
