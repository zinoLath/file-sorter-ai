# File Sorter AI

Organizador pessoal de arquivos: descreve cada arquivo, decide uma pasta alvo
do schema e registra a movimentação em planos.

## Linguagem

**Pasta alvo**:
Nó do schema que pode receber arquivos e que tem um prompt próprio.
_Avoid_: target, folder, pasta de destino

**Pasta com filhos**:
Nó do schema que tem subpastas; no router, serve de passo de navegação e, por
ter prompt, também pode ser destino.
_Avoid_: grupo, categoria

**Prompt da pasta**:
Descrição de uma pasta alvo no schema, usada como critério de classificação.
_Avoid_: subprompt, descrição da pasta

**Subprompt**:
Instrução compartilhada do core que complementa os prompts das pastas.
_Avoid_: prompt da pasta

**Opção**:
Item de uma decisão de choice enviado ao modelo; pode ser uma pasta alvo ou uma
opção sintética.
_Avoid_: label, critério, alternativa

**Abstenção**:
*Removida em A19.* O modelo sempre escolhe uma pasta; não existe opção
"nenhuma dessas".
_Avoid_: fallback, não classificado

**Fallback**:
Pasta `_nao_classificados` que recebe arquivos quando não há backend; não é
opção do modelo.
_Avoid_: abstenção, erro

**Classificação**:
Resultado da decisão para um arquivo, com destino, confiança e motivo.
_Avoid_: resposta, escolha

**Confiança**:
Probabilidade máxima da opção vencedora; não é acurácia calibrada.
_Avoid_: acurácia, certeza

**Threshold**:
Limite mínimo de confiança para aceitar uma classificação.
_Avoid_: corte, limite de acurácia

**Orçamento de prompt**:
Limite de tokens do modelo para pergunta e opções de uma chamada, com teto por opção.
_Avoid_: limite de palavras, limite de caracteres

**Flat**:
Modo de classificação em que todas as pastas alvo cabem numa única chamada ao
modelo.
_Avoid_: lista plana, modo simples

**Router**:
Modo de classificação hierárquico que percorre a árvore do schema quando o
número de pastas passa do limite nativo.
_Avoid_: classificador hierárquico

**State**:
Entrada do modelo para um arquivo, composta por nome, tipo e resumo.
_Avoid_: prompt, entrada

**Resumo**:
Descrição textual produzida por um extrator para alimentar o state.
_Avoid_: prompt, descrição

**Extrator**:
Componente que produz o resumo de um tipo de arquivo.
_Avoid_: harness, modelo

**Schema**:
Árvore XML-like que define as pastas alvo e seus prompts.
_Avoid_: targets, configuração

**Origem**:
Pasta cujos arquivos serão classificados.
_Avoid_: source, entrada

**Destino**:
Pasta raiz onde as pastas alvo e o fallback são criados.
_Avoid_: target, saída

**Movimentação**:
Transferência de um arquivo da origem para uma pasta alvo.
_Avoid_: ação, move

**Pulado**:
Arquivo da origem que não entra no plano; os motivos são regra de ignore ou symlink.
_Avoid_: ignorado, excluído

**Plano**:
Registro de uma execução de organização, com as movimentações propostas e os
arquivos pulados.
_Avoid_: journal, execução

**Journal**:
Histórico de planos persistidos, identificado por ids monotônicos.
_Avoid_: plano, log

**Plan**:
Ato de gerar um plano a partir de um schema e de uma origem.
_Avoid_: analisar, classificar

**Apply**:
Ato de executar as movimentações de um plano.
_Avoid_: executar, mover
