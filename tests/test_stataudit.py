"""
tests/test_stataudit.py — comprehensive test suite for stataudit.

Run with:  pytest tests/ -v
"""

import json
import sys
import pathlib

import pytest

# Make root-level stataudit importable when tests run from any directory
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import stataudit as sa
from stataudit import (
    AuditReport,
    Finding,
    Severity,
    _RULES,
    _split_sentences,
    audit_file,
    audit_text,
    main,
)


# ---------------------------------------------------------------------------
# Public API availability
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_audit_report_exported(self):
        assert hasattr(sa, "AuditReport")

    def test_finding_exported(self):
        assert hasattr(sa, "Finding")

    def test_audit_text_exported(self):
        assert callable(sa.audit_text)

    def test_audit_file_exported(self):
        assert callable(sa.audit_file)

    def test_severity_exported(self):
        assert hasattr(sa, "Severity")

    def test_version_defined(self):
        assert hasattr(sa, "__version__")
        assert isinstance(sa.__version__, str)


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

class TestSeverityOrdering:
    def test_info_lt_warning(self):
        assert Severity.INFO < Severity.WARNING

    def test_warning_lt_error(self):
        assert Severity.WARNING < Severity.ERROR

    def test_info_lt_error(self):
        assert Severity.INFO < Severity.ERROR

    def test_error_gt_warning(self):
        assert Severity.ERROR > Severity.WARNING

    def test_info_le_info(self):
        assert Severity.INFO <= Severity.INFO

    def test_error_ge_error(self):
        assert Severity.ERROR >= Severity.ERROR

    def test_warning_ge_info(self):
        assert Severity.WARNING >= Severity.INFO

    def test_info_not_gt_warning(self):
        assert not (Severity.INFO > Severity.WARNING)


# ---------------------------------------------------------------------------
# _split_sentences
# ---------------------------------------------------------------------------

class TestSplitSentences:
    def test_two_sentences(self):
        parts = _split_sentences("Hello world. This is a test.")
        assert len(parts) == 2

    def test_single_sentence(self):
        parts = _split_sentences("No split here")
        assert len(parts) == 1

    def test_empty_string(self):
        parts = _split_sentences("")
        assert parts == [""]

    def test_exclamation(self):
        parts = _split_sentences("First! Second.")
        assert len(parts) == 2

    def test_question(self):
        parts = _split_sentences("Really? Yes.")
        assert len(parts) == 2


# ---------------------------------------------------------------------------
# audit_text — empty / whitespace
# ---------------------------------------------------------------------------

class TestAuditTextEdgeCases:
    def test_empty_string(self):
        assert audit_text("") == []

    def test_whitespace_only(self):
        assert audit_text("   \n\t  ") == []

    def test_returns_list(self):
        result = audit_text("plain text with no stats")
        assert isinstance(result, list)

    def test_no_false_positives_clean(self):
        # A sentence with no statistical content should produce no findings
        findings = audit_text("The participants completed the questionnaire.")
        assert findings == []


# ---------------------------------------------------------------------------
# Rule: pvalue_ns
# ---------------------------------------------------------------------------

class TestRulePvalueNs:
    def test_bare_ns(self):
        findings = audit_text("The difference was ns.")
        assert any(f.rule == "pvalue_ns" for f in findings)

    def test_parenthesised_ns(self):
        findings = audit_text("The result (ns) was not significant.")
        assert any(f.rule == "pvalue_ns" for f in findings)

    def test_no_false_positive(self):
        # 'ns' inside a word should not match
        findings = audit_text("The instance count was noted.")
        assert not any(f.rule == "pvalue_ns" for f in findings)


# ---------------------------------------------------------------------------
# Rule: pvalue_exact
# ---------------------------------------------------------------------------

class TestRulePvalueExact:
    def test_equals(self):
        findings = audit_text("We found p = .034.")
        assert any(f.rule == "pvalue_exact" for f in findings)

    def test_less_than(self):
        findings = audit_text("Results were p < .001.")
        assert any(f.rule == "pvalue_exact" for f in findings)

    def test_greater_than(self):
        findings = audit_text("We noted p > .05.")
        assert any(f.rule == "pvalue_exact" for f in findings)

    def test_scientific_notation(self):
        findings = audit_text("We observed p = 3.2e-5.")
        assert any(f.rule == "pvalue_exact" for f in findings)


