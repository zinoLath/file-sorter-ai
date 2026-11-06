# Arquitetura

## Visão geral

```
┌────────────────────┐         ┌─────────────────────────────┐
│  GUI (PySide6)     │  API    │  Core                       │
│  editor do schema  │ ──────► │  orquestração + modelo      │
│  plano/apply       │ ◄────── │  progresso via callbacks    │
└────────────────────┘         └─────────────────────────────┘
                                        │
                                        ▼
                              ~/.config/fsort/ + plans/
```

- **GUI** ([src/gui](../src/gui/app.py)): edita o schema XML-like, salva/carrega
  XML, configura origem/destino/modelo, analisa (plano ephemeral), executa
  (persiste e aplica) em `QThread` e exibe plano/progresso/log.
- **Core**: orquestra extração, classificação, plano, journal e movimentação.

## Ponte GUI ↔ core

O único contrato entre os módulos é `FileSorter`
([src/core/api.py](../src/core/api.py)):

- `load_schema / save_schema` — schema XML-like
  ([schema.py](../src/core/schema.py))
- `plan(schema, origem, destino, persist=False) -> Plan` — não move
- `apply_plan(plan) -> ApplyResult` — persiste se necessário e move
- `apply_saved(plan_id)`, `list_plans()`, `show_plan(id)`, `fetch_model()`

A GUI nunca importa detalhes internos do core além dessa API; callbacks de
progresso (função `str -> None`) mantêm o acoplamento mínimo.

## Fluxo

```
origem ──► ignore ──► extrator ──► state ──► classificador ──► Plan
                                              (choice)          │
                                                                ▼
                                                       journal (planned/…)
                                                                │
                                                    apply (fileops) ──► disco
```

1. [orchestrator.py](../src/core/orchestrator.py) enumera a origem (top-level),
   aplica `.fsortignore`/ignore global e chama os extratores.
2. Cada arquivo vira `state` JSON (`arquivo`, `tipo`, `resumo`) — ver
   [integrations.md](integrations.md).
3. O classificador monta opções, faz flat/router e devolve `Classification`
   ([classification.md](classification.md)).
4. O orchestrator monta `Plan` (previsto, hashes, rota, `skipped`); `plans`
   persiste/atualiza o journal.
5. `fileops` executa copy→verify→delete, colisão, chown; `plans` grava o
   `ApplyResult`.

## Módulos

| Módulo | Papel |
|---|---|
| [src/core/api.py](../src/core/api.py) | Ponte GUI ↔ core (`FileSorter`) |
| [src/core/orchestrator.py](../src/core/orchestrator.py) | Enumeração, extratores, `state`, plano |
| [src/core/classifier.py](../src/core/classifier.py) | Flat/router, `Classification` |
| [src/core/model.py](../src/core/model.py) | Cliente do runtime Julia-1 (`logits` em lote) |
| [src/core/plans.py](../src/core/plans.py) | `Plan`, journal, ids, status, escrita atômica |
| [src/core/fileops.py](../src/core/fileops.py) | Movimentação segura, colisão, chown |
| [src/core/schema.py](../src/core/schema.py) | Parse/serialização/validação do schema |
| [src/core/budget.py](../src/core/budget.py) | Orçamento de tokens (512/48/8192) |
| [src/format](../src/format/__init__.py) | Extratores (texto, planilha, OCR, visão) |

## Decisões

- Modelo roda **local**, in-process ([docs/model-julia.md](../docs/model-julia.md)).
- Movimentação acontece **só após** plano; análise da GUI é ephemeral.
- CLI headless: `fsort` ([__main__.py](../src/core/__main__.py) delega).
- Contrato completo: [docs/decisions.md](../docs/decisions.md) (D1–D11 +
  A1–A18).
