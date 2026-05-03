#!/usr/bin/env python3
"""Standalone shim — delegates to the installable package at src/stataudit/.

Run directly:  python stataudit.py [args]
Or install:    pip install -e .  →  stataudit [args]
"""
import sys
from pathlib import Path

# Make the src/ package importable when running as a script
sys.path.insert(0, str(Path(__file__).parent / "src"))

from stataudit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
