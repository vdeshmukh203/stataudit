"""
Test suite for stataudit.

Tests cover:
  - Public API surface (imports, attributes)
  - Severity ordering
  - Individual detection rules (true-positive and true-negative cases)
  - audit_text / audit_file functions
  - AuditReport serialization (text, markdown, JSON, HTML)
  - StatAuditor high-level interface
  - Severity filtering
  - Finding dataclass
"""
import json
import textwrap

import pytest

import stataudit as sa
from stataudit import (
    AuditReport,
    Finding,
    Severity,
    StatAuditor,
    audit_file,
    audit_text,
)


# ── package surface ────────────────────────────────────────────────────────────

class TestPackageSurface:
    def test_audit_report_exported(self):
        assert hasattr(sa, "AuditReport")

    def test_finding_exported(self):
        assert hasattr(sa, "Finding")

    def test_audit_text_callable(self):
        assert callable(sa.audit_text)

    def test_audit_file_callable(self):
        assert callable(sa.audit_file)

    def test_stat_auditor_exported(self):
        assert hasattr(sa, "StatAuditor")

    def test_severity_exported(self):
        assert hasattr(sa, "Severity")

    def test_version_string(self):
        assert isinstance(sa.__version__, str)
        assert "." in sa.__version__


# ── Severity enum ──────────────────────────────────────────────────────────────

class TestSeverity:
    def test_ordering_info_lt_warning(self):
        assert Severity.INFO < Severity.WARNING

    def test_ordering_warning_lt_error(self):
        assert Severity.WARNING < Severity.ERROR

    def test_ordering_info_lt_error(self):
        assert Severity.INFO < Severity.ERROR

    def test_ordering_equal(self):
        assert Severity.INFO <= Severity.INFO
        assert Severity.WARNING >= Severity.WARNING

    def test_ordering_gt(self):
        assert Severity.ERROR > Severity.WARNING
        assert Severity.WARNING > Severity.INFO

    def test_from_string(self):
        assert Severity("INFO") is Severity.INFO
        assert Severity("WARNING") is Severity.WARNING
        assert Severity("ERROR") is Severity.ERROR

    def test_value_is_string(self):
        assert Severity.INFO.value == "INFO"


# ── Finding dataclass ──────────────────────────────────────────────────────────

class TestFinding:
    def _make(self, **kw):
        defaults = dict(
            rule="test_rule",
            text="some text",
            location="sentence 1",
            severity=Severity.WARNING,
            suggestion="Fix it.",
        )
        defaults.update(kw)
        return Finding(**defaults)

    def test_message_alias(self):
        f = self._make(suggestion="Do this.")
        assert f.message == "Do this."

    def test_to_dict_severity_is_string(self):
        f = self._make(severity=Severity.ERROR)
        d = f.to_dict()
        assert d["severity"] == "ERROR"
        assert isinstance(d["severity"], str)

    def test_to_dict_all_fields(self):
        f = self._make()
        d = f.to_dict()
        assert set(d) == {"rule", "text", "location", "severity", "suggestion"}

    def test_str_contains_severity(self):
        f = self._make(severity=Severity.WARNING)
        assert "WARNING" in str(f)

    def test_str_contains_rule(self):
        f = self._make(rule="my_rule")
        assert "my_rule" in str(f)


# ── audit_text edge cases ─────────────────────────────────────────────────────

class TestAuditTextEdgeCases:
    def test_empty_string_returns_empty(self):
        assert audit_text("") == []

    def test_whitespace_only_returns_empty(self):
        assert audit_text("   \n  ") == []

    def test_clean_text_no_findings(self):
        text = "The sky is blue."
        findings = audit_text(text)
        assert isinstance(findings, list)

    def test_returns_list_of_findings(self):
        findings = audit_text("The result was ns.")
        assert all(isinstance(f, Finding) for f in findings)


# ── individual rule tests ─────────────────────────────────────────────────────

