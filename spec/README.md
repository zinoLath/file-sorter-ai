# Spec viva — File Sorter AI

Esta pasta é a **spec broad** do sistema: como o sistema funciona como um todo,
features e integrações possíveis. Os **detalhes específicos** (mecânica de
chamadas, prompts, parâmetros) vivem **nos arquivos de código**, e são
**indexados daqui** por links.

## Mapa da spec

- [architecture.md](architecture.md) — visão geral do sistema e fluxo de dados
- [features.md](features.md) — features implementadas e planejadas
- [integrations.md](integrations.md) — extratores/harnesses de descrição
- [classification.md](classification.md) — classificação arquivo → pasta

## Regras da spec viva

1. Específicos vivem no código; a spec **indexa** o código com links relativos.
   Ex.: "Suporte para leitura de [OCR](../src/format/ocr.py)".
2. Ao mudar comportamento, atualizar **código + spec + docs** no mesmo commit.
3. Contexto de referência do projeto: [docs/brief.md](../docs/brief.md) e
   vocabulário em [GLOSSARY.md](../GLOSSARY.md).
4. Contrato da v2: [docs/decisions.md](../docs/decisions.md) (D1–D11 + A1–A18).

## Mapa do código

| Módulo | Papel |
|---|---|
| [src/gui](../src/gui/app.py) | GUI Qt (editor de schema XML-like + plano/apply) |
| [src/core/api.py](../src/core/api.py) | Ponte GUI ↔ core (`FileSorter`) |
| [src/core/orchestrator.py](../src/core/orchestrator.py) | Enumeração, extratores, `state`, plano |
| [src/core/classifier.py](../src/core/classifier.py) | Flat/router, `Classification` |
| [src/core/model.py](../src/core/model.py) | Cliente do runtime Julia-1 (`logits`) |
| [src/core/plans.py](../src/core/plans.py) | `Plan`/journal, ids, status |
| [src/core/fileops.py](../src/core/fileops.py) | Movimentação segura |
| [src/core/budget.py](../src/core/budget.py) | Orçamento de tokens |
| [src/core/ignore.py](../src/core/ignore.py) | `.fsortignore` + ignore global |
| [src/core/fetch.py](../src/core/fetch.py) | Download do Julia-1 |
| [src/core/eval.py](../src/core/eval.py) | Eval, confusão, confiança, sweep |
| [src/core/cli.py](../src/core/cli.py) | CLI `fsort` |
| [src/core/schema.py](../src/core/schema.py) | Parse/serialização/validação do schema |
| [src/format](../src/format/__init__.py) | Extratores (texto, planilha, OCR, visão) |
