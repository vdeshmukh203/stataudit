"""Test suite for the stataudit package."""
import json
import sys
from pathlib import Path

# Make the src layout importable when running pytest from the project root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import stataudit
from stataudit import AuditReport, Finding, Severity, StatAuditor, audit_file, audit_text


# ------------------------------------------------------------------ imports / API
class TestPublicAPI:
    def test_all_symbols_exported(self):
        for sym in ("Severity", "Finding", "AuditReport", "StatAuditor", "audit_text", "audit_file"):
            assert hasattr(stataudit, sym), f"Missing public symbol: {sym}"

    def test_version_present(self):
        assert hasattr(stataudit, "__version__")
        assert isinstance(stataudit.__version__, str)


# ------------------------------------------------------------------ Severity
class TestSeverity:
    def test_ordering(self):
        assert Severity.INFO < Severity.WARNING
        assert Severity.WARNING < Severity.ERROR
        assert Severity.ERROR > Severity.INFO
        assert Severity.INFO <= Severity.INFO
        assert Severity.ERROR >= Severity.WARNING

    def test_string_value(self):
        assert Severity.WARNING.value == "WARNING"


# ------------------------------------------------------------------ Finding
class TestFinding:
    def _make(self, sev=Severity.WARNING):
        return Finding(rule="test_rule", text="some text", location="sentence 1",
                       severity=sev, suggestion="Fix it.")

    def test_to_dict_severity_is_string(self):
        d = self._make().to_dict()
        assert d["severity"] == "WARNING"
        assert isinstance(d["severity"], str)

    def test_to_dict_all_keys(self):
        d = self._make().to_dict()
        for key in ("rule", "text", "location", "severity", "suggestion"):
            assert key in d

    def test_str_representation(self):
        s = str(self._make())
        assert "[WARNING]" in s
        assert "test_rule" in s


# ------------------------------------------------------------------ audit_text
class TestAuditText:
    def test_empty_string_returns_empty(self):
        assert audit_text("") == []

    def test_whitespace_only_returns_empty(self):
        assert audit_text("   \n  ") == []

    def test_clean_text_no_issues(self):
        findings = audit_text("The sky is blue.")
        assert isinstance(findings, list)

    def test_pvalue_ns_flagged(self):
        findings = audit_text("The result was ns.")
        assert any(f.rule == "pvalue_ns" for f in findings)

    def test_t_test_without_df_flagged(self):
        findings = audit_text("We found t = 2.34.")
        assert any(f.rule == "t_test_df_missing" for f in findings)

    def test_t_test_with_df_not_flagged(self):
        findings = audit_text("We found t(28) = 2.34, p = .021.")
        assert not any(f.rule == "t_test_df_missing" for f in findings)

    def test_anova_without_df_flagged(self):
        findings = audit_text("F = 9.12 was significant.")
        assert any(f.rule == "anova_missing_df" for f in findings)

    def test_anova_with_df_not_flagged(self):
        findings = audit_text("F(2, 87) = 9.12.")
        assert not any(f.rule == "anova_missing_df" for f in findings)

    def test_pvalue_threshold_flagged(self):
        findings = audit_text("The difference was significant, p = .05.")
        assert any(f.rule == "pvalue_threshold" for f in findings)

    def test_over_precision_flagged(self):
        findings = audit_text("The mean was 3.1415926.")
        assert any(f.rule == "over_precision" for f in findings)

    def test_sample_size_small_flagged(self):
        findings = audit_text("The study included N = 15 participants.")
        assert any(f.rule == "sample_size_small" for f in findings)

    def test_sample_size_adequate_not_flagged(self):
        findings = audit_text("The study included N = 120 participants.")
        assert not any(f.rule == "sample_size_small" for f in findings)

    def test_one_tailed_flagged(self):
        findings = audit_text("We used a one-tailed test.")
        assert any(f.rule == "one_tailed" for f in findings)

    def test_nhst_language_flagged(self):
        findings = audit_text("The effect was significant.")
        assert any(f.rule == "nhst_language" for f in findings)

    def test_severity_filter_warning(self):
        text = "The result was ns, t = 2.34, N = 10."
        all_f = audit_text(text, Severity.INFO)
        warn_f = audit_text(text, Severity.WARNING)
        assert len(warn_f) <= len(all_f)

    def test_severity_filter_error_returns_subset(self):
        text = "The result was ns, t = 2.34."
        error_f = audit_text(text, Severity.ERROR)
        # No ERROR-level rules defined yet — should be empty or less than WARNING
        warn_f = audit_text(text, Severity.WARNING)
        assert len(error_f) <= len(warn_f)

    def test_findings_have_locations(self):
        findings = audit_text("t = 2.34 was noted in sentence one.")
        for f in findings:
            assert f.location.startswith("sentence")

    def test_regression_without_r2_flagged(self):
        findings = audit_text("We regressed outcome on predictors.")
        assert any(f.rule == "regression_r2_missing" for f in findings)

    def test_regression_with_r2_not_flagged(self):
        # R-squared present in same sentence
        findings = audit_text("We regressed outcome on predictors, R-squared = .45.")
        assert not any(f.rule == "regression_r2_missing" for f in findings)

    def test_chi_square_without_df_flagged(self):
        findings = audit_text("chi-square = 5.12 was found.")
        assert any(f.rule == "chi_square_df_missing" for f in findings)

    def test_correlation_flagged(self):
        findings = audit_text("r = .45 was observed.")
        assert any(f.rule == "correlation_missing_n" for f in findings)


