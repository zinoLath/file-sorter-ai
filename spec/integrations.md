# Integrações (harnesses de descrição)

Cada arquivo é descrito por um extrator antes da classificação; o `resumo`
resultante entra no `state` JSON (`arquivo`, `tipo`, `resumo`) consumido pelo
[classificador](classification.md).

| Tipo | Formatos | Estado | Código |
|---|---|---|---|
| Texto | `.txt .md .rst .log` | funcional | [src/format/text.py](../src/format/text.py) |
| Leitura de colunas de planilhas | `.csv .xlsx .xls .ods` | funcional | [src/format/spreadsheet.py](../src/format/spreadsheet.py) |
| Texto de PDF | `.pdf` | funcional (pdftotext) | [src/format/ocr.py](../src/format/ocr.py) |
| Modelos visuais para imagens (Florence-2) | `.png .jpg .jpeg .gif .bmp .webp .avif` | funcional | [src/format/vision.py](../src/format/vision.py) |

Contrato dos extratores: `describe_file(path) -> FileDescription`, definido em
[src/format/base.py](../src/format/base.py) e registrado em
[src/format/__init__.py](../src/format/__init__.py).

- `describe_file` **nunca explode**: `NotImplementedError` e qualquer erro de
  leitura viram resumo genérico (`Arquivo <nome>` + tipo), para o plano não
  quebrar por extrator faltante ou arquivo ilegível.
- Formatos sem extrator → resumo `Arquivo <nome>`.
- `resumo` é truncado em `config.MAX_DESCRIPTION_CHARS`.
- PDFs com camada de texto são lidos por `pdftotext`; digitalizados sem camada de texto caem no resumo genérico (OCR real ainda pendente). Visão já descreve imagens quando o modelo está instalado/baixado.

Detalhes de implementação vivem nos arquivos de extrator; esta spec indexa.
Ver também [docs/integrations.md](../docs/integrations.md).