# ---------------------------------------------------------------------------
# Rule: pvalue_over_precision
# ---------------------------------------------------------------------------

class TestRulePvalueOverPrecision:
    def test_leading_dot_form(self):
        findings = audit_text("Significance: p = .000012.")
        assert any(f.rule == "pvalue_over_precision" for f in findings)

    def test_zero_dot_form(self):
        # Regression: 0.00001 was previously not caught
        findings = audit_text("We got p = 0.00001.")
        assert any(f.rule == "pvalue_over_precision" for f in findings)

    def test_three_zeros_not_flagged(self):
        # p = 0.001 is three zeros, should NOT trigger over_precision
        findings = audit_text("We found p = .001.")
        assert not any(f.rule == "pvalue_over_precision" for f in findings)


# ---------------------------------------------------------------------------
# Rule: ci_level_missing
# ---------------------------------------------------------------------------

class TestRuleCILevelMissing:
    def test_bare_ci_flagged(self):
        findings = audit_text("The CI was [1.2, 3.4].")
        assert any(f.rule == "ci_level_missing" for f in findings)

    def test_confidence_interval_spelled_out(self):
        findings = audit_text("The confidence interval ranged from 1 to 3.")
        assert any(f.rule == "ci_level_missing" for f in findings)

    def test_95_percent_ci_not_flagged(self):
        # "95% CI" should NOT be flagged — percentage precedes CI
        findings = audit_text("The 95% CI was [1.2, 3.4].")
        assert not any(f.rule == "ci_level_missing" for f in findings)

    def test_99_percent_ci_not_flagged(self):
        findings = audit_text("We report a 99% CI.")
        assert not any(f.rule == "ci_level_missing" for f in findings)

    def test_no_space_percent_ci_not_flagged(self):
        # "95%CI" (no space) should also not be flagged
        findings = audit_text("The 95%CI was [1.2, 3.4].")
        assert not any(f.rule == "ci_level_missing" for f in findings)


# ---------------------------------------------------------------------------
# Rule: t_test_df_missing
# ---------------------------------------------------------------------------

class TestRuleTTestDFMissing:
    def test_bare_t_value(self):
        findings = audit_text("We found t = 2.5.")
        assert any(f.rule == "t_test_df_missing" for f in findings)

    def test_negative_t_value(self):
        findings = audit_text("The test yielded t = -1.96.")
        assert any(f.rule == "t_test_df_missing" for f in findings)

    def test_t_with_df_not_flagged(self):
        # t(29) = 2.5 — correct APA format, should NOT be flagged
        findings = audit_text("We found t(29) = 2.5.")
        assert not any(f.rule == "t_test_df_missing" for f in findings)


# ---------------------------------------------------------------------------
# Rule: anova_missing_df
# ---------------------------------------------------------------------------

class TestRuleANOVAMissingDF:
    def test_bare_f_value(self):
        findings = audit_text("The ANOVA yielded F = 4.5.")
        assert any(f.rule == "anova_missing_df" for f in findings)

    def test_f_with_df_not_flagged(self):
        findings = audit_text("We found F(2, 87) = 4.5.")
        assert not any(f.rule == "anova_missing_df" for f in findings)


# ---------------------------------------------------------------------------
# Rule: sample_size_small
# ---------------------------------------------------------------------------

class TestRuleSampleSizeSmall:
    def test_n_equals_15(self):
        findings = audit_text("The study had N = 15 participants.")
        assert any(f.rule == "sample_size_small" for f in findings)

    def test_n_equals_1(self):
        findings = audit_text("Case study: n = 1.")
        assert any(f.rule == "sample_size_small" for f in findings)

    def test_n_equals_29(self):
        findings = audit_text("We recruited n = 29 volunteers.")
        assert any(f.rule == "sample_size_small" for f in findings)

    def test_n_equals_30_not_flagged(self):
        findings = audit_text("The study had N = 30 participants.")
        assert not any(f.rule == "sample_size_small" for f in findings)

    def test_n_equals_100_not_flagged(self):
        findings = audit_text("The study had N = 100 participants.")
        assert not any(f.rule == "sample_size_small" for f in findings)


