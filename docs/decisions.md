# Decisões — sessões de grilling (2026-10-25 e 2026-10-29)

Registro completo das sessões de stress-test do design. Este documento é o
**contrato da próxima rodada de implementação**: onde ele conflitar com código
antigo, ele vence (código superseded está sinalizado abaixo).

- **2026-10-25** — D1–D11: migração para o Julia-1 (modelo de decisão).
- **2026-10-29** — A1–A18: arquitetura da v2 (flat/router, plano/journal,
  fileops, ignore, CLI/GUI, eval). Onde A conflitar com D, **A vence**.

## O que a sessão mudou de rumo

1. A model card do Julia-1 foi **verificada** durante a sessão
   ([GitHub luigidemasi/julia1](https://github.com/luigidemasi/julia1) +
   [HuggingFace](https://huggingface.co/SupersonicLabs/Julia-1)). Descoberta
   central: **Julia-1 é um modelo de decisão (choice finito), NÃO generativo**.
   Isso invalidou o backend generativo do scaffold (`core/model.py` com
   `AutoModelForCausalLM.generate()`), aposentou o parsing de prosa
   (`match_folder`, template textual) e **dissolveu o problema de "alucinação
   de pasta"** — substituído por choice finito e orçamentos de token.
2. O batch imaginado ("várias descrições num prompt só") é **API nativa**:
   named-questions aceita até 32 perguntas por request.
3. O limite de pastas percebido pelo autor ("20 pastas por pasta") é o limite
   nativo real: **2–20 opções por choice**; listas maiores degradam acurácia
   (Banking77: 64/100 com 72 labels) e têm solução oficial: Router hierárquico.

## Decisões fechadas

### D1 — Backend in-process (runtime nativo `julia`)
`pip install -e ./Julia-1`, `load_model`/`predict`, inferência CPU. Escolhido
sobre o container HTTP (luigidemasi/julia1) por controle total do que entra e
sai e das configurações do modelo. Consequência: alinhar `pyproject.toml`
(Python 3.11+, transformers 5.x do runtime) — a máquina de dev tem Python 3.14,
testar cedo.

### D2 — Classificador: choice finito + threshold de confiança
> **Superado por A19 (2026-10-31):** o threshold e a abstenção foram removidos;
> o modelo sempre escolhe uma pasta.
- Pastas do schema viram **opções** (id = caminho, descrição = prompt). Sem
  prosa, sem matching de resposta.
- `max_probability` abaixo do threshold → `_nao_classificados`.
- Threshold **configurável na GUI, default 80%** — assumido sabendo que
  confiança não é acurácia calibrada (model card); recalibrar com o eval (D7).

### D3 — Orçamento de tokens é contrato de produto
8.192 tokens combinados; 512 para pergunta + opções; **48 tokens por opção**
(≈30–35 palavras em pt). Prompts do schema devem ser curtos; a GUI **avisa**
overflow, nunca trunca silenciosamente (strict encoding rejeita com erro).

### D4 — Pastas: 19 reais + 1 "nenhuma dessas" por nível; Router = árvore do schema
> **Superado por A19 (2026-10-31):** sem slot de abstenção; até 20 pastas reais
> por nível.
- Nativo 2–20 opções por nível; um slot é abstenção ("nenhuma dessas"), senão
  todo arquivo é forçado pra algum lugar.
- Mais de 20 pastas → router hierárquico seguindo a própria árvore (raiz →
  subpasta, 2–3 calls). Aceito: grupos não formam distribuição global.

### D5 — `state` em JSON estruturado
`{"arquivo": ..., "tipo": ..., "resumo": ...}` — extratores alimentam `resumo`.
A/B prosa vs JSON: **postergado** para quando o sistema estiver rodando.

### D6 — Batch nativo
Até 32 perguntas independentes por request → trabalho semanal do autor (ex.:
20 planilhas) resolve em poucas chamadas. Latência não é crítica no uso-alvo.

### D7 — Avaliação (sim, precisa medir — com custo mínimo)
- Gold set = **fixtures geradas por LLM** (rótulo por construção: gera o
  arquivo já sabendo a pasta-alvo) **+ complemento com arquivos locais
  rotulados** (sintéticos são limpos demais; Downloads real é sujo).
- Abstenção (`_nao_classificados`) **conta como erro** (protocolo da card).
- Reportar: acurácia, confusão entre pastas, distribuição de confiança — é
  isso que calibra o default de 80% do D2.
- Enquanto OCR/visão forem stub, o eval desses formatos mede o **fallback**,
  não o classificador.
- Target de acurácia: definir ao criar o eval (ex.: ≥85% no gold set).

### D8 — Privacidade
Uso pessoal do autor; download inicial do HuggingFace aceito; runtime 100%
local depois disso. UX offline no primeiro uso: erro claro (a definir).

### D9 — Planos (journal de movimentação)
- Config em `~/.config/fsort/`; planos em `~/.local/state/fsort/plans/`
  (config e estado são coisas diferentes no XDG).
- **Um arquivo por plano** (CRUD fácil); **ids monotônicos** — `0007.json` é
  mais novo que `0006.json`; newest-first é *view*; `--plan 0` = maior id;
  **nunca renumerar**.
- Schema por plano: `{"id", "timestamp", "status": "applied|rolled_back",
  "entries": [{"source", "target", "size", "sha256"}]}`.
- Undo com arquivo mexido na mão pelo usuário: **skip + reportar**.

### D10 — Apply de duas fases + privilégio
1. `fsort apply` roda **sem sudo**; falhas de permissão são coletadas.
2. Relatório do que falhou → prompt de sudo, com o **uid do usuário alvo já
   conhecido** (foi ele quem rodou sem sudo).
3. Re-execução privilegiada faz **chown automático para o usuário**
   (default on; `--nochown` para opt-out).
- `sudo` é **opt-in via CLI, nunca disparado pela GUI**; nunca criar diretórios
  como root dentro da árvore do usuário.

### D11 — `core/fileops.py`: uma classe dona do disco
Move seguro (copy → verify → delete; temp + rename; **limpeza do arquivo
parcial** quando a cópia falha no meio), resolução de colisão ` (n)`, chown,
registro no journal. Testável com fakes.

## Escopo da próxima rodada (ordem proposta em 2026-10-25)

> Ordem atual: **A18** (tracer bullet). A lista abaixo fica como registro.

1. Reescrever `core/model.py` — cliente do runtime nativo (choice 2–20, batch
   de perguntas, lazy load, CPU).
2. Reescrever `core/classifier.py` — opções do schema, threshold, router
   hierárquico; aposentar prosa/matching. `core/model.py` e `core/classifier.py`
   atuais estão **legacy** (formato generativo).
3. Criar `core/fileops.py` + `core/plans.py` (D9, D11).
4. CLI `fsort apply --plan N [--nochown]` (D10).
5. GUI: menu de configurações (threshold), warning de budget de prompt (D3),
   `closeEvent` + dirty-flag.
6. `core.eval` + gerador de fixtures sintéticas + `evals/gold.jsonl` (D7).
7. Alinhar `pyproject.toml` (Python 3.11+, deps do runtime `julia`, remover
   pressuposto generativo).
8. Sync contínuo código + spec + docs (regra da spec viva do AGENTS.md).

## Não-decisions da sessão de 2026-10-25

- A/B formato do `state`: postergado (D5) — **resolvido**: JSON adotado (A10).
- UX offline no primeiro uso: a definir (D8) — **resolvido**: A15.
- Target de acurácia do eval: definir junto com o eval (D7) — **resolvido**:
  A14.

## Sessão de arquitetura (2026-10-29)

Sessão focada em evitar retrabalho: contratos de módulo, plano/journal,
classificação, ignore, CLI/GUI e eval. Onde A conflitar com D, **A vence**.

### Correções de fato (runtime Julia-1)

- `head_length=512` é o orçamento **combinado** de pergunta + opções; 48 é
  **teto por opção**. Com 19 opções, sobram ~25 tokens/opção (~12–15 palavras).
  Corrige a leitura de D3.
- `state` aceita `str`, `dict` ou `list`; dict/list é serializado com
  `json.dumps(ensure_ascii=False)`. D5 fica resolvido: **JSON**.
- Para arquivos diferentes, o caminho é `engine.logits(rows)` + softmax próprio.
  `engine.predict(rows)` arredonda probabilidades; named-questions
  (`predict(state=..., questions=...)`) é para várias perguntas no mesmo state,
  não para vários arquivos. O batch é de até 32 rows.
- Runtime exige Python 3.11+; dev/CI em 3.12; `requires-python >=3.11,<3.13`
  até smoke test em 3.13/3.14.
- `.fsortignore` usa `pathspec` (`GitWildMatchPattern`), não subset manual.

### A1 — Enumeração e topologia

- v1 é **top-level only**; arquivos ocultos entram; symlinks e diretórios são
  pulados; `--recursive` fica para depois.
- **Flat** se o total de **pastas-folha** for ≤20: só folhas são opções numa
  única chamada (A20). Pasta com filhos é agrupamento, não destino.
- **Router** se o total de folhas for >20: percorre a árvore do schema. Em cada
  nível, as opções são os filhos; se o nó atual tem prompt, inclui também
  `__manter__` ("manter nesta pasta"). Logo: raiz admite até 20 filhos; nó
  não-raiz admite até 19 filhos (19 + manter = 20). Violação é erro de schema
  (sem clustering).
- Toda pasta precisa de prompt (inclusive pasta com filhos); prompt vazio é
  erro de schema.
- ID reservado `__manter__` (e `_nao_classificados`) é rejeitado no schema.
- O modelo **sempre escolhe uma pasta** (A19): não há abstenção nem corte por
  confiança; `target=None` só existe quando não há backend.
- `_nao_classificados` é destino do plano, nunca opção do modelo.

### A2 — Orçamento de prompt

- 512 tokens combinados (pergunta + opções); 48 tokens é teto por opção.
- GUI mostra palavras + tokens; o limite duro é em tokens.
- Com tokenizer real (quando `model_path` existe), o número é exato; sem ele,
  heurística conservadora de 1,6 token/palavra, marcada como aproximada.
- `BudgetError` com arquivo/opção; strict encoding continua como rede.

### A3 — Fronteiras dos módulos

- `core/model.py` — cliente fino do runtime `julia`: lazy load, `logits` em
  lote (32), strict encoding; zero regra de negócio.
- `core/classifier.py` — puro: monta opções, flat/router, retorna
  `Classification`; não toca disco; não conhece `FALLBACK_FOLDER`.
- `core/orchestrator.py` — enumera, descreve, monta `state`, chama
  `classify_many`, monta `Plan`; não move nem grava.
- `core/plans.py` — dono do estado do app: `Plan`, `PlanEntry`, `SkippedEntry`,
  ids, status, escrita atômica, lock.
- `core/fileops.py` — dono dos arquivos do usuário: copy→verify→delete, colisão,
  hash, chown, limpeza de parcial; devolve `ApplyResult`; **não** escreve journal.
- `core/api.py` — único contrato GUI↔core (`FileSorter`).
- `core/config.py` — settings + paths XDG.

### A4 — Contrato da classificação

`Classification`:
`target: str | None`, `confidence: float`,
`reason: "chosen" | "no_backend"`,
`trace: tuple[LevelDecision, ...]` (sempre), `probabilities` só em debug/eval.

- `target=None` acontece **apenas** sem backend (`no_backend`); com backend, o
  alvo é sempre a opção vencedora (A19).
- O orchestrator decide o destino final (`_nao_classificados` no `no_backend`).
- `backend=None` retorna `no_backend` para todos.

### A5 — Ignore

- `~/.config/fsort/ignore` (global) + `.fsortignore` na raiz da origem;
  global aplica primeiro, local depois; `!` re-inclui.
- Sintaxe gitignore completa via `pathspec`; o matcher recebe caminho relativo
  + `is_dir` (pronto para `--recursive` futuro).
- `.fsortignore` nunca é movido; `.gitignore` não é lido.
- v1: diretórios não entram em `skipped`; o plano registra arquivos ignorados e
  symlinks (`reason="ignored"|"symlink"`, `detail` = padrão).
- `skipped` é persistido no plano; `apply` nunca toca neles; GUI mostra
  contagem/log.

### A6 — Modelo e batch

- `core/model.py`: `predict_choices(requests: list[ChoiceRequest]) ->
  list[ChoiceAnswer]`; chunk de 32; valida 2–20 opções; strict encoding; lazy.
- `ChoiceRequest = {state: dict, instructions: str, criteria: dict[str,str]}`.
- `ChoiceAnswer = {choice: str, probabilities: dict[str,float],
  max_probability: float}`.
- Usa `engine.logits(rows)` + softmax próprio (não `predict`, que arredonda).
- `classifier.classify_many(states, folders)` é dono do flat/router e do
  batching por nível; o orchestrator só prepara states e chama.
- Overflow/encoding estoura com arquivo+opção; nunca fallback silencioso.

### A7 — `fileops`

- Sempre copy→verify→delete, mesmo no mesmo filesystem; nada de `shutil.move`.
- Fluxo: sha256 da origem → temp `.fsort-tmp-*` no diretório de destino →
  fsync → sha256 do temp → colisão ` (n)` no apply → rename → delete da origem.
- Falha no meio remove o temp e deixa a origem intacta.
- Falha no delete registra `delete_failed`, mantém o target e reporta.
- Preserva mode+mtime (best-effort); chown só no apply privilegiado;
  `--nochown` desliga.
- `ApplyResult` (moved/failed) é devolvido; `plans` persiste.

### A8 — Schema

- `validate_schema(roots) -> list[SchemaIssue]` em `core/schema.py`, com
  severidade/código/caminho.
- Erros: nome vazio/inválido/`..`/reservado, irmãos duplicados, prompt vazio,
  nível com opções >20 (raiz: >20 filhos; não-raiz: >19 filhos).
- Avisos: orçamento de prompt, total >20 (ativa router).
- GUI bloqueia plano em erro; CLI sai 1.
- `dump_schema` sempre com `<targets>` raiz e preserva `name` quando o nome real
  não for tag XML válida.
- `iter_folders` assume schema válido.

### A9 — Journal

- Config em `~/.config/fsort/`; planos em `~/.local/state/fsort/plans/`.
- Um JSON por plano; ids `NNNN` (4 dígitos), `max+1`, nunca renumerar;
  `--plan 0` = maior id; erro claro em 9999.
- JSON com `version: 1`, timestamps UTC ISO 8601.
- Escrita atômica (temp + fsync + `os.replace` + fsync do diretório); lock
  `plans/.lock` com `fcntl.flock` (Linux v1).
- `fsort list` newest-first; `fsort forget --plan N` remove só `planned`.
- Status: `planned | partial | applied | failed | rolled_back`.
  - `applied`: nada pendente/falhou.
  - `partial`: alguns moved + alguns failed.
  - `failed`: nenhum moved e houve failure.
- `apply` permitido em `planned|partial|failed`; retenta só entradas fora de
  `result.moved` e com `retryable=true`, revalidando hash; recusa
  `applied|rolled_back`.
- `FailureRecord.retryable`: permission/IO = true; hash mismatch = false.
  Entradas não-retryable ficam reportadas e exigem novo plano.
- Plano reescrito atomicamente após cada entrada (resume/crash best-effort).
- Sudo reexecuta o mesmo `fsort apply --plan N`; usa `SUDO_UID`/`SUDO_GID`;
  chown do target **e do plano** de volta ao usuário; `--nochown` desliga.
- GUI nunca dispara sudo.
- Isso refina D9 (que só previa `applied|rolled_back`).

### A10 — Contrato do plano

`Plan`:
`version`, `id`, `created_at`, `status`, `source`, `target`, `schema_path`,
`schema_sha256`, `model_id`, `model_revision?`, `entries`,
`skipped`, `result`.

`PlanEntry`:
`source`, `target` (previsto), `size`, `sha256`, `kind`, `confidence`, `reason`,
`route: [{node, choice, max_probability}]`, `state?` (opt-in).

`SkippedEntry`: `{source, reason: "ignored"|"symlink", detail}`.

`ApplyResult`:
`{started_at, finished_at, moved: [{source, target (efetivo), size, sha256}],
failed: [{source, target, error, phase, retryable}]}`; `phase = mkdir | copy |
verify | rename | delete | chown`.

- `include_state = false` default; `--include-state`/checkbox. Quando ligado,
  `PlanEntry.state` grava o JSON exato enviado ao modelo (`arquivo`, `tipo`,
  `resumo`); sem campo `summary` duplicado.
- Não grava `resumo`/state por padrão (privacidade).
- `entries.target` é o previsto; `result.moved.target` é o efetivo após colisão.
- Rollback futuro usa `result.moved`; rollback fica fora desta rodada.
- Plano só é gravado no fim do `fsort plan` (ou no apply da GUI); falha não
  deixa plano. Plano vazio (tudo pulado) é válido.
- Schema não é copiado; `path + sha256` bastam.
- Arquivos `0600`, diretório `0700`.

### A11 — Persistência

- CLI `fsort plan` persiste por padrão; `--ephemeral` só imprime.
- GUI "Analisar" é ephemeral; "Executar" persiste o plano (id atribuído nesse
  momento) e aplica.
- `Plan.id` em memória pode ser `None`; o JSON salvo sempre tem id.
- `fsort show --plan N --json` entrega o plano completo para LLM.

### A12 — Config, precedência e CLI

- Config TOML em `~/.config/fsort/config.toml`:
  `chown = true`, `model_path = ...`, `include_state = false`.
- Precedência: CLI > env > config > default.
- `model_path`: `--model-path` > `FSORT_MODEL_PATH` > config > default.
- `--nochown` sobrescreve `chown`; `--target` default = `source`;
  `--source`/`--schema` obrigatórios no `plan`.
- Exit codes: 0 sucesso; 1 erro/falha de apply; 2 uso (argparse).
- Comandos: `fsort plan`, `apply`, `list`, `show`, `forget`, `fetch-model`,
  `eval`; `python -m core` delega para `fsort`.
- `fsort apply --plan 0` = maior id.

### A13 — GUI

- `FileSorter` expõe `plan(..., persist=False) -> Plan`,
  `apply_plan(plan) -> ApplyResult`, `apply_saved(plan_id)`, `list_plans()`,
  `show_plan(id)`, `fetch_model()`.
- Tabela: Origem, Destino, Confiança, Motivo; `route` no detalhe; pulados no
  log/aba.
- Configurações: include_state, model_path (read-only), fetch model.
- Budget warning no editor (debounce) e no plano; bloqueia em erro.
- Dirty flag + `closeEvent`; worker único; sem cancelamento na v1.
- "Executar" só para plano válido, sem sudo; falha de permissão mostra
  `sudo fsort apply --plan N`.

### A14 — Eval

- Julia-1 não é generativo: fixtures sintéticas são geradas por LLM **externo
  em tempo de desenvolvimento**, não no runtime.
- `evals/gold.jsonl` commitado; eval não chama LLM.
- Gold set: 200 sintéticos + 50 arquivos locais rotulados.
- Métricas: acurácia, matriz de confusão, distribuição de confiança.
- Metas: ≥90% sintético (sanidade), ≥70% real (utilidade).
- `core.eval` roda fora do pytest normal (`pytest -m eval` ou CLI).

### A15 — Bootstrap/offline

- Download explícito: `fsort fetch-model`/botão; `scripts/fetch_model.py` baixa
  runtime+pesos para `~/.local/share/fsort/Julia-1`.
- Modelo lazy na primeira classificação; não no startup da GUI.
- Sem `model_path` e sem rede: erro claro com o comando de fetch; sem retry
  automático.
- GUI mostra estado `não encontrado | baixando | carregando | pronto | erro`.

### A16 — Packaging

- `requires-python >=3.11,<3.13` até smoke test em 3.13/3.14; dev/CI em 3.12.
- Remover pressuposto generativo; `transformers` 5.x do runtime; `pathspec`.
- `pip install -e` do runtime `julia` via setup documentado; `FSORT_MODEL_PATH`.

### A17 — Testes

- pytest padrão sem modelo/GUI: schema, budget, ignore, plans, classifier
  (fake), orchestrator (fake), fileops (`tmp_path`).
- Integração `plan → apply` em `tmp_path` com backend fake e journal real.
- Eval marcada (`pytest -m eval` ou `python -m core.eval`), fora do CI padrão.
- GUI sem `pytest-qt`; lógica na `FileSorter`/worker; smoke manual.
- Fakes roteirizados: `FakeModel`, `FailingFileOps`.

### A18 — Ordem de implementação

1. schema → classifier flat com `FakeModel` → `Plan` → `fsort plan` em `tmp` +
   testes.
2. `fileops` + `fsort apply` em `tmp` (sem sudo) → journal.
3. modelo real (Julia) + budget + strict encoding.
4. router + ignore + `skipped`.
5. CLI final (`list`, overrides, exit codes).
6. GUI (settings, budget, dirty, apply sem sudo).
7. eval + fixtures.
8. packaging/docs/spec.

### A19 — Sem abstenção (2026-10-31)

- Removidos `__abstencao__` e o corte por threshold: o modelo sempre devolve a
  pasta vencedora (argmax); `reason` fica `chosen` (ou `no_backend`).
- Consequências: opções por nível passam a ser 20 pastas reais (router: 19 +
  `__manter__`); `DEFAULT_THRESHOLD`, `--threshold`, `FSORT_THRESHOLD`, o campo
  `threshold` do `Plan` e o sweep do eval deixam de existir.
- `_nao_classificados` continua existindo apenas como destino quando não há
  backend; nenhum arquivo é descartado por baixa confiança.
- Motivo: rodar o produto em arquivos reais sem que a maior parte caia em
  "abstenção"; a confiança vira informação no plano, não portão.

### A20 — Flat usa só pastas-folha (2026-10-31)

- No modo flat, as opções são as **pastas-folha** (`iter_leaf_folders`), não
  todos os nós. Pasta com filhos é agrupamento; oferecê-la junto dos filhos
  fazia o pai engolir as subpastas (medido: `fotos` recebia 47/50 casos de
  `fotos/memorias`).
- No router a pasta intermediária continua alcançável via `__manter__`; a
  mudança vale só para a decisão flat.
- Consequência de limite: o corte flat/router conta folhas, não nós totais.

### O que A supersede em D

- **D3** — orçamento: 512 combinado, 48 teto (não 48/opção para 19 opções).
- **D4** — topologia: flat ≤20; router >20; prompt obrigatório; `__manter__`.
  O slot de abstenção foi removido por A19.
- **D5** — `state` JSON adotado.
- **D6** — batch via `logits(rows)` (não named-questions para arquivos
  diferentes).
- **D7** — metas de eval definidas (90/70).
- **D8** — UX offline definida (fetch explícito).
- **D9** — status `planned|partial|applied|failed|rolled_back`; resume; sudo.
- **D10** — apply em duas fases com resume e chown do plano.
- **D11** — `fileops` não escreve journal; `plans` persiste.
