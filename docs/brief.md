# Brief do projeto — File Sorter AI

Registro do pedido original (intenção do autor). Toda decisão de design deve ser
rastreável até este documento.

## Requisitos declarados

1. **GUI em Qt (Python)** que serve para:
   - Organizar os *targets* de cada pasta, numa estrutura **XML-like** (elementos
     com children), onde cada pasta tem sua própria **descrição** (`prompt`).
   - Rodar o **core** (que executa todas as operações de organização).

2. **Formato XML-like** — exemplo dado pelo autor:

   ```xml
   <documentos prompt="Coloque aqui todos os documentos encontrados que podem ser
   importantes, como contas, comprovantes, e etc">
     <contas prompt="Contas de água, luz, internet" />
     <comprovantes prompt="Comprovantes bancários" />
   </documentos>
   ```

3. **Core** — orquestra todos os modelos:
   - Classificação `arquivo -> pasta` usando o modelo **Julia**
     ([SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1)),
     **localmente**; considerar uma **avaliação do porte D3** (ver
     [model-julia.md](model-julia.md)).
   - Considerar a possibilidade de concentrar **todos os subprompts** no core
     (hoje eles vivem no schema XML e são combinados no
     [classificador](../src/core/classifier.py)).
   - Deve ficar **preparado para rodar calls para harnesses** com output de
     modelos: leitura de colunas de planilhas, OCR de PDFs, calls para modelos
     visuais para imagens, texto — afim de retornar uma **descrição** que
     alimentará o classificador de pasta (ver
     [integrations.md](integrations.md)).

4. **Spec viva** — o código é a spec:
   - Uma pasta de **spec broad** (como o sistema funciona como um todo,
     explicação de features e de integrações possíveis): pasta [`spec/`](../spec/README.md).
   - Os **específicos** (como funcionam as chamadas, o prompt, e tudo mais)
     **vivem nos arquivos de código**, sendo **indexados pela spec** em momentos
     oportunos. Ex.: "Suporte para leitura de [OCR](../src/format/ocr.py)".

5. **Integração GUI ↔ core**: os dois módulos conversam entre si (ponte em
   [src/core/api.py](../src/core/api.py)).

6. **Documentação**: todas as informações relevantes ficam nesta pasta
   (`docs/`), e o `AGENTS.md` dá o contexto para agentes de código.
