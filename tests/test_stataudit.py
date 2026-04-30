"""
Tests for stataudit — Statistical Reporting Auditor.

Run with:  pytest tests/
"""
import json
import pathlib
import sys
import tempfile

import pytest

# Allow importing the top-level stataudit.py when running from anywhere.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import stataudit as sa
from stataudit import (
    AuditReport,
    Finding,
    Severity,
    audit_file,
    audit_text,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rules(findings):
    """Return the set of rule names triggered."""
    return {f.rule for f in findings}


def _severities(findings):
    return {f.severity for f in findings}


# ---------------------------------------------------------------------------
# Module-level API smoke tests
# ---------------------------------------------------------------------------

class TestModuleAPI:
    def test_public_symbols_exported(self):
        for name in sa.__all__:
            assert hasattr(sa, name), f"Missing public symbol: {name}"

    def test_version_string(self):
        assert isinstance(sa.__version__, str)
        major, minor, patch = sa.__version__.split(".")
        assert major.isdigit() and minor.isdigit() and patch.isdigit()

    def test_audit_text_callable(self):
        assert callable(audit_text)

    def test_audit_file_callable(self):
        assert callable(audit_file)

    def test_finding_is_dataclass(self):
        f = Finding(
            rule="test", text="x", location="sentence 1",
            severity=Severity.INFO, suggestion="do something"
        )
        assert f.rule == "test"

    def test_audit_report_instantiation(self):
        r = AuditReport(source="test")
        assert r.findings == []


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

class TestSeverity:
    def test_order(self):
        assert Severity.INFO < Severity.WARNING < Severity.ERROR

    def test_ge(self):
        assert Severity.ERROR >= Severity.WARNING
        assert Severity.WARNING >= Severity.INFO

    def test_eq(self):
        assert Severity.INFO == Severity.INFO

    def test_filter_respected(self):
        text = "We found ns results with p = .034 and t = 2.3."
        info_count = len(audit_text(text, Severity.INFO))
        warn_count = len(audit_text(text, Severity.WARNING))
        assert info_count >= warn_count


# ---------------------------------------------------------------------------
# Empty / trivial input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_string(self):
        assert audit_text("") == []

    def test_whitespace_only(self):
        assert audit_text("   \n\t  ") == []

    def test_no_stats_text(self):
        findings = audit_text("The weather is nice today.")
        assert findings == []


# ---------------------------------------------------------------------------
# Individual rule tests
# ---------------------------------------------------------------------------

class TestPValueRules:
    def test_pvalue_exact_triggers(self):
        findings = audit_text("The difference was significant (p = .034).")
        assert "pvalue_exact" in _rules(findings)

    def test_pvalue_exact_less_than(self):
        findings = audit_text("Results: p < .001.")
        assert "pvalue_exact" in _rules(findings)

    def test_pvalue_ns_triggers(self):
        findings = audit_text("The difference was ns.")
        assert "pvalue_ns" in _rules(findings)

    def test_pvalue_ns_parenthetical(self):
        findings = audit_text("No effect was found (ns).")
        assert "pvalue_ns" in _rules(findings)

    def test_pvalue_zero_triggers(self):
        findings = audit_text("We found p = 0.000 for the test.")
        assert "pvalue_zero" in _rules(findings)

    def test_pvalue_zero_integer(self):
        findings = audit_text("p = 0 was observed.")
        assert "pvalue_zero" in _rules(findings)

    def test_pvalue_over_precision(self):
        findings = audit_text("The result was p = .00000234.")
        assert "pvalue_over_precision" in _rules(findings)

    def test_apa_format_with_leading_zero(self):
        findings = audit_text("Results showed p = 0.045.")
        assert "apa_p_format" in _rules(findings)

    def test_apa_format_no_false_positive_without_zero(self):
        findings = audit_text("Results showed p = .045.")
        assert "apa_p_format" not in _rules(findings)


class TestCIRules:
    def test_ci_level_missing_bare_ci(self):
        findings = audit_text("The 95% CI was [1.2, 3.4].")
        # "95% CI" has a digit after CI so should NOT trigger
        assert "ci_level_missing" not in _rules(findings)

    def test_ci_level_missing_bare_abbreviation(self):
        findings = audit_text("The CI was [1.2, 3.4].")
        assert "ci_level_missing" in _rules(findings)

    def test_ci_level_missing_full_words(self):
        findings = audit_text("The confidence interval ranged from 1 to 3.")
        assert "ci_level_missing" in _rules(findings)


class TestTestStatisticRules:
    def test_t_test_df_missing(self):
        findings = audit_text("The test yielded t = 2.31.")
        assert "t_test_df_missing" in _rules(findings)

    def test_t_test_with_df_no_flag(self):
        # t(df) format should NOT trigger the rule
        findings = audit_text("The test yielded t(48) = 2.31.")
        assert "t_test_df_missing" not in _rules(findings)

    def test_anova_missing_df(self):
        findings = audit_text("An ANOVA showed F = 4.52.")
        assert "anova_missing_df" in _rules(findings)

    def test_anova_with_df_no_flag(self):
        findings = audit_text("ANOVA showed F(2, 57) = 4.52.")
        assert "anova_missing_df" not in _rules(findings)


class TestEffectSizeRules:
    def test_sample_size_small_single_digit(self):
        findings = audit_text("The study used N = 8 participants.")
        assert "sample_size_small" in _rules(findings)

    def test_sample_size_small_below_30(self):
        findings = audit_text("We recruited n = 25 subjects.")
        assert "sample_size_small" in _rules(findings)

    def test_sample_size_adequate_no_flag(self):
        findings = audit_text("N = 120 participants completed the study.")
        assert "sample_size_small" not in _rules(findings)

    def test_nhst_only_significant(self):
        findings = audit_text("The effect was significant.")
        assert "nhst_only" in _rules(findings)

    def test_nhst_only_insignificant(self):
        findings = audit_text("The result was insignificant.")
        assert "nhst_only" in _rules(findings)

    def test_nhst_only_failed_to_reject(self):
        findings = audit_text("We failed to reject the null hypothesis.")
        assert "nhst_only" in _rules(findings)

    def test_correlation_missing_n(self):
        findings = audit_text("The correlation was r = .45.")
        assert "correlation_missing_n" in _rules(findings)

    def test_regression_r2_missing(self):
        findings = audit_text("We regressed score on time.")
        assert "regression_r2_missing" in _rules(findings)

    def test_regression_r2_present_no_flag(self):
        findings = audit_text("Regression of score on time showed R² = .32.")
        assert "regression_r2_missing" not in _rules(findings)


class TestPrecisionRules:
    def test_over_precision(self):
        findings = audit_text("The mean was 3.141592.")
        assert "over_precision" in _rules(findings)

    def test_normal_precision_no_flag(self):
        findings = audit_text("The mean was 3.14.")
        assert "over_precision" not in _rules(findings)


class TestMethodologyRules:
    def test_one_tailed(self):
        findings = audit_text("A one-tailed test was applied.")
        assert "one_tailed" in _rules(findings)

    def test_one_tailed_no_hyphen(self):
        findings = audit_text("We used a one tailed t-test.")
        assert "one_tailed" in _rules(findings)

    def test_multiple_comparisons_bonferroni(self):
        findings = audit_text("Bonferroni correction was applied.")
        assert "multiple_comparisons" in _rules(findings)

    def test_multiple_comparisons_fdr(self):
        findings = audit_text("FDR correction was used.")
        assert "multiple_comparisons" in _rules(findings)

    def test_multiple_comparisons_holm(self):
        findings = audit_text("The Holm-Bonferroni method was applied.")
        assert "multiple_comparisons" in _rules(findings)


class TestDataDisclosureRules:
    def test_outlier_handling(self):
        findings = audit_text("Two outlier cases were removed.")
        assert "outlier_handling" in _rules(findings)

    def test_missing_data(self):
        findings = audit_text("Missing data were handled by listwise deletion.")
        assert "missing_data" in _rules(findings)

    def test_missing_values(self):
        findings = audit_text("There were 12 missing values in the dataset.")
        assert "missing_data" in _rules(findings)


class TestMLRules:
    def test_seed_unreported_random(self):
        findings = audit_text("Weights were randomly initialized.")
        assert "seed_unreported" in _rules(findings)

    def test_seed_unreported_stochastic(self):
        findings = audit_text("The stochastic gradient descent optimizer was used.")
        assert "seed_unreported" in _rules(findings)


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------

class TestAuditFile:
    def test_basic_file(self, tmp_path):
        p = tmp_path / "ms.txt"
        p.write_text("The result was significant (p = .031).\n", encoding="utf-8")
        findings = audit_file(p)
        assert len(findings) > 0
        assert all(f.location.startswith("line") for f in findings)

    def test_file_location_line_1(self, tmp_path):
        p = tmp_path / "ms.txt"
        p.write_text("t = 2.31 was observed.\n", encoding="utf-8")
        findings = audit_file(p)
        t_findings = [f for f in findings if f.rule == "t_test_df_missing"]
        assert t_findings
        assert t_findings[0].location == "line 1"

    def test_file_multiline_location(self, tmp_path):
        p = tmp_path / "ms.txt"
        content = "First line has no stats.\nSecond line: t = 3.1.\n"
        p.write_text(content, encoding="utf-8")
        findings = audit_file(p)
        t_findings = [f for f in findings if f.rule == "t_test_df_missing"]
        assert t_findings
        assert t_findings[0].location == "line 2"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            audit_file(tmp_path / "nonexistent.txt")

    def test_severity_filter_in_file(self, tmp_path):
        p = tmp_path / "ms.txt"
        p.write_text("Result: ns, p = .034, t = 2.1.\n", encoding="utf-8")
        all_f = audit_file(p, Severity.INFO)
        warn_f = audit_file(p, Severity.WARNING)
        assert len(all_f) >= len(warn_f)


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------

class TestAuditReport:
    def _sample_report(self):
        findings = [
            Finding("r1", "some text", "sentence 1", Severity.WARNING, "fix it"),
            Finding("r2", "more text", "sentence 2", Severity.INFO,    "note"),
        ]
        return AuditReport(source="test.txt", findings=findings)

    def test_summary_counts(self):
        r = self._sample_report()
        s = r.summary
        assert s["total"] == 2
        assert s["by_severity"]["WARNING"] == 1
        assert s["by_severity"]["INFO"] == 1
        assert s["by_severity"]["ERROR"] == 0

    def test_to_text_contains_rule(self):
        r = self._sample_report()
        out = r.to_text()
        assert "r1" in out
        assert "r2" in out

    def test_to_text_empty(self):
        r = AuditReport(source="test.txt")
        assert "No findings" in r.to_text()

    def test_to_markdown_has_header(self):
        r = self._sample_report()
        md = r.to_markdown()
        assert "# Statistical Audit Report" in md
        assert "## WARNING" in md
        assert "## INFO" in md

    def test_to_markdown_empty(self):
        r = AuditReport(source="test.txt")
        md = r.to_markdown()
        assert "_No findings._" in md

    def test_to_json_valid(self):
        r = self._sample_report()
        data = json.loads(r.to_json())
        assert "summary" in data
        assert "findings" in data
        assert data["summary"]["total"] == 2
        assert len(data["findings"]) == 2

    def test_to_json_severity_serialised_as_string(self):
        r = self._sample_report()
        data = json.loads(r.to_json())
        sevs = {f["severity"] for f in data["findings"]}
        assert sevs == {"WARNING", "INFO"}

    def test_finding_to_dict(self):
        f = Finding("rule", "txt", "loc", Severity.ERROR, "sug")
        d = f.to_dict()
        assert d["severity"] == "ERROR"
        assert d["rule"] == "rule"

    def test_finding_str(self):
        f = Finding("myrule", "text", "line 3", Severity.WARNING, "fix this")
        s = str(f)
        assert "myrule" in s
        assert "WARNING" in s
        assert "line 3" in s


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_list_rules(self, capsys):
        rc = main(["--list-rules"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pvalue_exact" in out
        assert "pvalue_ns" in out

    def test_file_audit_text_format(self, tmp_path, capsys):
        p = tmp_path / "ms.txt"
        p.write_text("There were ns results.\n", encoding="utf-8")
        rc = main([str(p)])
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_file_audit_json_format(self, tmp_path, capsys):
        p = tmp_path / "ms.txt"
        p.write_text("Result ns.\n", encoding="utf-8")
        rc = main([str(p), "--format", "json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "findings" in data

    def test_file_audit_markdown_format(self, tmp_path, capsys):
        p = tmp_path / "ms.txt"
        p.write_text("Result ns.\n", encoding="utf-8")
        rc = main([str(p), "--format", "markdown"])
        out = capsys.readouterr().out
        assert "# Statistical Audit Report" in out

    def test_missing_file_returns_2(self, capsys):
        rc = main(["nonexistent_file_xyz.txt"])
        assert rc == 2

    def test_output_file(self, tmp_path, capsys):
        ms = tmp_path / "ms.txt"
        out = tmp_path / "report.txt"
        ms.write_text("Result ns.\n", encoding="utf-8")
        rc = main([str(ms), "--output", str(out)])
        assert out.exists()
        assert "pvalue_ns" in out.read_text()

    def test_severity_filter_cli(self, tmp_path, capsys):
        p = tmp_path / "ms.txt"
        p.write_text("Result ns.\n", encoding="utf-8")
        rc_info = main([str(p), "--severity", "INFO"])
        rc_err  = main([str(p), "--severity", "ERROR"])
        # INFO gives at least as many findings as ERROR
        # (we just verify both exit cleanly)
        assert rc_info in (0, 1)
        assert rc_err in (0, 1)

    def test_strict_flag_returns_1_for_warnings(self, tmp_path):
        p = tmp_path / "ms.txt"
        p.write_text("Result ns.\n", encoding="utf-8")
        rc = main([str(p), "--strict"])
        assert rc == 1

    def test_clean_text_returns_0(self, tmp_path):
        p = tmp_path / "ms.txt"
        p.write_text("The weather was pleasant.\n", encoding="utf-8")
        rc = main([str(p)])
        assert rc == 0

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Regression / edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_multiple_findings_same_sentence(self):
        text = "The result was significant (ns, t = 2.3, p = 0.034)."
        findings = audit_text(text)
        rules = _rules(findings)
        # Should trigger nhst_only, pvalue_ns, t_test_df_missing, apa_p_format
        assert "pvalue_ns" in rules
        assert "t_test_df_missing" in rules
        assert "apa_p_format" in rules

    def test_unicode_text(self):
        text = "Die Ergebnisse waren signifikant (p = .034, η² = .12)."
        findings = audit_text(text)
        # Should not crash on Unicode
        assert isinstance(findings, list)

    def test_long_text_performance(self):
        sentence = "The result was significant (p = .034). "
        text = sentence * 200
        findings = audit_text(text)
        assert len(findings) > 0

    def test_finding_text_is_snippet(self):
        text = "We found that the effect was significant at p = .031 level."
        findings = audit_text(text, Severity.INFO)
        pv = [f for f in findings if f.rule == "pvalue_exact"]
        assert pv
        # Snippet should be shorter than the full sentence
        assert len(pv[0].text) < len(text)