class TestRulePvalueNs:
    def test_ns_triggers_warning(self):
        findings = audit_text("The result was ns.")
        rules = [f.rule for f in findings]
        assert "pvalue_ns" in rules

    def test_ns_in_parens_triggers(self):
        findings = audit_text("Difference (ns) was noted.")
        rules = [f.rule for f in findings]
        assert "pvalue_ns" in rules

    def test_severity_is_warning(self):
        findings = audit_text("The result was ns.")
        ns_f = [f for f in findings if f.rule == "pvalue_ns"]
        assert all(f.severity == Severity.WARNING for f in ns_f)

    def test_suggestion_present(self):
        findings = audit_text("ns")
        ns_f = [f for f in findings if f.rule == "pvalue_ns"]
        assert all(f.suggestion for f in ns_f)


class TestRulePvalueOverPrecision:
    def test_four_zeros_triggers(self):
        findings = audit_text("We found p = .00001.")
        rules = [f.rule for f in findings]
        assert "pvalue_over_precision" in rules

    def test_three_zeros_triggers(self):
        findings = audit_text("p = .0001 was reported.")
        rules = [f.rule for f in findings]
        assert "pvalue_over_precision" in rules

    def test_leading_zero_form(self):
        findings = audit_text("p = 0.0001 was observed.")
        rules = [f.rule for f in findings]
        assert "pvalue_over_precision" in rules

    def test_two_zeros_does_not_trigger(self):
        findings = audit_text("p = .012 was observed.")
        rules = [f.rule for f in findings]
        assert "pvalue_over_precision" not in rules


class TestRuleTTestDfMissing:
    def test_t_without_df_triggers(self):
        findings = audit_text("We found t = 3.45.")
        rules = [f.rule for f in findings]
        assert "t_test_df_missing" in rules

    def test_t_with_df_ok(self):
        findings = audit_text("We found t(45) = 3.45.")
        rules = [f.rule for f in findings]
        assert "t_test_df_missing" not in rules


class TestRuleAnovaMissingDf:
    def test_f_without_df_triggers(self):
        findings = audit_text("We found F = 12.3.")
        rules = [f.rule for f in findings]
        assert "anova_missing_df" in rules

    def test_f_with_df_ok(self):
        findings = audit_text("We found F(2, 45) = 12.3.")
        rules = [f.rule for f in findings]
        assert "anova_missing_df" not in rules


class TestRuleCiLevelMissing:
    def test_bare_ci_triggers(self):
        findings = audit_text("The CI was [1.2, 3.4].")
        rules = [f.rule for f in findings]
        assert "ci_level_missing" in rules

    def test_bare_confidence_interval_triggers(self):
        findings = audit_text("A confidence interval was computed.")
        rules = [f.rule for f in findings]
        assert "ci_level_missing" in rules


class TestRuleSampleSizeSmall:
    def test_small_n_triggers(self):
        findings = audit_text("We recruited N = 15 participants.")
        rules = [f.rule for f in findings]
        assert "sample_size_small" in rules

    def test_n_equals_29_triggers(self):
        findings = audit_text("N = 29.")
        rules = [f.rule for f in findings]
        assert "sample_size_small" in rules

    def test_n_equals_30_ok(self):
        findings = audit_text("N = 30.")
        rules = [f.rule for f in findings]
        assert "sample_size_small" not in rules

    def test_large_n_ok(self):
        findings = audit_text("We recruited N = 200 participants.")
        rules = [f.rule for f in findings]
        assert "sample_size_small" not in rules


class TestRuleOverPrecision:
    def test_five_decimals_triggers(self):
        findings = audit_text("The value was 3.14159265.")
        rules = [f.rule for f in findings]
        assert "over_precision" in rules

    def test_three_decimals_ok(self):
        findings = audit_text("The value was 3.141.")
        rules = [f.rule for f in findings]
        assert "over_precision" not in rules


class TestRuleOneTailed:
    def test_one_tailed_triggers(self):
        findings = audit_text("A one-tailed test was used.")
        rules = [f.rule for f in findings]
        assert "one_tailed" in rules

    def test_onetailed_no_hyphen_triggers(self):
        findings = audit_text("A onetailed test was used.")
        rules = [f.rule for f in findings]
        assert "one_tailed" in rules