# ---------------------------------------------------------------------------
# Rule: over_precision
# ---------------------------------------------------------------------------

class TestRuleOverPrecision:
    def test_six_decimal_places(self):
        findings = audit_text("The mean was 3.123456 units.")
        assert any(f.rule == "over_precision" for f in findings)

    def test_four_decimal_places_not_flagged(self):
        findings = audit_text("The mean was 3.1234 units.")
        assert not any(f.rule == "over_precision" for f in findings)


# ---------------------------------------------------------------------------
# Rule: one_tailed
# ---------------------------------------------------------------------------

class TestRuleOneTailed:
    def test_hyphenated(self):
        findings = audit_text("We used a one-tailed test.")
        assert any(f.rule == "one_tailed" for f in findings)

    def test_no_hyphen(self):
        findings = audit_text("A one tailed hypothesis was tested.")
        assert any(f.rule == "one_tailed" for f in findings)


# ---------------------------------------------------------------------------
# Rule: nhst_only
# ---------------------------------------------------------------------------

class TestRuleNHSTOnly:
    def test_significant(self):
        findings = audit_text("The effect was significant.")
        assert any(f.rule == "nhst_only" for f in findings)

    def test_insignificant(self):
        findings = audit_text("The difference was insignificant.")
        assert any(f.rule == "nhst_only" for f in findings)

    def test_failed_to_reject(self):
        findings = audit_text("We failed to reject the null hypothesis.")
        assert any(f.rule == "nhst_only" for f in findings)


# ---------------------------------------------------------------------------
# Rule: outlier_handling
# ---------------------------------------------------------------------------

class TestRuleOutlierHandling:
    def test_outlier(self):
        findings = audit_text("Outlier observations were removed from analysis.")
        assert any(f.rule == "outlier_handling" for f in findings)

    def test_outliers_plural(self):
        findings = audit_text("Three outliers were identified.")
        assert any(f.rule == "outlier_handling" for f in findings)


# ---------------------------------------------------------------------------
# Rule: missing_data
# ---------------------------------------------------------------------------

class TestRuleMissingData:
    def test_missing_data(self):
        findings = audit_text("Missing data were handled by listwise deletion.")
        assert any(f.rule == "missing_data" for f in findings)

    def test_missing_values(self):
        findings = audit_text("Missing values were imputed using MICE.")
        assert any(f.rule == "missing_data" for f in findings)

    def test_missing_cases(self):
        findings = audit_text("Missing cases were excluded.")
        assert any(f.rule == "missing_data" for f in findings)


# ---------------------------------------------------------------------------
# Rule: regression_r2_missing
# ---------------------------------------------------------------------------

class TestRuleRegressionR2Missing:
    def test_regression_flagged(self):
        findings = audit_text("We regressed the outcome on age and education.")
        assert any(f.rule == "regression_r2_missing" for f in findings)

    def test_regression_r_squared_not_flagged(self):
        findings = audit_text("The regression yielded R-squared = 0.45.")
        assert not any(f.rule == "regression_r2_missing" for f in findings)

    def test_regression_r2_not_flagged(self):
        findings = audit_text("The regression model had R2 = .52.")
        assert not any(f.rule == "regression_r2_missing" for f in findings)


# ---------------------------------------------------------------------------
# Rule: multiple_comparisons
# ---------------------------------------------------------------------------

class TestRuleMultipleComparisons:
    def test_bonferroni(self):
        findings = audit_text("Bonferroni correction was applied.")
        assert any(f.rule == "multiple_comparisons" for f in findings)

    def test_fdr(self):
        findings = audit_text("FDR correction controlled for multiplicity.")
        assert any(f.rule == "multiple_comparisons" for f in findings)

    def test_benjamini_hochberg(self):
        findings = audit_text("The Benjamini-Hochberg procedure was used.")
        assert any(f.rule == "multiple_comparisons" for f in findings)


# ---------------------------------------------------------------------------
# Rule: correlation_missing_n
# ---------------------------------------------------------------------------

