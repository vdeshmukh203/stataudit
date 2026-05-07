"""Command-line interface for stataudit."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .auditor import audit_file, audit_text
from .report import AuditReport, Severity
from .rules import RULES


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stataudit",
        description="Audit statistical reporting in academic text.",
    )
    sub = p.add_subparsers(dest="command")

    # ---- check subcommand ------------------------------------------------
    check = sub.add_parser("check", help="Audit a file or stdin.")
    check.add_argument("input", nargs="?", help="Text file to audit (default: stdin).")
    check.add_argument(
        "--format",
        choices=["text", "markdown", "json", "html"],
        default="text",
    )
    check.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Minimum severity level to report.",
    )
    check.add_argument("--output", "-o", help="Write report to this file.")

    # ---- list-rules subcommand -------------------------------------------
    sub.add_parser("list-rules", help="List all detection rules and exit.")

    # ---- gui subcommand --------------------------------------------------
    sub.add_parser("gui", help="Launch the graphical interface.")

    # Backwards-compat: allow bare invocation without a subcommand.
    p.add_argument("_input", nargs="?", metavar="INPUT", help=argparse.SUPPRESS)
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json", "html"],
        default="text",
        dest="_format",
    )
    p.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "ERROR"],
        default="INFO",
        dest="_severity",
    )
    p.add_argument("--output", "-o", dest="_output", help=argparse.SUPPRESS)
    p.add_argument("--list-rules", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)

    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # GUI
    if args.command == "gui" or getattr(args, "gui", False):
        from .gui import run_gui
        run_gui()
        return 0

    # List rules
    if args.command == "list-rules" or getattr(args, "list_rules", False):
        for name, _, sev, suggestion in RULES:
            print(f"{name:35s}  [{sev.value}]  {suggestion[:60]}")
        return 0

    # Determine input / format / severity from subcommand or top-level flags
    if args.command == "check":
        input_path = args.input
        fmt = args.format
        min_sev = Severity(args.severity)
        out_path = args.output
    else:
        input_path = getattr(args, "_input", None)
        fmt = getattr(args, "_format", "text")
        min_sev = Severity(getattr(args, "_severity", "INFO"))
        out_path = getattr(args, "_output", None)

    if input_path:
        path = Path(input_path)
        if not path.is_file():
            print(f"Error: file not found: {input_path}", file=sys.stderr)
            return 1
        report = AuditReport(source=str(path), findings=audit_file(path, min_sev))
    else:
        if sys.stdin.isatty():
            print("stataudit: reading from stdin (Ctrl-D to finish)…", file=sys.stderr)
        text = sys.stdin.read()
        report = AuditReport(source="<stdin>", findings=audit_text(text, min_sev))

    formatters = {
        "json": report.to_json,
        "markdown": report.to_markdown,
        "html": report.to_html,
        "text": report.to_text,
    }
    output = formatters[fmt]()

    if out_path:
        Path(out_path).write_text(output, encoding="utf-8")
        print(f"Report written to {out_path}")
    else:
        print(output)

    return 1 if any(f.severity == Severity.ERROR for f in report.findings) else 0


if __name__ == "__main__":
    sys.exit(main())
