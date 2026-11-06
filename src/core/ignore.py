from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pathspec

from core import config

LOCAL_IGNORE = ".fsortignore"


@dataclass(frozen=True)
class IgnoreMatch:
    ignored: bool
    pattern: str = ""


class IgnoreMatcher:
    def __init__(self, patterns: list[str]) -> None:
        self._lines = list(patterns)
        self._spec = pathspec.GitIgnoreSpec.from_lines(self._lines)

    @classmethod
    def from_source(
        cls,
        source: str | Path,
        *,
        global_path: str | Path | None = None,
        local_name: str = LOCAL_IGNORE,
    ) -> "IgnoreMatcher":
        lines: list[str] = []
        global_file = Path(global_path) if global_path is not None else config.ignore_path()
        for path in (global_file, Path(source) / local_name):
            if path.is_file():
                lines.extend(
                    path.read_text(encoding="utf-8", errors="replace").splitlines()
                )
        lines.append(LOCAL_IGNORE)
        return cls(lines)

    def match(self, relative: str, *, is_dir: bool = False) -> IgnoreMatch:
        candidate = relative.rstrip("/") + "/" if is_dir else relative
        result = self._spec.check_file(candidate)
        if not result.include:
            return IgnoreMatch(False)
        pattern = self._spec.patterns[result.index].pattern
        return IgnoreMatch(True, pattern)
