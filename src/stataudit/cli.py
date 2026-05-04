"""Command-line interface for stataudit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .auditor import RULES, audit_file, audit_text
from .report import AuditReport, Severity


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description=(
            "Audit statistical reporting in academic manuscripts.\n"
            "Pass a file path or pipe text via stdin."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        help="Text file to audit. Reads from stdin when omitted.",
    )
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json", "html"],
        default="text",
        help="Output format (default: text).",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity to include in the report (default: INFO).",
    )
    p.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write the report to FILE instead of stdout.",
    )
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="Print all detection rules with severity and exit.",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface.",
    )
    return p


def main(argv: list | None = None) -> int:
    """Entry point for the ``stataudit`` command.

    Returns
    -------
    int
        Exit code: 0 on success, 1 if any ERROR-level finding is present or
        the input file cannot be read.
    """
    args = _build_parser().parse_args(argv)

    if args.gui:
        from .gui import main as gui_main
        gui_main()
        return 0

    if args.list_rules:
        for name, _, sev, suggestion in RULES:
            print(f"{name:<35}  [{sev.value:<7}]  {suggestion}")
        return 0

    min_sev = Severity(args.severity)

    if args.input:
        path = Path(args.input)
        if not path.is_file():
            print(f"stataudit: error: file not found: {args.input}", file=sys.stderr)
            return 1
        report = AuditReport(source=str(path), findings=audit_file(path, min_sev))
    else:
        if sys.stdin.isatty():
            print(
                "stataudit: reading from stdin — pipe text or pass a file path.\n"
                "Use --help for usage information.",
                file=sys.stderr,
            )
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    formatters = {
        "text": report.to_text,
        "markdown": report.to_markdown,
        "json": report.to_json,
        "html": report.to_html,
    }
    output = formatters[args.format]()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0
