"""Command-line interface for stataudit."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from ._rules import RULES
from .auditor import audit_file, audit_text
from .report import AuditReport, Severity


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  stataudit paper.txt\n"
            "  stataudit paper.txt --format markdown --severity WARNING\n"
            "  stataudit paper.txt --format html -o report.html\n"
            "  stataudit --gui\n"
            "  cat paper.txt | stataudit --format json\n"
        ),
    )
    p.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
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
        help="Minimum severity level to include (default: INFO).",
    )
    p.add_argument("--output", "-o", metavar="FILE", help="Write the report to FILE.")
    p.add_argument(
        "--list-rules", action="store_true", help="Print all detection rules and exit."
    )
    p.add_argument(
        "--gui", action="store_true", help="Launch the graphical interface."
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.gui:
        try:
            from .gui import launch
        except ImportError as exc:
            print(f"GUI unavailable: {exc}", file=sys.stderr)
            return 1
        launch()
        return 0

    if args.list_rules:
        for name, _, sev, suggestion in RULES:
            print(f"{name:<35}  [{sev.value:<7}]  {suggestion[:70]}")
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
            print("Reading from stdin… (Ctrl+D to finish)", file=sys.stderr)
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    if args.format == "json":
        output = report.to_json()
    elif args.format == "markdown":
        output = report.to_markdown()
    elif args.format == "html":
        output = report._to_html()
    else:
        output = report.to_text()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0


# Backward-compatible alias
_cli = main
