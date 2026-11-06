from __future__ import annotations

from pathlib import Path

from core import config
from format.base import FileDescription


class TextExtractor:
    extensions = (".txt", ".md", ".rst", ".log")
    kind = "texto"

    def describe(self, path: Path) -> FileDescription:
        text = path.read_text(encoding="utf-8", errors="replace")
        return FileDescription(path=path, kind=self.kind, summary=text[: config.MAX_DESCRIPTION_CHARS])
