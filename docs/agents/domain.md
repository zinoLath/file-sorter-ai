# Domain Docs

Como as skills de engenharia devem consumir a documentação de domínio deste repo ao explorar o código.

## Antes de explorar, leia

- **`GLOSSARY.md`** na raiz, ou
- **`GLOSSARY-MAP.md`** na raiz se existir: aponta um `GLOSSARY.md` por contexto. Leia os relevantes.
- **`docs/adr/`**: leia ADRs que tocam a área onde você vai trabalhar. Em repos multi-contexto, cheque também `src/<context>/docs/adr/`.

Se algum desses arquivos não existir, **siga em silêncio**. Não alardeie a ausência; não sugira criá-los de antemão. A skill `/domain-modeling` (via `/grill-with-docs` e `/improve-codebase-architecture`) cria-os sob demanda quando termos ou decisões forem resolvidos.

## Estrutura de arquivos

Repo single-context (a maioria):

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Repo multi-context (presença de `GLOSSARY-MAP.md` na raiz):

```
/
├── GLOSSARY-MAP.md
├── docs/adr/                          ← decisões do sistema
└── src/
    ├── ordering/
    │   ├── GLOSSARY.md
    │   └── docs/adr/                  ← decisões do contexto
    └── billing/
        ├── GLOSSARY.md
        └── docs/adr/
```

## Use o vocabulário do glossário

Quando sua saída nomear um conceito de domínio (título de issue, proposta de refactor, hipótese, nome de teste), use o termo definido no `GLOSSARY.md`. Não derive para sinônimos que o glossário evita.

Se o conceito ainda não estiver no glossário, isso é um sinal: ou você está inventando linguagem que o projeto não usa (reconsidere) ou há uma lacuna real (anote para `/domain-modeling`).

## Sinalize conflitos com ADR

Se sua saída contradisser um ADR existente, exponha explicitamente em vez de sobrepor em silêncio:

> _Contradiz ADR-0007 (event-sourced orders), mas vale reabrir porque…_
