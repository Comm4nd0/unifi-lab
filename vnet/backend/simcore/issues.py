"""Problem reporting shared by every analysis pass."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Severity ladder, mirroring the way the UniFi console ranks alerts."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"critical": 0, "warning": 1, "info": 2}[self.value]


@dataclass(frozen=True)
class Subject:
    """The thing an issue is about, so the UI can deep-link to it."""

    kind: str  # device | port | link | client | flow | site
    id: str
    label: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id, "label": self.label}


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    title: str
    detail: str
    subjects: tuple[Subject, ...] = ()
    recommendation: str = ""
    category: str = "general"  # stp | power | capacity | topology | config
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "category": self.category,
            "title": self.title,
            "detail": self.detail,
            "recommendation": self.recommendation,
            "subjects": [s.to_dict() for s in self.subjects],
            "meta": self.meta,
        }


def sort_issues(issues: list[Issue]) -> list[Issue]:
    """Critical first, then warnings, then info; stable within a severity."""
    return sorted(issues, key=lambda i: (i.severity.rank, i.category, i.code))
