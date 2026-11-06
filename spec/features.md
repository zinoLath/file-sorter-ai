# Features

> Contexto: o scaffold v1 foi construído antes da verificação da model card do
> Julia-1. A sessão de 2026-10-25 fechou D1–D11; a de 2026-10-29 fechou a
> arquitetura da v2 (A1–A18) — [docs/decisions.md](../docs/decisions.md).

## Implementadas (scaffold v1)

- [x] Editor de schema XML-like em árvore (nome + prompt por pasta), com
      sanitização de nomes — [src/gui/main_window.py](../src/gui/main_window.py)
- [x] Salvar/carregar schema em XML — [src/core/schema.py](../src/core/schema.py)
- [x] Execução pela GUI: plano (dry-run padrão), tabela de movimentações, log —
      [src/gui/main_window.py](../src/gui/main_window.py)
- [x] Orquestração extrair → classificar → mover, com colisão ` (n)` —
      [src/core/orchestrator.py](../src/core/orchestrator.py)
- [x] CLI headless (`python -m core`) —
      [src/core/__main__.py](../src/core/__main__.py)
- [x] Extração de texto e colunas de planilhas —
      [src/format/text.py](../src/format/text.py),
      [src/format/spreadsheet.py](../src/format/spreadsheet.py)
- [x] Backend generativo e matching de prosa removidos — substituídos por
      choice finito (`core/model.py` com tipos de choice) e classificador flat

## v2 — implementada (A18 etapas 1–8)

- [x] `core/schema.py` → `validate_schema`, prompt obrigatório, nomes
      reservados, opções ≤20 (raiz ≤20, não-raiz ≤19), dump canônico — A8
- [x] `core/classifier.py` → flat (≤20), router (>20), sem abstenção/threshold,
      `Classification` com `trace` — A1/A4/A19
- [x] `core/plans.py` → `Plan`/`PlanEntry`/`SkippedEntry`, journal, ids, status,
      escrita atômica, lock, chown do plano — A9/A10
- [x] `core/fileops.py` → copy→verify→delete, colisão no apply, chown,
      `ApplyResult` — A7
- [x] CLI `fsort plan/apply/list/show/forget/fetch-model/eval`, overrides e
      exit codes — A12
- [x] `core/model.py` → cliente do runtime nativo (`logits` em lote de 32,
      softmax, strict encoding, lazy, CPU) — A3/A6. Smoke real feito em Python
      3.12 com runtime + pesos.
- [x] `core/budget.py` → 512 combinados, 48 por opção, tokenizer exato quando
      disponível e heurística marcada como aproximada — A2
- [x] Ignore `.fsortignore` + global via `pathspec`; `skipped` de ignore e
      symlink persistido no plano — A5
- [x] Retry de failed no `apply` (revalida hash; não-retryable exige novo
      plano) — A9
- [x] Apply privilegiado: sudo com `SUDO_UID`/`SUDO_GID`, chown do target e do
      plano; `--nochown` desliga — A9/D10
- [x] GUI: settings (include_state/model_path), budget warning,
      dirty flag/closeEvent, fetch-model e apply sem sudo — A13/A15
- [x] `include_state` opt-in para planos legíveis por LLM — A10/A11
- [x] `core.eval` + 400 fixtures sintéticas em `evals/gold.jsonl` +
      `evals/local.jsonl` (50 arquivos reais rotulados, fora do git) —
      A14. Números atuais em [evals/README.md](../evals/README.md).
- [x] `scripts/fetch_model.py` + estados offline — A15
- [x] `pyproject.toml` alinhado (Python 3.11–3.12, `pathspec`,
      `huggingface_hub`, runtime `julia` instalado à parte) — A16

## Planejadas

- [ ] OCR de PDFs/TIFFs — [src/format/ocr.py](../src/format/ocr.py)
- [x] Descrição de imagens via Florence-2 local (caption + OCR) —
      [src/format/vision.py](../src/format/vision.py)
- [ ] Recursão de diretórios (`--recursive`) e `.fsortignore` por diretório —
      A1/A5
- [ ] A/B formato do `state` (JSON vs prosa) — opcional, pós-eval (D5/A10)
- [ ] Subprompts centralizados no core —
      [src/core/classifier.py](../src/core/classifier.py)
- [ ] Regras manuais/regex por pasta (atalhos antes do modelo)
- [ ] Rollback (`rolled_back`) — o journal já grava `result.moved` — A9/A10