class TestRuleNhstOnly:
    def test_significant_triggers(self):
        findings = audit_text("The difference was significant.")
        rules = [f.rule for f in findings]
        assert "nhst_only" in rules

    def test_insignificant_triggers(self):
        findings = audit_text("The difference was insignificant.")
        rules = [f.rule for f in findings]
        assert "nhst_only" in rules


class TestRuleRegressionR2:
    def test_regression_without_r2_triggers(self):
        findings = audit_text("We ran a regression on the data.")
        rules = [f.rule for f in findings]
        assert "regression_r2_missing" in rules

    def test_regression_with_r2_ok(self):
        findings = audit_text("We ran a regression; R² = .45.")
        rules = [f.rule for f in findings]
        assert "regression_r2_missing" not in rules

    def test_regression_with_r_squared_ok(self):
        # R-squared must appear in the same sentence as "regression" for the rule to suppress
        findings = audit_text("We ran a regression with R-squared = .45.")
        rules = [f.rule for f in findings]
        assert "regression_r2_missing" not in rules


class TestRuleCorrelationMissingN:
    def test_r_triggers(self):
        findings = audit_text("The correlation was r = .45.")
        rules = [f.rule for f in findings]
        assert "correlation_missing_n" in rules


class TestRuleSeedUnreported:
    def test_random_seed_triggers(self):
        findings = audit_text("We set a random seed for reproducibility.")
        rules = [f.rule for f in findings]
        assert "seed_unreported" in rules


# ── severity filtering ────────────────────────────────────────────────────────

class TestSeverityFiltering:
    def test_info_includes_all(self):
        text = "The result was ns. The value was 3.14159265."
        info = audit_text(text, Severity.INFO)
        warn = audit_text(text, Severity.WARNING)
        assert len(info) >= len(warn)

    def test_warning_excludes_info(self):
        findings = audit_text("The value was 3.14159265.", Severity.WARNING)
        assert all(f.severity >= Severity.WARNING for f in findings)

    def test_error_excludes_info_and_warning(self):
        findings = audit_text("The result was ns.", Severity.ERROR)
        assert all(f.severity == Severity.ERROR for f in findings)


# ── audit_file ────────────────────────────────────────────────────────────────

