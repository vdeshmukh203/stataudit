"""
Command-line interface for stataudit.

Entry point: :func:`main`.  Install the package and run ``stataudit --help``
for usage details, or invoke programmatically via ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import _RULES, AuditReport, Severity, audit_file, audit_text


def _parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    """Build and run the argument parser.

    Parameters
    ----------
    argv:
        Argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    argparse.Namespace
        Parsed arguments: ``input``, ``format``, ``severity``,
        ``output``, ``list_rules``.
    """
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  stataudit manuscript.txt\n"
            "  stataudit manuscript.txt --format markdown -o report.md\n"
            "  stataudit --severity WARNING manuscript.txt\n"
            "  echo 'The result was significant (ns).' | stataudit\n"
        ),
    )
    p.add_argument(
        "input",
        nargs="?",
        help="Text file to audit. Reads from stdin when omitted.",
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
        metavar="FILE",
        help="Write the report to FILE instead of stdout.",
    )
    p.add_argument(
        "--list-rules",
        action="store_true",
        help="List all detection rules and exit.",
    )
    return p.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    """Run the stataudit command-line tool.

    Parameters
    ----------
    argv:
        Argument list (defaults to ``sys.argv[1:]``).  Pass an explicit
        list for programmatic or test invocation.

    Returns
    -------
    int
        Exit code: ``0`` for success (no ERROR-severity findings),
        ``1`` if any ERROR-severity finding was produced or if the input
        file cannot be read.
    """
    args = _parse_args(argv)

    if args.list_rules:
        for name, _, sev, suggestion in _RULES:
            print(f"{name:35s}  [{sev.value:7s}]  {suggestion[:60]}")
        return 0

    min_sev = Severity(args.severity)

    if args.input:
        path = Path(args.input)
        try:
            findings = audit_file(path, min_sev)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        report = AuditReport(source=str(path), findings=findings)
    else:
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    if args.format == "json":
        output = report.to_json()
    elif args.format == "markdown":
        output = report.to_markdown()
    else:
        output = report.to_text()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0
