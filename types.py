from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TranscriptionKind = Literal["partial", "final"]


@dataclass(frozen=True)
class TranscriptionEvent:
    kind: TranscriptionKind
    text: str


@dataclass(frozen=True)
class CodeToken:
    text: str
    code: str
    type: str

