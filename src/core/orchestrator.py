from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from core import config
from core.classifier import Classification, classify_many
from core.fileops import sha256_file
from core.ignore import IgnoreMatcher
from core.model import ChoiceBackend
from core.plans import Plan, PlanEntry, SkippedEntry, utc_now
from core.schema import FolderNode
from format import describe_file

ProgressFn = Callable[[str], None]


class SortOrchestrator:
    def __init__(
        self,
        folders: list[tuple[str, str]],
        *,
        schema_path: str | Path,
        schema_sha256: str,
        roots: list[FolderNode] | None = None,
        backend: ChoiceBackend | None = None,
        target_root: str | Path | None = None,
        include_state: bool = False,
        ignore: IgnoreMatcher | None = None,
    ) -> None:
        self.folders = folders
        self.roots = roots
        self.schema_path = Path(schema_path)
        self.schema_sha256 = schema_sha256
        self.backend = backend
        self.target_root = Path(target_root) if target_root is not None else None
        self.include_state = include_state
        self.ignore = ignore

    def plan(self, source_dir: str | Path, progress: ProgressFn | None = None) -> Plan:
        source = Path(source_dir).resolve()
        if not source.is_dir():
            raise ValueError(f"origem inválida: {source}")
        target_root = (self.target_root or source).resolve()

        entries: list[PlanEntry] = []
        skipped: list[SkippedEntry] = []
        states: list[dict[str, object]] = []
        pending: list[tuple[Path, str, int]] = []
        ignore = self.ignore or IgnoreMatcher.from_source(source)

        for item in sorted(source.iterdir(), key=lambda path: path.name):
            is_symlink = item.is_symlink()
            if is_symlink:
                ignored = ignore.match(item.name)
                if ignored.ignored:
                    skipped.append(
                        SkippedEntry(
                            source=str(item), reason="ignored", detail=ignored.pattern
                        )
                    )
                else:
                    detail = self._symlink_detail(item)
                    skipped.append(
                        SkippedEntry(source=str(item), reason="symlink", detail=detail)
                    )
                continue
            if item.is_dir():
                continue
            ignored = ignore.match(item.name)
            if ignored.ignored:
                skipped.append(
                    SkippedEntry(
                        source=str(item), reason="ignored", detail=ignored.pattern
                    )
                )
                continue
            if not item.is_file():
                continue
            if progress is not None:
                progress(f"Lendo {item.name}")
            description = describe_file(item)
            state = {
                "arquivo": item.name,
                "tipo": description.kind,
                "resumo": description.summary,
            }
            states.append(state)
            pending.append((item, description.kind, item.stat().st_size))

        if progress is not None:
            progress(f"Classificando {len(states)} arquivo(s)")
        classifications = classify_many(
            states,
            self.folders,
            roots=self.roots,
            backend=self.backend,
        )
        for (item, kind, size), state, classification in zip(
            pending, states, classifications, strict=True
        ):
            entries.append(
                self._entry(item, kind, size, state, classification, target_root)
            )

        return Plan(
            id=None,
            created_at=utc_now(),
            status="planned",
            source=str(source),
            target=str(target_root),
            schema_path=str(self.schema_path.resolve()),
            schema_sha256=self.schema_sha256,
            model_id=getattr(self.backend, "model_id", config.MODEL_ID),
            model_revision=getattr(self.backend, "revision", None),
            entries=entries,
            skipped=skipped,
            result=None,
        )

    def _entry(
        self,
        item: Path,
        kind: str,
        size: int,
        state: dict[str, object],
        classification: Classification,
        target_root: Path,
    ) -> PlanEntry:
        folder = classification.target or config.FALLBACK_FOLDER
        target = target_root / folder / item.name
        return PlanEntry(
            source=str(item),
            target=str(target),
            size=size,
            sha256=sha256_file(item),
            kind=kind,
            confidence=classification.confidence,
            reason=classification.reason,
            route=[asdict(decision) for decision in classification.trace],
            state=state if self.include_state else None,
        )

    @staticmethod
    def _symlink_detail(item: Path) -> str:
        try:
            return os.readlink(item)
        except OSError:
            return "symlink"
