"""Command-line interface for stataudit."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._core import RULES, Severity, audit_file, audit_text
from .report import AuditReport


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic manuscripts.",
    )
    p.add_argument(
        "input",
        nargs="?",
        help="Plain-text file to audit (omit to read from stdin).",
    )
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text).",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity to report (default: INFO).",
    )
    p.add_argument(
        "--output",
        "-o",
        help="Write report to this file instead of stdout.",
    )
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="Print all detection rules and exit.",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch the browser-based GUI.",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Entry point for the ``stataudit`` command.

    Returns
    -------
    int
        0 on success; 1 if any ERROR-severity findings are present or if an
        input file is not found.
    """
    args = _parse_args(argv)

    if args.gui:
        from .gui import launch
        launch()
        return 0

    if args.list_rules:
        for name, _, sev, suggestion in RULES:
            print(f"{name:35s}  [{sev.value:7s}]  {suggestion[:60]}")
        return 0

    min_sev = Severity(args.severity)

    if args.input:
        path = Path(args.input)
        if not path.is_file():
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            return 1
        report = AuditReport(source=str(path), findings=audit_file(path, min_sev))
    else:
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    formatters = {
        "json": report.to_json,
        "markdown": report.to_markdown,
        "text": report.to_text,
    }
    output = formatters[args.format]()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0