class TestAuditFile:
    def test_finds_issues_in_file(self, tmp_path):
        f = tmp_path / "ms.txt"
        f.write_text("The result was ns. We found t = 3.4.", encoding="utf-8")
        findings = audit_file(f)
        assert len(findings) > 0

    def test_location_is_line_number(self, tmp_path):
        f = tmp_path / "ms.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        findings = audit_file(f)
        assert any(f.location.startswith("line ") for f in findings)

    def test_empty_file_no_findings(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert audit_file(f) == []


# ── AuditReport ───────────────────────────────────────────────────────────────

class TestAuditReport:
    def _report_with(self, *sevs: Severity) -> AuditReport:
        findings = [
            Finding(f"rule_{i}", "text", "sentence 1", sev, "suggestion")
            for i, sev in enumerate(sevs)
        ]
        return AuditReport(source="test", findings=findings)

    def test_summary_total(self):
        r = self._report_with(Severity.ERROR, Severity.WARNING, Severity.INFO)
        assert r.summary["total"] == 3

    def test_summary_counts(self):
        r = self._report_with(Severity.ERROR, Severity.WARNING, Severity.INFO)
        s = r.summary["by_severity"]
        assert s["ERROR"] == 1
        assert s["WARNING"] == 1
        assert s["INFO"] == 1

    def test_to_text_no_findings(self):
        r = AuditReport(source="test", findings=[])
        assert "No findings" in r.to_text()

    def test_to_text_with_findings(self):
        r = self._report_with(Severity.WARNING)
        t = r.to_text()
        assert "Audit report" in t
        assert "WARNING" in t

    def test_to_markdown_header(self):
        r = AuditReport(source="test", findings=[])
        md = r.to_markdown()
        assert "# Statistical Audit Report" in md

    def test_to_markdown_source(self):
        r = AuditReport(source="my_paper.txt", findings=[])
        md = r.to_markdown()
        assert "my_paper.txt" in md

    def test_to_json_valid(self):
        r = self._report_with(Severity.INFO)
        data = json.loads(r.to_json())
        assert "findings" in data
        assert "summary" in data
        assert len(data["findings"]) == 1

    def test_to_json_severity_string(self):
        r = self._report_with(Severity.ERROR)
        data = json.loads(r.to_json())
        assert data["findings"][0]["severity"] == "ERROR"

    def test_to_html_doctype(self):
        r = AuditReport(source="test", findings=[])
        assert "<!DOCTYPE html>" in r.to_html()

    def test_to_html_contains_source(self):
        r = AuditReport(source="my_paper.txt", findings=[])
        assert "my_paper.txt" in r.to_html()

    def test_to_html_with_findings(self):
        r = self._report_with(Severity.WARNING)
        html = r.to_html()
        assert "WARNING" in html
        assert "<table" in html

    def test_save_html(self, tmp_path):
        r = AuditReport(source="test", findings=[])
        out = str(tmp_path / "report.html")
        r.save_html(out)
        content = (tmp_path / "report.html").read_text()
        assert "<!DOCTYPE html>" in content

    def test_save_formats(self, tmp_path):
        r = self._report_with(Severity.INFO)
        for fmt, ext in [("text", ".txt"), ("markdown", ".md"), ("json", ".json"), ("html", ".html")]:
            out = tmp_path / f"report{ext}"
            r.save(str(out), fmt=fmt)
            assert out.exists()
            assert out.stat().st_size > 0


# ── StatAuditor ───────────────────────────────────────────────────────────────

class TestStatAuditor:
    def test_run_returns_report(self):
        auditor = StatAuditor("The result was ns.")
        report = auditor.run()
        assert isinstance(report, AuditReport)

    def test_run_finds_issues(self):
        auditor = StatAuditor("The result was ns, t = 3.4.")
        report = auditor.run()
        assert len(report.findings) > 0

    def test_run_with_file(self, tmp_path):
        f = tmp_path / "ms.txt"
        f.write_text("The result was ns.", encoding="utf-8")
        auditor = StatAuditor(str(f))
        report = auditor.run()
        assert len(report.findings) > 0

    def test_run_min_severity(self):
        auditor = StatAuditor("The result was ns, t = 3.4.")
        info_report = auditor.run(Severity.INFO)
        warn_report = auditor.run(Severity.WARNING)
        assert len(info_report.findings) >= len(warn_report.findings)

    def test_source_attribute(self):
        auditor = StatAuditor("Some text.")
        assert auditor.source == "Some text."


# ── regression: specific bugs fixed ──────────────────────────────────────────

class TestBugFixes:
    """Regression tests for bugs that existed in the original stataudit.py."""

    def test_pvalue_over_precision_was_broken(self):
        # Original regex r'\bp\s*=\s*\.?0{4,}\d+' failed to match p = 0.0001
        # because \.? didn't match the leading '0' in '0.0001'.
        findings = audit_text("p = 0.0001 was observed.")
        rules = [f.rule for f in findings]
        assert "pvalue_over_precision" in rules

    def test_regression_r2_was_broken(self):
        # Original regex had R.squared (dot = any char), now fixed to proper pattern.
        # Regression WITHOUT R² should trigger; regression WITH R² should not.
        findings_without = audit_text("We ran a regression.")
        findings_with = audit_text("We ran a regression with R2 = .55.")
        rules_without = [f.rule for f in findings_without]
        rules_with = [f.rule for f in findings_with]
        assert "regression_r2_missing" in rules_without
        assert "regression_r2_missing" not in rules_with

    def test_audit_text_empty_was_not_guarded(self):
        # Original audit_text had no early return for empty/whitespace input.
        assert audit_text("") == []
        assert audit_text("   ") == []
