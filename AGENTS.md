# AGENTS.md — contexto para agentes de código

## O projeto

**File Sorter AI** — organizador de arquivos pessoal com classificação
local por LLM. Dois módulos que conversam entre si:

1. **GUI** (Qt/PySide6, [src/gui](src/gui/app.py)): edita os *targets* —
   estrutura **XML-like** com pastas aninhadas, cada uma com um `prompt`
   (descrição) próprio — e **roda o core** por essa mesma janela.
2. **Core** ([src/core/api.py](src/core/api.py)): orquestra todos os modelos.
   Classifica `arquivo -> pasta` com o modelo de decisão **Julia-1**
   ([SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1)) —
   **choice finito, NÃO generativo** — rodando local e in-process (fatos e
   limites em [docs/model-julia.md](docs/model-julia.md)). Antes de
   classificar, arquivos passam por
   **harnesses de descrição** (leitura de colunas de planilhas, OCR de PDFs,
   modelos visuais para imagens, texto) que produzem o resumo consumido pelo
   classificador — ver [spec/integrations.md](spec/integrations.md).

Formato do schema (exemplo do autor, normalizado em
[schemas/example.xml](schemas/example.xml); detalhes em
[docs/schema-format.md](docs/schema-format.md)):

```xml
<documentos prompt="Documentos importantes como contas, comprovantes e etc">
  <contas prompt="Contas de água, luz, internet" />
  <comprovantes prompt="Comprovantes bancários" />
</documentos>
```

## Spec viva (CONVENÇÃO CENTRAL)

- `spec/` contém a spec **broad**: visão do sistema
  ([spec/architecture.md](spec/architecture.md)), features
  ([spec/features.md](spec/features.md)) e integrações possíveis.
- Os **específicos** (mecânica das chamadas, prompt, parâmetros) vivem **nos
  arquivos de código**, indexados pela spec com links relativos — ex.:
  "Suporte para leitura de [OCR](src/format/ocr.py)" em
  [spec/integrations.md](spec/integrations.md).
- **Regra**: qualquer mudança de comportamento atualiza código + spec + `docs/`
  juntos. Não deixar a spec apontando para algo que não existe.
- Contexto original do projeto: [docs/brief.md](docs/brief.md) (não editar sem
  necessidade; é o registro do pedido).
- **Decisões fechadas (2026-10-25 e 2026-10-29)**:
  [docs/decisions.md](docs/decisions.md) — **contrato da próxima rodada de
  implementação; ler antes de codar**. D1–D11 (Julia-1) + A1–A18 (arquitetura
  da v2); onde A conflitar com D, A vence. Onde a doc conflitar com código, a
  doc vence.

## Estado do código (importante)

- v2 **implementada** (A18 etapas 1–8): schema/validação, classificador
  flat/router, `plans.py`, `fileops.py`, `budget.py`, ignore via `pathspec`,
  cliente nativo do Julia-1 (`engine.logits`), CLI completa, GUI com settings,
  eval e packaging.
- Smoke test real **feito** em Python 3.12 com o runtime `julia` e os pesos
  (load + inferência + eval sintético). O eval está rodando com dados reais:
  `evals/local.jsonl` tem 50 arquivos do usuário rotulados; baseline de
  2026-10-31 sem abstenção (A19) é 95,0% sintético e 60,0% local. Falta
  calibrar prompts, visão de imagens e limpeza do resumo de PDF para chegar às
  metas de 90%/70%. Contrato em [docs/decisions.md](docs/decisions.md)
  (A1–A20, ordem A18).

## Estrutura

```
main.py              launcher da GUI (python main.py)
GLOSSARY.md          vocabulário canônico do domínio
schemas/             schemas XML-like de exemplo
spec/                spec broad (indexa o código)
docs/                brief, decisões, formato do schema, modelo, integrações
src/gui/             GUI Qt: main_window, worker (QThread), app
src/core/            api (ponte GUI↔core), orchestrator, classifier,
                     model (Julia-1), schema (XML-like), config, CLI,
                     plans, fileops, budget, ignore, fetch, eval
src/format/          extratores: text, spreadsheet, ocr (stub), vision (Florence-2)
evals/               schema, gold sintético e exemplo de gold local
scripts/             fetch_model.py, fetch_vision_model.py, setup_vision_env.py, generate_gold.py
tests/               pytest (não dependem de GUI nem do modelo)
```

## Comandos

```bash
pip install -e ".[dev]"       # deps da GUI/CLI (runtime do modelo à parte)
pytest                        # testes rápidos, sem modelo/GUI
pytest -m eval                # eval real (requer modelo; fora do CI)
python main.py                # abre a GUI
fsort fetch-model             # baixa repo runtime+pesos em ~/.local/share/fsort/Julia-1
fsort fetch-vision            # baixa Florence-2 (~460 MiB) para imagens
python -m pip install -e ~/.local/share/fsort/Julia-1  # runtime (Python 3.11/3.12)
python scripts/setup_vision_env.py  # opcional: Florence-2/visão
fsort plan --schema schemas/example.xml --source ~/Downloads
fsort apply --plan 0
fsort list                    # planos, mais novo primeiro
fsort eval --schema evals/schema.xml --gold evals/gold.jsonl
python -m core.eval --schema evals/schema.xml  # equivalente headless
python -m core ...            # delega para fsort
```

## Convenções

- Documentação, specs, prompts e mensagens de UI em **pt-BR**; identificadores
  de código em inglês.
- **Sem comentários no código** — a documentação do "porquê" morre na spec/docs
  (spec viva); docstrings apenas quando essenciais.
- Type hints em todo código novo; testes pytest para toda lógica nova.
- Modelo é **lazy** (`ModelBackend.load()`): GUI e testes não devem exigir
  download do modelo; sem backend, `classify_many` retorna `no_backend` e o
  orchestrator mapeia para `_nao_classificados` ([src/core/config.py](src/core/config.py)).
- A ponte GUI ↔ core é só [src/core/api.py](src/core/api.py) (`FileSorter`) +
  callbacks de progresso; não vazar internos do core para a GUI.
- `describe_file` **nunca explode**: `NotImplementedError` e qualquer erro de
  leitura viram resumo genérico (nunca quebrar o plano por extrator faltante).
- `fileops` é a única dona dos arquivos do usuário; `plans` é a única dona do
  estado do app; `classifier` não toca disco.
- Planos que podem conter conteúdo (`include_state`) são opt-in e `0600`.

## Agent skills

### Issue tracker

Issues e specs vivem como markdown local em `.scratch/<feature>/`. Veja `docs/agents/issue-tracker.md`.

### Triage labels

Cinco papéis canônicos, label igual ao nome: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Veja `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` na raiz e ADRs em `docs/adr/`. Veja `docs/agents/domain.md`.
