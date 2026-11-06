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
abstenção, com os prompts de `contas` e `comprovantes` calibrados. Resultado
determinístico entre corridas.

| conjunto | casos | acurácia | meta |
|---|---|---|---|
| sintético (`gold.jsonl`) | 350 | **95,7%** (335/350) | ≥90% — atingida |
| local (`local.jsonl`) | 46 | **76,1%** (35/46) | ≥70% — atingida |

Sintético por classe:

| classe | acertos |
|---|---|
| notas, planilhas, outros | 50/50 (100%) |
| contas | 49/50 (98%) |
| contratos, comprovantes, fotos/memorias | 90–92% |

Local por classe:

| classe | acertos |
|---|---|
| contas | 1/1 (100%) |
| planilhas | 10/11 (91%) |
| outros | 17/19 (89%) |
| notas | 6/9 (67%) |
| contratos | 1/5 (20%) |
| comprovantes | 0/1 (único caso local) |

Observações:

- **Remoção de `memes` e calibração de prompts**: a lista de opções entra no
  prompt do modelo, então remover uma categoria redistribui decisões. Sem
  calibração, o primeiro re-measure deu 83,4% sintético / 60,9% local
  (`contas` caiu a 52%, `comprovantes` a 36%). Calibrar os prompts de
  `contas` (boleto, fatura, condomínio) e `comprovantes` (PIX, TED, recibos de
  aluguel, cartão, mensalidade, estorno) recuperou e superou o baseline de
  2026-10-31 (95,0% sintético / 60,0% local em 8 destinos). Números entre
  schemas não são comparáveis 1:1; o estado atual é o canônico.
- **`contratos` no local segue 1/5** — parte é rótulo do autor (formulários
  que não são contrato), parte é o modelo. Candidato a revisão de rótulos no
  próximo ciclo.
- O prompt de `notas` cita os formatos (`.txt, .md`) — prior de formato:
  qualquer `.txt/.md` tende a `notas`.
