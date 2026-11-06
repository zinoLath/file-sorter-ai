from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from core import config
from format.base import FileDescription

MAX_PAGES = 2
TIMEOUT_SECONDS = 20
MAX_SUMMARY_CHARS = 800
PAGE_NUMBER = re.compile(r"^\d{1,4}$")


def clean_text(text: str) -> str:
    """Colapsa o texto do PDF e remove cabeçalho/rodapé repetido.

    Cabeçalho e rodapé aparecem nas duas páginas lidas; linha idêntica repetida
    (curta) é descartada. Linhas longas ficam — são conteúdo, não moldura.
    """
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    counts = Counter(lines)
    kept = [
        line
        for line in lines
        if not PAGE_NUMBER.match(line)
        and (counts[line] == 1 or len(line) > 120)
    ]
    return " ".join(kept)


class OcrExtractor:
    """Texto de PDFs com camada de texto (pdftotext/poppler).

    Digitalizados sem camada de texto ainda dependem de OCR real — fora do
    escopo por enquanto; nesse caso o resumo cai no genérico.
    """

    extensions = (".pdf",)
    kind = "documento"

    def describe(self, path: Path) -> FileDescription:
        text = self._extract(path)
        summary = clean_text(text)
        if not summary:
            summary = f"Arquivo {path.name} (PDF sem camada de texto)"
        return FileDescription(
            path=path,
            kind=self.kind,
            summary=summary[:MAX_SUMMARY_CHARS],
        )

    def _extract(self, path: Path) -> str:
        binary = shutil.which("pdftotext")
        if binary is None:
            raise RuntimeError("pdftotext não encontrado (instale poppler)")
        completed = subprocess.run(
            [
                binary,
                "-f",
                "1",
                "-l",
                str(MAX_PAGES),
                "-enc",
                "UTF-8",
                str(path),
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "pdftotext falhou")
        return completed.stdout
