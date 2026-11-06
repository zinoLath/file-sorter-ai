# Integrações (harnesses de descrição de arquivos)

Antes de classificar, cada arquivo passa por um **extrator** que devolve uma
`FileDescription` (resumo textual). Esse resumo entra no `state` JSON
(`arquivo`, `tipo`, `resumo`) consumido pelo
[classificador](../src/core/classifier.py).

## Extratores

| Tipo | Estado | Formatos | Código |
|---|---|---|---|
| Texto | funcional | `.txt .md .rst .log` | [src/format/text.py](../src/format/text.py) |
| Planilha | funcional | `.csv .xlsx .xls .ods` | [src/format/spreadsheet.py](../src/format/spreadsheet.py) |
| Texto de PDF | funcional (pdftotext) | `.pdf` | [src/format/ocr.py](../src/format/ocr.py) |
| Modelo visual (Florence-2) | funcional | `.png .jpg .jpeg .gif .bmp .webp .avif` | [src/format/vision.py](../src/format/vision.py) |

- Leitura de **colunas de planilhas**: cabeçalhos + primeiras linhas viram
  resumo; `.xls` legado via `xlrd`, `.xlsx` via `openpyxl`
  ([spreadsheet.py](../src/format/spreadsheet.py)).
- **Texto de PDF**: primeiras 2 páginas via `pdftotext` (poppler); linha curta
  repetida (cabeçalho/rodapé) e número de página são descartados, o texto é
  colapsado e cortado em 800 chars. PDF só de imagem (sem camada de texto) cai
  no resumo genérico — OCR de digitalizados continua pendente
  ([ocr.py](../src/format/ocr.py)).
- **Modelos visuais para imagens**: Florence-2 local
  ([vision.py](../src/format/vision.py)) roda `<DETAILED_CAPTION>` e, por
  padrão, também `<OCR>` para incluir texto visível no resumo. O modelo é lazy:
  carrega só na primeira imagem e cai no resumo genérico se as
  dependências/modelo não estiverem disponíveis.
- Florence-2 exige `transformers==4.45.2`, incompatível com o
  `transformers>=5.0,<5.1` do runtime Julia-1. Por isso o extrator usa um
  **venv isolado** (`~/.local/share/fsort/vision-venv`, criado por
  `python scripts/setup_vision_env.py`) via subprocesso persistente. Se o
  interpretador atual já for compatível, ele roda in-process.
- Formatos sem extrator → resumo "Arquivo <nome>".
- Visão: rode `python scripts/setup_vision_env.py`, baixe com
  `fsort fetch-vision` (ou `scripts/fetch_vision_model.py`) e opcionalmente
  configure `FSORT_VISION_PYTHON`, `FSORT_VISION_MODEL_PATH`,
  `FSORT_VISION_MODEL_ID`, `FSORT_VISION_DEVICE`, `FSORT_VISION_TASK`,
  `FSORT_VISION_MAX_TOKENS`, `FSORT_VISION_NUM_BEAMS`,
  `FSORT_VISION_OCR=0` e `FSORT_VISION=0`.
- Requisitos do Florence-2-base: ~2 GB de RAM em CPU, ~460 MiB de pesos e
  ~2–3 GB para o venv com torch. GPU é opcional; CPU funciona, com latência
  maior.

## Contrato

- Registro dos extratores: `EXTRACTORS` em [src/format/__init__.py](../src/format/__init__.py).
- `describe_file(path) -> FileDescription` — nunca explode: `NotImplementedError`
  e qualquer erro de leitura viram resumo genérico (`Arquivo <nome>` + tipo).
- Resumo truncado em `config.MAX_DESCRIPTION_CHARS`.

## Regra de spec viva

O mecanismo **específico** de cada chamada (biblioteca, prompt, parâmetros)
deve viver no arquivo do extrator; esta spec apenas indexa e descreve o papel
de cada um.
