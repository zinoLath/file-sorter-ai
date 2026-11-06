# Modelo de classificação — Julia-1

Fatos verificados na model card durante a sessão de grilling (2026-10-25):
[SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1) e
[luigidemasi/julia1](https://github.com/luigidemasi/julia1). Decisões
aplicáveis: [decisions.md](decisions.md).

## O que o Julia-1 É

- **Modelo de decisão** (`state` + `question` + 2–20 `options` → opção
  vencedora **com probabilidades**). Tipos: `choice`, `score`, `noul` (boolean).
- 144.3M parâmetros — encoder [mmBERT-small](https://huggingface.co/jhu-clsp/mmBERT-small)
  + decision head. Multilíngue.
- **NÃO é generativo**, não é chat, não é `AutoModelForMaskedLM`, não é
  pipeline do Transformers. Tem **runtime próprio**: `pip install -e ./Julia-1`
  → `load_model(...)` → `engine.predict(state=..., questions=...)`.

## Limites que são contrato do produto

| Limite | Valor | Consequência |
|---|---|---|
| Opções por choice | 2–20 | 20 pastas reais; no router com `manter`, 19 reais + manter |
| Perguntas por request | até 32 (named-questions) | batch de arquivos nativo |
| Contexto combinado | 8.192 tokens | state cabe folgado |
| Pergunta + opções | 512 tokens **combinados** | com 20 opções, ~25 tokens/opção |
| Por opção | 48 tokens (teto) | teto isolado; não reserva 48 para cada uma |

O teto de 48 é por opção; o orçamento de 512 é do conjunto. Com 20 opções a
média precisa ficar em ~25 tokens (~12–15 palavras em pt). Strict encoding
**rejeita overflow** (sem truncamento silencioso).

## Comportamento e qualidade

- `state` pode ser `str`, `dict` ou `list`; dict/list é serializado como JSON
  (`json.dumps(ensure_ascii=False)`). O `state` de arquivo é
  `{"arquivo", "tipo", "resumo"}`.
- Named-questions (`predict(state=..., questions=...)`) devolvem probabilidades
  completas e `max_probability`; é o caminho para várias perguntas no **mesmo**
  state. Para arquivos diferentes, use `engine.logits(rows)` + softmax próprio
  (o `predict(rows)` legado arredonda as probabilidades).
- A confiança é concentração de entropia e **não é acurácia calibrada** — desde
  A19 ela é só informativa (plano/GUI); não corta a classificação.
- Benchmarks da card: typed decisions 73,15%; choice 71,33%; MASSIVE pt
  86,25% (18 labels); **listas longas degradam** (Banking77, 72 labels com
  shortlist: 64/100).
- Router hierárquico oficial para >20 opções (agrupar → reavaliar); grupos não
  formam distribuição global — usamos a **árvore do schema** como hierarquia
  (D4/A1). Raiz com >20 filhos ou nó não-raiz com >19 é erro de schema; não
  inventamos clustering.

## Deploy

- **In-process** (D1): weights FP32 **550,5 MiB**, CPU inference (sem GPU
  necessária), threads via `JULIA_CPU_THREADS`. Container HTTP
  (luigidemasi/julia1) é alternativa descartada por ora.
- Runtime exige **Python 3.11+**; dev/CI em 3.12 (`requires-python
  >=3.11,<3.13` até smoke test em 3.13/3.14). `transformers` 5.x.
- Download explícito via `fsort fetch-model`/`scripts/fetch_model.py` para
  `~/.local/share/fsort/Julia-1`; modelo lazy na primeira classificação
  (A15). Runtime 100% local depois do download.

## Estado do código

- `core/model.py` implementa o cliente nativo: lazy load de
  `julia.load_model`, `engine.logits(rows)` em lotes de 32, softmax próprio e
  strict encoding. `fsort fetch-model` baixa o repositório completo em
  `~/.local/share/fsort/Julia-1`.
- `core/classifier.py` implementa flat (≤20 folhas) e router (>20), sem
  abstenção e sem threshold, com `trace`.
- Smoke test real (2026-10-29) em Python 3.12: `load_model`, `engine.logits` e
  softmax funcionaram em CPU com os pesos reais. Antes de A19, o eval sintético
  de 8 pastas (400 casos) dava 56,8% com threshold 0.80; sem abstenção, o
  argmax subiu para 95,0% (e 60,0% no local) — números em
  [evals/README.md](../evals/README.md). `pyproject.toml` reflete
  `>=3.11,<3.13`, `pathspec` e runtime `julia` instalado à parte.
