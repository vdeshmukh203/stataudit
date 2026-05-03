"""Tests for stataudit — JOSS-level coverage."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

import stataudit as sa
from stataudit import AuditReport, Finding, Severity, StatAuditor, audit_text
from stataudit._core import RULES


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_module_exports_auditor(self):
        assert hasattr(sa, "StatAuditor")

    def test_module_exports_report(self):
        assert hasattr(sa, "AuditReport")

    def test_module_exports_finding(self):
        assert hasattr(sa, "Finding")

    def test_module_exports_severity(self):
        assert hasattr(sa, "Severity")

    def test_module_exports_audit_text(self):
        assert callable(sa.audit_text)

    def test_module_exports_audit_file(self):
        assert callable(sa.audit_file)

    def test_version_string(self):
        assert isinstance(sa.__version__, str)
        parts = sa.__version__.split(".")
        assert len(parts) >= 2


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------


class TestSeverity:
    def test_info_lt_warning(self):
        assert Severity.INFO < Severity.WARNING

    def test_warning_lt_error(self):
        assert Severity.WARNING < Severity.ERROR

    def test_info_lt_error(self):
        assert Severity.INFO < Severity.ERROR

    def test_equal(self):
        assert Severity.WARNING == Severity.WARNING
        assert not (Severity.WARNING < Severity.WARNING)

    def test_ge(self):
        assert Severity.ERROR >= Severity.WARNING
        assert Severity.ERROR >= Severity.ERROR


# ---------------------------------------------------------------------------
# audit_text — basic rule coverage
# ---------------------------------------------------------------------------


class TestAuditText:
    def test_empty_text_returns_empty(self):
        assert audit_text("") == []

    def test_whitespace_only(self):
        assert audit_text("   \n\t  ") == []

    def test_returns_list_of_findings(self):
        results = audit_text("The result was significant.")
        assert isinstance(results, list)
        assert all(isinstance(f, Finding) for f in results)

    # --- individual rule triggers ---

    def test_pvalue_ns_triggers(self):
        findings = audit_text("The result was ns.")
        rules = [f.rule for f in findings]
        assert "pvalue_ns" in rules

    def test_pvalue_ns_parenthesised(self):
        findings = audit_text("No difference was found (ns).")
        assert any(f.rule == "pvalue_ns" for f in findings)

    def test_pvalue_over_precision_triggers(self):
        findings = audit_text("We found p = .00001 in the analysis.")
        assert any(f.rule == "pvalue_over_precision" for f in findings)

    def test_pvalue_over_precision_not_triggered_for_p001(self):
        findings = audit_text("The result was significant (p < .001).")
        rules = [f.rule for f in findings]
        assert "pvalue_over_precision" not in rules

    def test_pvalue_exact_info_fires(self):
        findings = audit_text("We observed p = .034.")
        assert any(f.rule == "pvalue_exact" for f in findings)

    def test_ci_level_missing_triggers(self):
        findings = audit_text("The 95% CI was reported.")
        # "95% CI" — the digit follows "CI" so the warning should NOT fire
        rules = [f.rule for f in findings]
        assert "ci_level_missing" not in rules

    def test_ci_level_missing_fires_without_number(self):
        findings = audit_text("A CI was computed for the difference.")
        assert any(f.rule == "ci_level_missing" for f in findings)

    def test_t_test_df_missing_triggers(self):
        findings = audit_text("A t-test showed t = 3.21.")
        assert any(f.rule == "t_test_df_missing" for f in findings)

    def test_t_test_df_present_no_trigger(self):
        findings = audit_text("A t-test showed t(48) = 3.21.")
        rules = [f.rule for f in findings]
        assert "t_test_df_missing" not in rules

    def test_anova_missing_df_triggers(self):
        findings = audit_text("ANOVA revealed F = 9.12.")
        assert any(f.rule == "anova_missing_df" for f in findings)

    def test_anova_df_present_no_trigger(self):
        findings = audit_text("ANOVA revealed F(2, 45) = 9.12.")
        rules = [f.rule for f in findings]
        assert "anova_missing_df" not in rules

    def test_sample_size_small_triggers(self):
        findings = audit_text("Participants (N = 15) completed the task.")
        assert any(f.rule == "sample_size_small" for f in findings)

    def test_sample_size_adequate_no_trigger(self):
        findings = audit_text("Participants (N = 120) completed the task.")
        rules = [f.rule for f in findings]
        assert "sample_size_small" not in rules

    def test_over_precision_triggers(self):
        findings = audit_text("The mean was 3.141592.")
        assert any(f.rule == "over_precision" for f in findings)

    def test_one_tailed_triggers(self):
        findings = audit_text("A one-tailed test was used.")
        assert any(f.rule == "one_tailed" for f in findings)

    def test_nhst_only_triggers(self):
        findings = audit_text("The difference was significant.")
        assert any(f.rule == "nhst_only" for f in findings)

    def test_outlier_handling_triggers(self):
        findings = audit_text("Three outlier data points were removed.")
        assert any(f.rule == "outlier_handling" for f in findings)

    def test_missing_data_triggers(self):
        findings = audit_text("Missing data were imputed using MICE.")
        assert any(f.rule == "missing_data" for f in findings)

    def test_regression_r2_missing_triggers(self):
        findings = audit_text("We regressed score on age.")
        assert any(f.rule == "regression_r2_missing" for f in findings)

    def test_regression_r2_present_no_trigger(self):
        findings = audit_text("We regressed score on age (R² = .42).")
        rules = [f.rule for f in findings]
        assert "regression_r2_missing" not in rules

    def test_regression_r2_alternative_spellings(self):
        for text in [
            "We regressed score on age (R2 = .42).",
            "We regressed score on age (R^2 = .42).",
            "We regressed score on age (R-squared = .42).",
        ]:
            rules = [f.rule for f in audit_text(text)]
            assert "regression_r2_missing" not in rules, f"Triggered for: {text!r}"

    def test_multiple_comparisons_triggers(self):
        findings = audit_text("Bonferroni correction was applied.")
        assert any(f.rule == "multiple_comparisons" for f in findings)

    def test_correlation_missing_n_triggers(self):
        findings = audit_text("A strong correlation was found (r = .72).")
        assert any(f.rule == "correlation_missing_n" for f in findings)


# ---------------------------------------------------------------------------
# Severity filtering
# ---------------------------------------------------------------------------


class TestSeverityFilter:
    def test_warning_filter_excludes_info(self):
        text = "Outlier values were removed."  # outlier_handling → INFO
        findings = audit_text(text, min_severity=Severity.WARNING)
        assert all(f.severity >= Severity.WARNING for f in findings)

    def test_error_filter_excludes_warnings(self):
        text = "The result was ns and the CI was reported."
        findings = audit_text(text, min_severity=Severity.ERROR)
        assert all(f.severity == Severity.ERROR for f in findings)

    def test_info_includes_all(self):
        text = "The result was ns and outliers were removed."
        all_f = audit_text(text, min_severity=Severity.INFO)
        warn_f = audit_text(text, min_severity=Severity.WARNING)
        assert len(all_f) >= len(warn_f)


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------


class TestFinding:
    def _make(self, rule="test_rule", sev=Severity.WARNING):
        return Finding(
            rule=rule,
            text="some text",
            location="sentence 1",
            severity=sev,
            suggestion="Fix it.",
        )

    def test_to_dict_has_required_keys(self):
        d = self._make().to_dict()
        for k in ("rule", "text", "location", "severity", "suggestion"):
            assert k in d

    def test_to_dict_severity_is_string(self):
        d = self._make(sev=Severity.ERROR).to_dict()
        assert d["severity"] == "ERROR"

    def test_str_representation(self):
        s = str(self._make())
        assert "WARNING" in s
        assert "test_rule" in s
        assert "Fix it." in s


# ---------------------------------------------------------------------------
# AuditReport
# ---------------------------------------------------------------------------


class TestAuditReport:
    def _report(self) -> AuditReport:
        findings = audit_text(
            "The result was ns. A CI was computed. t = 3.21 was found."
        )
        return AuditReport(source="test_source", findings=findings)

    def test_summary_keys(self):
        r = self._report()
        s = r.summary
        assert "total" in s
        assert "by_severity" in s
        assert "source" in s

    def test_summary_counts(self):
        r = self._report()
        s = r.summary
        total = sum(s["by_severity"].values())
        assert total == s["total"]

    def test_to_json_valid(self):
        r = self._report()
        data = json.loads(r.to_json())
        assert "findings" in data
        assert "summary" in data

    def test_to_markdown_contains_headers(self):
        r = self._report()
        md = r.to_markdown()
        assert "# Statistical Audit Report" in md

    def test_to_text_non_empty(self):
        r = self._report()
        assert r.to_text().strip()

    def test_empty_report_text(self):
        r = AuditReport(source="x", findings=[])
        assert "No findings" in r.to_text()

    def test_empty_report_markdown(self):
        r = AuditReport(source="x", findings=[])
        assert "_No findings._" in r.to_markdown()

    def test_save_json(self, tmp_path):
        r = self._report()
        p = tmp_path / "out.json"
        r.save(p, fmt="json")
        data = json.loads(p.read_text())
        assert "findings" in data

    def test_save_markdown(self, tmp_path):
        r = self._report()
        p = tmp_path / "out.md"
        r.save(p, fmt="markdown")
        assert "# Statistical Audit Report" in p.read_text()

    def test_save_html(self, tmp_path):
        r = self._report()
        p = tmp_path / "out.html"
        r.save_html(p)
        html = p.read_text()
        assert "<!DOCTYPE html>" in html
        assert "stataudit" in html

    def test_save_invalid_format(self, tmp_path):
        r = self._report()
        with pytest.raises(ValueError, match="Unknown format"):
            r.save(tmp_path / "out.xyz", fmt="xyz")


# ---------------------------------------------------------------------------
# StatAuditor
# ---------------------------------------------------------------------------


class TestStatAuditor:
    def test_audit_text_input(self):
        auditor = StatAuditor("The result was ns.")
        report = auditor.run()
        assert isinstance(report, AuditReport)
        assert any(f.rule == "pvalue_ns" for f in report.findings)

    def test_audit_empty_text(self):
        report = StatAuditor("").run()
        assert report.findings == []

    def test_audit_file_input(self, tmp_path):
        p = tmp_path / "manuscript.txt"
        p.write_text("The mean was 3.141592 and it was significant.", encoding="utf-8")
        auditor = StatAuditor(p)
        report = auditor.run()
        assert len(report.findings) > 0

    def test_audit_file_path_string(self, tmp_path):
        p = tmp_path / "ms.txt"
        p.write_text("A CI was computed.", encoding="utf-8")
        auditor = StatAuditor(str(p))
        report = auditor.run()
        assert any(f.rule == "ci_level_missing" for f in report.findings)

    def test_min_severity_respected(self):
        auditor = StatAuditor(
            "Outliers were removed.", min_severity=Severity.WARNING
        )
        report = auditor.run()
        assert all(f.severity >= Severity.WARNING for f in report.findings)

    def test_label_set_for_text(self):
        report = StatAuditor("hello").run()
        assert report.source == "<text>"

    def test_label_set_for_file(self, tmp_path):
        p = tmp_path / "paper.txt"
        p.write_text("t = 3.2 found.", encoding="utf-8")
        report = StatAuditor(p).run()
        assert "paper.txt" in report.source


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------


class TestAuditFile:
    def test_line_location(self, tmp_path):
        text = textwrap.dedent("""\
            Introduction paragraph.
            We found ns results.
            Conclusion.
        """)
        p = tmp_path / "ms.txt"
        p.write_text(text, encoding="utf-8")
        findings = sa.audit_file(p)
        ns_findings = [f for f in findings if f.rule == "pvalue_ns"]
        assert ns_findings
        assert "line" in ns_findings[0].location

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            sa.audit_file(tmp_path / "missing.txt")


# ---------------------------------------------------------------------------
# RULES meta-tests
# ---------------------------------------------------------------------------


class TestRules:
    def test_all_rules_have_four_fields(self):
        for rule in RULES:
            assert len(rule) == 4, f"Rule tuple has wrong length: {rule!r}"

    def test_rule_names_unique(self):
        names = [r[0] for r in RULES]
        assert len(names) == len(set(names)), "Duplicate rule names found"

    def test_all_severities_valid(self):
        valid = {Severity.INFO, Severity.WARNING, Severity.ERROR}
        for name, _pat, sev, _sug in RULES:
            assert sev in valid, f"Invalid severity for rule {name!r}: {sev!r}"

    def test_all_suggestions_non_empty(self):
        for name, _pat, _sev, suggestion in RULES:
            assert suggestion.strip(), f"Empty suggestion for rule {name!r}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_list_rules(self, capsys):
        from stataudit.cli import main
        rc = main(["--list-rules"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_stdin_audit(self, capsys, monkeypatch):
        import io
        from stataudit.cli import main
        monkeypatch.setattr("sys.stdin", io.StringIO("The result was ns."))
        rc = main([])
        assert rc == 0  # no ERROR-level findings
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_file_audit(self, tmp_path, capsys):
        from stataudit.cli import main
        p = tmp_path / "ms.txt"
        p.write_text("The result was ns.", encoding="utf-8")
        rc = main([str(p)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_file_not_found(self, capsys):
        from stataudit.cli import main
        rc = main(["/nonexistent/file.txt"])
        assert rc == 1

    def test_json_format(self, capsys, monkeypatch):
        import io
        from stataudit.cli import main
        monkeypatch.setattr("sys.stdin", io.StringIO("t = 3.2 found."))
        rc = main(["--format", "json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "findings" in data

    def test_markdown_format(self, capsys, monkeypatch):
        import io
        from stataudit.cli import main
        monkeypatch.setattr("sys.stdin", io.StringIO("t = 3.2 found."))
        main(["--format", "markdown"])
        out = capsys.readouterr().out
        assert "# Statistical Audit Report" in out

    def test_output_file(self, tmp_path, monkeypatch, capsys):
        import io
        from stataudit.cli import main
        monkeypatch.setattr("sys.stdin", io.StringIO("t = 3.2 found."))
        out_path = tmp_path / "report.txt"
        rc = main(["--output", str(out_path)])
        assert rc == 0
        assert out_path.exists()
        assert "t_test_df_missing" in out_path.read_text()

    def test_severity_filter_warning(self, capsys, monkeypatch):
        import io
        from stataudit.cli import main
        monkeypatch.setattr(
            "sys.stdin",
            io.StringIO("Outliers were removed. The result was ns."),
        )
        main(["--severity", "WARNING"])
        out = capsys.readouterr().out
        # outlier_handling is INFO → should not appear
        assert "outlier_handling" not in out
        # pvalue_ns is WARNING → should appear
        assert "pvalue_ns" in out