class TestRuleCorrelationMissingN:
    def test_pearson_r(self):
        findings = audit_text("We found r = 0.45 between the variables.")
        assert any(f.rule == "correlation_missing_n" for f in findings)

    def test_negative_r(self):
        findings = audit_text("A negative correlation r = -0.32 was observed.")
        assert any(f.rule == "correlation_missing_n" for f in findings)


# ---------------------------------------------------------------------------
# Rule: effect_size_check
# ---------------------------------------------------------------------------

class TestRuleEffectSizeCheck:
    def test_cohens_d(self):
        findings = audit_text("The effect size Cohen's d = 0.5 was medium.")
        assert any(f.rule == "effect_size_check" for f in findings)

    def test_eta_squared(self):
        findings = audit_text("Partial eta-squared was .12.")
        assert any(f.rule == "effect_size_check" for f in findings)

    def test_effect_size_phrase(self):
        findings = audit_text("The effect size was not reported.")
        assert any(f.rule == "effect_size_check" for f in findings)


# ---------------------------------------------------------------------------
# Severity filtering
# ---------------------------------------------------------------------------

class TestSeverityFiltering:
    def test_filter_warning_excludes_info(self):
        findings = audit_text(
            "The mean was 3.123456. The result was ns.",
            min_severity=Severity.WARNING,
        )
        for f in findings:
            assert f.severity >= Severity.WARNING

    def test_filter_error_no_warning_info(self):
        findings = audit_text(
            "The result was ns. We found t = 2.5.",
            min_severity=Severity.ERROR,
        )
        for f in findings:
            assert f.severity == Severity.ERROR

    def test_info_includes_all(self):
        text = "The result was ns. We found t = 2.5. The mean was 3.123456."
        info_findings = audit_text(text, min_severity=Severity.INFO)
        warn_findings = audit_text(text, min_severity=Severity.WARNING)
        assert len(info_findings) >= len(warn_findings)


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

class TestFinding:
    def test_str_contains_severity(self):
        f = Finding(
            rule="test_rule",
            text="example text",
            location="line 1",
            severity=Severity.WARNING,
            suggestion="Fix it.",
        )
        assert "[WARNING]" in str(f)

    def test_str_contains_rule(self):
        f = Finding(
            rule="my_rule",
            text="x",
            location="line 1",
            severity=Severity.INFO,
            suggestion="Do something.",
        )
        assert "my_rule" in str(f)

    def test_to_dict_severity_is_string(self):
        f = Finding(
            rule="r",
            text="t",
            location="l",
            severity=Severity.ERROR,
            suggestion="s",
        )
        d = f.to_dict()
        assert d["severity"] == "ERROR"
        assert isinstance(d["severity"], str)

    def test_to_dict_keys(self):
        f = Finding(
            rule="r", text="t", location="l", severity=Severity.INFO, suggestion="s"
        )
        d = f.to_dict()
        assert set(d.keys()) == {"rule", "text", "location", "severity", "suggestion"}


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------

