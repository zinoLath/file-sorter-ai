from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class FileDescription:
    path: Path
    kind: str
    summary: str


class Extractor(Protocol):
    extensions: tuple[str, ...]
    kind: str

    def describe(self, path: Path) -> FileDescription: ...
