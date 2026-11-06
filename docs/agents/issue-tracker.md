# Issue tracker: Markdown local

Issues e specs deste repo vivem como arquivos markdown em `.scratch/`.

## Convenções

- Uma feature por diretório: `.scratch/<feature-slug>/`
- A spec é `.scratch/<feature-slug>/spec.md`
- Issues de implementação: um arquivo por ticket em `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numerados de `01`, nunca um arquivo único combinado
- Estado de triage é uma linha `Status:` no topo de cada issue (ver `triage-labels.md`)
- Comentários e histórico append no fim do arquivo sob `## Comments`

## Quando uma skill diz "publish to the issue tracker"

Crie um arquivo em `.scratch/<feature-slug>/` (criando o diretório se preciso).

## Quando uma skill diz "fetch the relevant ticket"

Leia o arquivo no caminho indicado. O usuário normalmente passa o caminho ou o número.

## Wayfinding operations

Usado por `/wayfinder`. O **map** é um arquivo com um **child** por ticket.

- **Map**: `.scratch/<effort>/map.md` (corpo Notes / Decisions-so-far / Fog).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numerado de `01`, com a pergunta no corpo. `Type:` registra o tipo (`research`/`prototype`/`grilling`/`task`); `Status:` registra `claimed`/`resolved`.
- **Blocking**: linha `Blocked by: NN, NN` no topo. Ticket desbloqueado quando todos listados estão `resolved`.
- **Frontier**: varra `.scratch/<effort>/issues/` por arquivos abertos, desbloqueados e não reivindicados; menor número vence.
- **Claim**: defina `Status: claimed` e salve antes de trabalhar.
- **Resolve**: append da resposta sob `## Answer`, defina `Status: resolved`, e append de um ponteiro de contexto (gist + link) em Decisions-so-far no `map.md`.
