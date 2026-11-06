# Eval

- `schema.xml` — schema usado pelo gold set: 7 destinos, com imagens em
  `fotos/memorias`. A categoria `memes` foi removida em 2026-11-06: o caption
  do Florence descreve o conteúdo da imagem ("anime characters"), não a
  natureza de meme — que é formato/cultura, não cena — e no local da rodada
  anterior foi 0/4.
- `gold.jsonl` — 350 casos sintéticos (50 por destino), rótulo por construção.
  As fixtures são geradas por templates determinísticos
  (`scripts/generate_gold.py`); o contrato A14 prevê geração por LLM externo em
  tempo de desenvolvimento.
- `local.fake.jsonl` — 50 casos locais fake (`source=local-fake`), para smoke.
- `local.jsonl.example` — formato dos arquivos locais reais rotulados.
- `local.jsonl` — ignorado pelo git; 46 arquivos reais do usuário rotulados
  (memes removidos em 2026-11-06 junto com a categoria; sem screenshots;
  memórias só no sintético).

Rodar sem modelo real (testes):

```bash
pytest tests/test_eval.py
```

Rodar o eval real (requer runtime e pesos):

```bash
fsort eval --schema evals/schema.xml --gold evals/gold.jsonl
```

Metas: ≥90% sintético (sanidade) e ≥70% local (utilidade). O modelo não abstém
(A19); no modo flat só pastas-folha são opções (A20).

## Baseline real (CPU FP32, 2026-11-06)

Modelo `SupersonicLabs/Julia-1`, schema de 7 destinos (sem memes), sem
abstenção. Resultado determinístico entre corridas.

| conjunto | casos | acurácia |
|---|---|---|
| sintético (`gold.jsonl`) | 350 | **83,4%** (292/350) |
| local (`local.jsonl`) | 46 | **60,9%** (28/46) |

Sintético por classe:

| classe | acertos |
|---|---|
| contratos, notas, planilhas | 50/50 (100%) |
| outros | 47/50 (94%) |
| fotos/memorias | 45/50 (90%) |
| contas | 26/50 (52%) |
| comprovantes | 24/50 (48%) |

Local por classe:

| classe | acertos |
|---|---|
| planilhas | 11/11 (100%) |
| outros | 11/19 (58%) |
| notas | 5/9 (56%) |
| contratos | 1/5 (20%) |
| contas 0/1 · comprovantes 0/1 | |

Observações:

- **Não comparável 1:1 com o baseline de 2026-10-31** (95,0% sintético /
  60,0% local em 8 destinos): o conjunto de opções entra no prompt, e a
  remoção de `memes` redistribuiu decisões. `contas` caiu de 80% para 52% e
  `comprovantes` de 90% para 48% no sintético, espalhando para `outros` e
  `notas`; `contratos`, `notas` e `planilhas` seguem 100%.
- O prompt de `notas` cita os formatos (`.txt, .md`); em 2026-10-31 isso levou
  o local de 44% para 60% e o sintético de 92,8% para 95,0% no schema antigo.
  É um prior de formato: qualquer `.txt/.md` tende a `notas`.
- A meta de 90% sintético não está atingida no schema atual (83,4%): calibrar
  os prompts de `contas` e `comprovantes` é o próximo passo. A de 70% local
  também não (60,9%).
- contratos locais seguem ruins (1/5) — parte é rótulo do autor (formulários
  que não são contrato), parte é o modelo.