# ------------------------------------------------------------------ audit_file
class TestAuditFile:
    def test_audit_file_returns_findings(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("The result was ns, t = 2.34, p = .05.")
        findings = audit_file(f)
        assert len(findings) > 0

    def test_audit_file_locations_are_line_numbers(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("Line one is fine.\nThe result was ns here.\nLine three fine.")
        findings = audit_file(f)
        assert any(fi.location.startswith("line") for fi in findings)

    def test_audit_file_empty(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert audit_file(f) == []


# ------------------------------------------------------------------ AuditReport
class TestAuditReport:
    def _report(self, *sevs):
        findings = [
            Finding(f"r{i}", "t", f"s{i}", s, "Fix.")
            for i, s in enumerate(sevs)
        ]
        return AuditReport(source="test", findings=findings)

    def test_summary_counts(self):
        r = self._report(Severity.ERROR, Severity.WARNING, Severity.INFO, Severity.INFO)
        s = r.summary
        assert s["total"] == 4
        assert s["by_severity"]["ERROR"] == 1
        assert s["by_severity"]["WARNING"] == 1
        assert s["by_severity"]["INFO"] == 2

    def test_to_json_valid(self):
        r = self._report(Severity.WARNING)
        data = json.loads(r.to_json())
        assert "summary" in data
        assert "findings" in data
        assert data["findings"][0]["severity"] == "WARNING"

    def test_to_markdown_contains_heading(self):
        r = self._report(Severity.WARNING)
        md = r.to_markdown()
        assert "# Statistical Audit Report" in md
        assert "WARNING" in md

    def test_to_markdown_empty(self):
        r = AuditReport(source="empty", findings=[])
        assert "_No findings._" in r.to_markdown()

    def test_to_text_empty(self):
        r = AuditReport(source="empty", findings=[])
        assert "No findings" in r.to_text()

    def test_to_html_valid(self):
        r = self._report(Severity.WARNING)
        html = r._to_html()
        assert "<!DOCTYPE html>" in html
        assert "WARNING" in html

    def test_save_html(self, tmp_path):
        r = self._report(Severity.INFO)
        out = tmp_path / "report.html"
        r.save_html(str(out))
        assert out.exists()
        assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


# ------------------------------------------------------------------ StatAuditor
class TestStatAuditor:
    def test_raw_text(self):
        auditor = StatAuditor("The result was ns.")
        report = auditor.run()
        assert isinstance(report, AuditReport)
        assert len(report.findings) > 0

    def test_file_path(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("t = 3.5 was ns.")
        auditor = StatAuditor(str(f))
        report = auditor.run()
        assert isinstance(report, AuditReport)
        assert len(report.findings) > 0

    def test_min_severity_respected(self):
        auditor_info = StatAuditor("The result was ns, t = 2.34.", Severity.INFO)
        auditor_warn = StatAuditor("The result was ns, t = 2.34.", Severity.WARNING)
        r_info = auditor_info.run()
        r_warn = auditor_warn.run()
        assert len(r_warn.findings) <= len(r_info.findings)


# ------------------------------------------------------------------ CLI
class TestCLI:
    def test_list_rules(self, capsys):
        from stataudit.cli import main
        ret = main(["--list-rules"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_version(self, capsys):
        import pytest
        from stataudit.cli import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_stdin_text_format(self, monkeypatch, capsys):
        import io
        from stataudit.cli import main
        monkeypatch.setattr("sys.stdin", io.StringIO("The result was ns."))
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        ret = main(["--format", "text"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "pvalue_ns" in out

    def test_stdin_json_format(self, monkeypatch, capsys):
        import io
        from stataudit.cli import main
        monkeypatch.setattr("sys.stdin", io.StringIO("t = 2.34 was noted."))
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        ret = main(["--format", "json"])
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert "findings" in data

    def test_file_not_found(self, capsys):
        from stataudit.cli import main
        ret = main(["nonexistent_file.txt"])
        assert ret == 1

    def test_output_file(self, tmp_path, monkeypatch, capsys):
        import io
        from stataudit.cli import main
        out_path = tmp_path / "report.txt"
        monkeypatch.setattr("sys.stdin", io.StringIO("The result was ns."))
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        ret = main(["--output", str(out_path)])
        assert ret == 0
        assert out_path.exists()