class TestAuditReport:
    def _sample_report(self) -> AuditReport:
        findings = audit_text("The result was ns. We found t = 2.5. The mean was 3.123456.")
        return AuditReport(source="test.txt", findings=findings)

    def test_summary_keys(self):
        report = self._sample_report()
        s = report.summary
        assert "source" in s
        assert "total" in s
        assert "by_severity" in s

    def test_summary_total_matches_findings(self):
        report = self._sample_report()
        assert report.summary["total"] == len(report.findings)

    def test_summary_by_severity_sums(self):
        report = self._sample_report()
        bysev = report.summary["by_severity"]
        assert sum(bysev.values()) == len(report.findings)

    def test_to_text_non_empty(self):
        report = self._sample_report()
        assert isinstance(report.to_text(), str)
        assert len(report.to_text()) > 0

    def test_to_markdown_header(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "# Statistical Audit Report" in md

    def test_to_markdown_source(self):
        report = self._sample_report()
        assert "test.txt" in report.to_markdown()

    def test_to_json_valid(self):
        report = self._sample_report()
        parsed = json.loads(report.to_json())
        assert "findings" in parsed
        assert "summary" in parsed

    def test_to_json_findings_list(self):
        report = self._sample_report()
        parsed = json.loads(report.to_json())
        assert isinstance(parsed["findings"], list)

    def test_empty_report_text(self):
        report = AuditReport(source="empty.txt", findings=[])
        assert report.to_text() == "No findings for empty.txt."

    def test_empty_report_markdown(self):
        report = AuditReport(source="empty.txt", findings=[])
        assert "_No findings._" in report.to_markdown()

    def test_empty_report_json(self):
        report = AuditReport(source="empty.txt", findings=[])
        parsed = json.loads(report.to_json())
        assert parsed["findings"] == []
        assert parsed["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------

class TestAuditFile:
    def test_findings_returned(self, tmp_path):
        p = tmp_path / "sample.txt"
        p.write_text(
            "The result was ns. We found t = 2.5.", encoding="utf-8"
        )
        findings = audit_file(p)
        assert len(findings) > 0

    def test_locations_are_line_numbers(self, tmp_path):
        p = tmp_path / "sample.txt"
        p.write_text(
            "The result was ns.\nWe found t = 2.5.\n", encoding="utf-8"
        )
        findings = audit_file(p)
        for f in findings:
            assert f.location.startswith("line"), f"Expected 'line N', got {f.location!r}"

    def test_severity_filter_applied(self, tmp_path):
        p = tmp_path / "sample.txt"
        p.write_text("The mean was 3.123456. The result was ns.", encoding="utf-8")
        findings = audit_file(p, min_severity=Severity.WARNING)
        for f in findings:
            assert f.severity >= Severity.WARNING

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.txt"
        p.write_text("", encoding="utf-8")
        assert audit_file(p) == []


# ---------------------------------------------------------------------------
# CLI (main function)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_list_rules_exit_zero(self, capsys):
        rc = main(["--list-rules"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_file_input_text_format(self, tmp_path, capsys):
        p = tmp_path / "doc.txt"
        p.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(p)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_file_input_json_format(self, tmp_path, capsys):
        p = tmp_path / "doc.txt"
        p.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(p), "--format", "json"])
        parsed = json.loads(capsys.readouterr().out)
        assert "findings" in parsed

    def test_file_input_markdown_format(self, tmp_path, capsys):
        p = tmp_path / "doc.txt"
        p.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(p), "--format", "markdown"])
        out = capsys.readouterr().out
        assert "# Statistical Audit Report" in out

    def test_output_file_written(self, tmp_path, capsys):
        p = tmp_path / "doc.txt"
        out_p = tmp_path / "report.txt"
        p.write_text("The result was ns.", encoding="utf-8")
        main([str(p), "--output", str(out_p)])
        assert out_p.exists()
        assert "pvalue_ns" in out_p.read_text()

    def test_missing_file_returns_1(self, capsys):
        rc = main(["nonexistent_file_xyz.txt"])
        assert rc == 1

    def test_severity_filter_warning(self, tmp_path, capsys):
        p = tmp_path / "doc.txt"
        p.write_text("The result was ns. Mean = 3.123456.", encoding="utf-8")
        main([str(p), "--severity", "WARNING"])
        out = capsys.readouterr().out
        assert "pvalue_ns" in out
        # over_precision is INFO; should be filtered out
        assert "over_precision" not in out

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0

    def test_no_error_findings_returns_0(self, tmp_path, capsys):
        p = tmp_path / "clean.txt"
        p.write_text("The participants completed the questionnaire.", encoding="utf-8")
        rc = main([str(p)])
        assert rc == 0


# ---------------------------------------------------------------------------
# Rules completeness
# ---------------------------------------------------------------------------

class TestRulesCompleteness:
    def test_rule_names_unique(self):
        names = [r[0] for r in _RULES]
        assert len(names) == len(set(names)), "Duplicate rule names detected"

    def test_all_rules_have_suggestion(self):
        for name, _, _, suggestion in _RULES:
            assert suggestion, f"Rule {name!r} has empty suggestion"

    def test_all_patterns_compile(self):
        import re
        for name, pattern, _, _ in _RULES:
            assert hasattr(pattern, "finditer"), f"Rule {name!r} pattern is not compiled"
