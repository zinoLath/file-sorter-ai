# Formato do schema (XML-like)

Define as pastas alvo da organização e o subprompt de cada uma.

## Gramática

```xml
<targets>
  <pasta prompt="descrição usada como critério de classificação">
    <subpasta prompt="..." />
  </pasta>
</targets>
```

Regras:

- A raiz pode ser `<targets>` com várias pastas de topo, **ou** um único
  elemento de pasta (nesse caso ele é a única raiz).
- O **nome da tag** é o nome da pasta; aninhamento define subpastas.
- O atributo `prompt` é a descrição da pasta — vira descrição da opção no
  classificador. **Toda pasta precisa de prompt** (inclusive pasta com filhos);
  prompt vazio é erro de schema (A8).
- Atributo `name` opcional para sobrescrever o nome da pasta quando o nome
  desejado não é válido como tag XML. O dump preserva `name` quando o nome real
  não for tag válida e sempre usa `<targets>` como raiz canônica (A8).
- Nomes são sanitizados ao editar na GUI (`sanitize_name` em
  [src/core/schema.py](../src/core/schema.py)).
- Nomes reservados `__manter__` e `_nao_classificados` são rejeitados; irmãos
  duplicados são erro.
- `validate_schema(roots)` devolve `SchemaIssue` (severidade/código/caminho);
  a GUI bloqueia o plano em erro e a CLI sai 1. `iter_folders` assume schema
  válido.

## Exemplo canônico

[schemas/example.xml](../schemas/example.xml)

## Limites práticos (orçamento de tokens)

Os prompts das pastas viram descrições de opções no modelo de decisão — com
orçamento apertado (ver [decisions.md](decisions.md), D3/D4 e
[model-julia.md](model-julia.md)):

- **512 tokens combinados** (pergunta + opções) e **48 tokens por opção** como
  teto. Com 20 opções, a média fica em ~25 tokens (~12–15 palavras em pt);
- **20 opções no máximo por choice**: 20 pastas reais; no router com
  `__manter__`, 19 reais + manter;
- overflow é **rejeitado** pelo strict encoding — a GUI avisa, nunca trunca;
- **total de folhas ≤20** → flat (só folhas são opções); **>20** → router
  hierárquico pela própria árvore (raiz → subpasta). Raiz admite até 20 filhos;
  nó não-raiz até 19 (por causa do `__manter__`). Violação é erro de schema
  (sem clustering automático).

## Parsing / serialização

Implementado em [src/core/schema.py](../src/core/schema.py):

- `parse_schema(text) -> list[FolderNode]`
- `load_schema(path) / save_schema(path, roots)`
- `validate_schema(roots) -> list[SchemaIssue]` — erros/avisos de A8
- `dump_schema(roots)` — raiz `<targets>` canônica; preserva `name` quando o
  nome real não é tag XML válida
- `iter_folders(roots) -> list[(caminho_relativo, prompt)]` — caminhos do tipo
  `documentos/contas` são os identificadores usados na classificação; assume
  schema válido.
