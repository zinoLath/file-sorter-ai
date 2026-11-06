# File Sorter AI

Organizador de arquivos com classificação **local** por LLM. Uma GUI em
Qt edita as pastas alvo (estrutura XML-like com prompt por pasta) e roda o
core, que descreve cada arquivo (texto, planilhas e imagens) e
pergunta ao modelo [Julia-1](https://huggingface.co/SupersonicLabs/Julia-1)
em qual pasta ele se encaixa.

- Documentação: [docs/](docs/brief.md) · Decisões atuais:
  [docs/decisions.md](docs/decisions.md) · Spec viva: [spec/](spec/README.md) ·
  Guia para agentes: [AGENTS.md](AGENTS.md)

## Status

A **v2** (A18 etapas 1–8) está implementada: schema/validação, classificador
flat/router, plano/journal, `fileops`, ignore, cliente nativo do Julia-1, CLI
completa, GUI com settings e eval. O smoke test real do Julia-1 foi feito em
Python 3.12 (load + inferência + eval). O classificador **não abstém** (A19):
todo arquivo recebe a pasta mais provável. O gold sintético tem 400 casos e o
local, 50 arquivos reais rotulados (`evals/local.jsonl`, fora do git). Contrato
em [docs/decisions.md](docs/decisions.md) (A1–A20).

## Uso

```bash
pip install -e ".[dev]"
fsort fetch-model
python -m pip install -e ~/.local/share/fsort/Julia-1  # Python 3.11/3.12
python scripts/setup_vision_env.py  # opcional: descrição de imagens
fsort fetch-vision                     # opcional: Florence-2
python main.py            # GUI
```

Na GUI: abra/edite o schema (ex.: [schemas/example.xml](schemas/example.xml)),
escolha pasta de origem e raiz de destino, ajuste o modelo em
**Configurações**, clique **Analisar arquivos** (simulação por padrão) e depois
**Executar movimentações**.

CLI:

```bash
fsort plan --schema schemas/example.xml --source ~/Downloads
fsort apply --plan 0
fsort list
fsort show --plan 0 --json
fsort eval --schema evals/schema.xml --gold evals/gold.jsonl
```

A GUI “Analisar” é ephemeral; “Executar” persiste o plano e aplica sem sudo.
Falhas de permissão mostram `sudo fsort apply --plan N`. Planos ficam em
`~/.local/state/fsort/plans/`; config em `~/.config/fsort/config.toml`.
Detalhes e limites em [docs/decisions.md](docs/decisions.md) e vocabulário em
[GLOSSARY.md](GLOSSARY.md).

## Licença

Apache-2.0 — veja [LICENSE](LICENSE) e [NOTICE](NOTICE) para atribuições de
terceiros. Os modelos Julia-1 e Florence-2-base são baixados em runtime e
não são redistribuídos aqui; cada um mantém sua licença original
(Apache-2.0 e MIT, respectivamente).
