"""Core data models: Severity enum and Finding dataclass."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def _order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.value]

    def __le__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() <= other._order()

    def __lt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() < other._order()

    def __gt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() > other._order()

    def __ge__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() >= other._order()


@dataclass
class Finding:
    rule: str
    text: str
    location: str
    severity: Severity
    suggestion: str

    @property
    def message(self) -> str:
        """Alias for suggestion (for API compatibility)."""
        return self.suggestion

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    def __str__(self) -> str:
        return (
            f"[{self.severity.value}] {self.rule}\n"
            f"  Text      : {self.text!r}\n"
            f"  Location  : {self.location}\n"
            f"  Suggestion: {self.suggestion}"
        )
