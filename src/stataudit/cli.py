"""Command-line interface for stataudit."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import audit_file, audit_text
from .models import Severity
from .report import AuditReport
from .rules import _RULES


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description=(
            "Audit statistical reporting in academic manuscripts.\n"
            "Reads from FILE (or stdin) and reports issues with p-values,\n"
            "confidence intervals, effect sizes, degrees of freedom, and more."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        metavar="FILE",
        help="Text file to audit (omit to read from stdin or launch GUI).",
    )
    p.add_argument(
        "--format", "-f",
        choices=["text", "markdown", "json", "html"],
        default="text",
        help="Output format (default: text).",
    )
    p.add_argument(
        "--severity", "-s",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity level to report (default: INFO).",
    )
    p.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write report to FILE instead of stdout.",
    )
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="Print all detection rules and exit.",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch the web-based graphical interface.",
    )
    return p


def main(argv=None) -> int:
    """Entry point for the ``stataudit`` CLI command."""
    args = _build_parser().parse_args(argv)

    if args.gui:
        from .gui import launch
        launch()
        return 0

    if args.list_rules:
        for name, _, sev, suggestion in _RULES:
            print(f"{name:35s}  [{sev.value:7s}]  {suggestion}")
        return 0

    min_sev = Severity(args.severity)

    if args.input:
        path = Path(args.input)
        if not path.is_file():
            print(f"stataudit: error: file not found: {args.input}", file=sys.stderr)
            return 1
        report = AuditReport(source=str(path), findings=audit_file(path, min_sev))
    else:
        if sys.stdin.isatty() and not args.input:
            # Interactive terminal with no file: open the GUI
            from .gui import launch
            launch()
            return 0
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    fmt = args.format
    if fmt == "json":
        output = report.to_json()
    elif fmt == "markdown":
        output = report.to_markdown()
    elif fmt == "html":
        output = report.to_html()
    else:
        output = report.to_text()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0


# Alias used by the legacy entry-point in pyproject.toml
_cli = main
