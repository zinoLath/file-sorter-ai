# Classificação arquivo → pasta (choice finito)

> **Status:** flat (≤20) e router (>20), sem abstenção nem threshold,
> `Classification` com `trace`, runtime nativo do Julia-1 e strict encoding
> estão implementados em [src/core/classifier.py](../src/core/classifier.py) e
> [src/core/model.py](../src/core/model.py). O smoke test real foi feito em
> Python 3.12 (load, `logits` e softmax); falta calibrar prompts com o eval.
> Contrato completo em [docs/decisions.md](../docs/decisions.md) (A1–A6, A19).

## Como funciona (v2)

1. Cada pasta do schema tem prompt obrigatório e vira **opção** de `choice`
   (id = caminho relativo, descrição = prompt). Limite nativo 2–20 opções.
2. **Flat** quando o total de **pastas-folha** é ≤20: só as folhas são opções
   numa única chamada. Pasta com filhos é agrupamento, não destino (A20).
3. **Router** quando o total de folhas é >20: percorre a árvore do schema. Em
   cada nível:
   - opções = filhos (pasta com filhos navega; pasta folha termina);
   - `__manter__` ("manter nesta pasta") se o nó atual tem prompt.
   Raiz admite até 20 filhos; nó não-raiz até 19 (19 + manter = 20).
   Violação é erro de schema — não há clustering automático.
4. O arquivo vem de `state` (JSON: `arquivo`, `tipo`, `resumo`) — ver
   [integrations.md](integrations.md).
5. Batch de até **32 arquivos** por request; para arquivos diferentes o
   runtime é `engine.logits(rows)` + softmax próprio. Named-questions é para
   várias perguntas no mesmo `state`.
6. Resultado é uma `Classification` (`target`, `confidence`, `reason`, `trace`).
   O modelo **sempre escolhe uma pasta**; não existe opção de abstenção e a
   confiança não corta o resultado (A19).
7. `_nao_classificados` é destino do plano **apenas** quando não há backend
   (`reason="no_backend"`), **nunca** opção do modelo.

## Subprompts e orçamento

- Prompt da pasta = descrição da opção; deve ser curto. O orçamento é de
  **512 tokens combinados** (pergunta + opções) e **48 tokens por opção** como
  teto. Com 20 opções, a média fica em ~25 tokens (~12–15 palavras em pt).
- A GUI mostra palavras + tokens; o limite duro é em tokens. Sem tokenizer, usa
  heurística conservadora (1,6 token/palavra) marcada como aproximada.
- `BudgetError` identifica arquivo/opção; strict encoding rejeita overflow.
- A possibilidade de centralizar/estender subprompts no core segue planejada
  ([features.md](features.md#planejadas)).

## O que morreu do design antigo

- Template de prompt em prosa e parsing da resposta (`build_prompt`,
  `match_folder`) — removidos; choice finito **não alucina pasta**.
- `temperature`/`max_new_tokens` na config — não se aplicam ao runtime nativo.
- Fallback decidido dentro do classificador — agora é do orchestrator.
