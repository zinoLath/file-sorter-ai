from __future__ import annotations

import csv
from pathlib import Path

from core import config
from format.base import FileDescription

PREVIEW_ROWS = 5


class SpreadsheetExtractor:
    extensions = (".csv", ".xlsx", ".xls", ".ods")
    kind = "planilha"

    def describe(self, path: Path) -> FileDescription:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            columns, rows = self._read_csv(path)
        elif suffix == ".xls":
            columns, rows = self._read_xls(path)
        else:
            columns, rows = self._read_xlsx(path)
        preview = "; ".join(",".join(row) for row in rows)
        summary = f"Planilha com colunas: {', '.join(columns)}. Primeiras linhas: {preview}"
        return FileDescription(path=path, kind=self.kind, summary=summary[: config.MAX_DESCRIPTION_CHARS])

    def _read_csv(self, path: Path) -> tuple[list[str], list[list[str]]]:
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            reader = csv.reader(handle)
            rows = [row for _, row in zip(range(PREVIEW_ROWS + 1), reader)]
        if not rows:
            return [], []
        return rows[0], rows[1:]

    def _read_xls(self, path: Path) -> tuple[list[str], list[list[str]]]:
        import xlrd

        book = xlrd.open_workbook(str(path), on_demand=True)
        try:
            sheet = book.sheet_by_index(0)
            rows = [
                [str(cell.value) if cell.value not in ("", None) else "" for cell in sheet.row(index)]
                for index in range(min(PREVIEW_ROWS + 1, sheet.nrows))
            ]
        finally:
            book.release_resources()
        if not rows:
            return [], []
        return rows[0], rows[1:]

    def _read_xlsx(self, path: Path) -> tuple[list[str], list[list[str]]]:
        from openpyxl import load_workbook

        workbook = load_workbook(path, read_only=True, data_only=True)
        rows: list[list[str]] = []
        try:
            sheet = workbook.active
            for row in sheet.iter_rows(max_row=PREVIEW_ROWS + 1, values_only=True):
                rows.append([str(cell) if cell is not None else "" for cell in row])
        finally:
            workbook.close()
        if not rows:
            return [], []
        return rows[0], rows[1:]
