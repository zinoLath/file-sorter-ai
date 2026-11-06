from __future__ import annotations

from pathlib import Path

from format.base import Extractor, FileDescription
from format.ocr import OcrExtractor
from format.spreadsheet import SpreadsheetExtractor
from format.text import TextExtractor
from format.vision import VisionExtractor

EXTRACTORS: tuple[Extractor, ...] = (
    TextExtractor(),
    SpreadsheetExtractor(),
    OcrExtractor(),
    VisionExtractor(),
)


def get_extractor(path: Path) -> Extractor | None:
    suffix = path.suffix.lower()
    for extractor in EXTRACTORS:
        if suffix in extractor.extensions:
            return extractor
    return None


def describe_file(path: Path) -> FileDescription:
    extractor = get_extractor(path)
    if extractor is None:
        return FileDescription(path=path, kind="desconhecido", summary=f"Arquivo {path.name}")
    try:
        return extractor.describe(path)
    except Exception:
        return FileDescription(
            path=path,
            kind=extractor.kind,
            summary=f"Arquivo {path.name} (extração de {extractor.kind} indisponível)",
        )
