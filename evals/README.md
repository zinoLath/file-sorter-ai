# Eval

- `schema.xml` — schema usado pelo gold set: 8 destinos, com a árvore de
  imagens em `fotos/memorias` e `fotos/memes` (sem `screenshots`).
- `gold.jsonl` — 400 casos sintéticos (50 por destino), rótulo por construção.
  As fixtures são geradas por templates determinísticos
  (`scripts/generate_gold.py`); o contrato A14 prevê geração por LLM externo em
  tempo de desenvolvimento.
- `local.fake.jsonl` — 50 casos locais fake (`source=local-fake`), para smoke.
- `local.jsonl.example` — formato dos arquivos locais reais rotulados.
- `local.jsonl` — ignorado pelo git; 50 arquivos reais do usuário rotulados
  (atualizado em 2026-10-31, sem screenshots; memórias só no sintético).

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

## Baseline real (CPU FP32, 2026-10-31)

Modelo `SupersonicLabs/Julia-1`, schema de 8 destinos, sem abstenção:

| conjunto | casos | acurácia |
|---|---|---|
| sintético (`gold.jsonl`) | 400 | **95,0%** (380/400) |
| local (`local.jsonl`) | 50 | **60,0%** (30/50) |

Sintético por classe:

| classe | acertos |
|---|---|
| contratos, notas, planilhas, fotos/memes, outros | 50/50 (100%) |
| comprovantes | 45/50 (90%) |
| fotos/memorias | 45/50 (90%) |
| contas | 40/50 (80%) |

Local por classe:

| classe | acertos |
|---|---|
| planilhas | 11/11 (100%) |
| outros | 13/19 (68%) |
| notas | 5/9 (56%) |
| contratos | 1/5 (20%) |
| fotos/memes | 0/4 (0%) |
| contas | 0/1 · comprovantes 0/1 |

Observações:

- O prompt de `notas` agora cita os formatos (`.txt, .md`); isso levou o local
  de 44% para 60% e o sintético de 92,8% para 95,0% (notas locais 1/9 -> 5/9,
  outros 7/19 -> 13/19). É um prior de formato: qualquer `.txt/.md` tende a
  `notas`.
- **memórias vs memes funciona no sintético** (90% e 100%), mas nos memes reais
  0/4: o caption do Florence descreve o conteúdo ("anime characters"), não a
  natureza de meme — que é formato/cultura, não cena. Sem OCR do texto overlaid
  ou sinal de nome/pasta, o modelo não tem como saber.
- `planilhas` continua 11/11 no local; `outros` (PDFs/aulas) melhorou para 68%.
- contratos locais seguem ruins (1/5) — parte é rótulo meu (formulários que não
  são contrato), parte é o modelo.
- A meta de 90% sintético foi superada (95,0%); a de 70% local ainda não (60%).
