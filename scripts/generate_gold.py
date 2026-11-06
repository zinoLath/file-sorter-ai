from __future__ import annotations

import argparse
import json
from pathlib import Path

TARGETS: dict[str, tuple[str, str, list[str]]] = {
    "contas": (
        "pdf",
        "conta-{n}.pdf",
        [
            "Conta de luz de janeiro",
            "Conta de água do mês",
            "Fatura da internet residencial",
            "Conta de telefone celular",
            "Fatura do cartão de crédito",
            "Conta de gás encanado",
            "Boleto da assinatura de streaming",
            "Fatura do plano de saúde",
            "Conta de condomínio",
            "Fatura de energia elétrica",
        ],
    ),
    "comprovantes": (
        "pdf",
        "comprovante-{n}.pdf",
        [
            "Comprovante de PIX enviado",
            "Recibo de aluguel pago",
            "Transferência bancária realizada",
            "Comprovante de pagamento de boleto",
            "Recibo de compra no cartão",
            "Comprovante de depósito em conta",
            "Comprovante de TED",
            "Recibo de pagamento de serviço",
            "Comprovante de estorno",
            "Recibo de mensalidade",
        ],
    ),
    "contratos": (
        "pdf",
        "contrato-{n}.pdf",
        [
            "Contrato de locação assinado",
            "Termo de serviço aceito",
            "Acordo de prestação de serviços",
            "Contrato de trabalho",
            "Contrato de compra e venda",
            "Termo de confidencialidade",
            "Contrato de financiamento",
            "Termo de adesão ao plano",
            "Contrato de prestação de consultoria",
            "Acordo de parceria comercial",
        ],
    ),
    "fotos/memorias": (
        "imagem",
        "IMG_{n}.jpg",
        [
            "Foto de viagem na praia",
            "Foto de família em festa",
            "Registro de pôr do sol",
            "Foto de paisagem na montanha",
            "Foto de aniversário infantil",
            "Foto de passeio no parque",
            "Foto de casamento de amigos",
            "Foto de viagem à cidade histórica",
            "Foto de cachorro no quintal",
            "Foto de trilha na natureza",
        ],
    ),
    "fotos/memes": (
        "imagem",
        "meme-{n}.png",
        [
            "Meme de gato com legenda engraçada",
            "Reaction image de risada",
            "Figurinha de WhatsApp de anime",
            "Meme de segunda-feira",
            "Reaction image de choque",
            "Meme de programador",
            "Figurinha animada de meme",
            "Meme de política com texto",
            "Reaction image de deboche",
            "Meme antigo de fórum",
        ],
    ),
    "planilhas": (
        "planilha",
        "planilha-{n}.xlsx",
        [
            "Planilha de orçamento mensal",
            "Controle de gastos pessoais",
            "Tabela de despesas do projeto",
            "Planilha de investimentos",
            "Controle de estoque da loja",
            "Planilha de horas trabalhadas",
            "Orçamento de reforma",
            "Planilha de vendas",
            "Controle de contas a pagar",
            "Planilha de metas financeiras",
        ],
    ),
    "notas": (
        "texto",
        "notas-{n}.md",
        [
            "Anotações da reunião de equipe",
            "Lista de compras do mercado",
            "Ideias para o próximo projeto",
            "Lembretes da semana",
            "Rascunho de artigo",
            "Lista de tarefas domésticas",
            "Notas de aula",
            "Planejamento de viagem",
            "Ideias de presente",
            "Lembretes de consultas médicas",
        ],
    ),
    "outros": (
        "desconhecido",
        "arquivo-{n}.pdf",
        [
            "Manual de montagem de móvel",
            "Apostila de curso online",
            "Recado de voz transcrito",
            "Arquivo sem categoria clara",
            "Guia de instalação do aparelho",
            "Material de treinamento",
            "Receita culinária impressa",
            "Catálogo de produtos",
            "Folder de evento",
            "Material de referência técnica",
        ],
    ),
}

LOCAL_CASES: list[tuple[str, str, str, str]] = [
    ("conta", "minha-conta.pdf", "documento", "conta de energia de outubro, veio por e-mail"),
    ("conta", "fatura_setembro.pdf", "documento", "fatura do cartão, valor alto, revisar"),
    ("conta", "boleto-internet.pdf", "documento", "boleto da internet fibra 500mb"),
    ("contas", "conta_agua.txt", "texto", "conta de água e esgoto do mês passado"),
    ("contas", "luz.pdf", "documento", "conta de luz, vencimento dia 10"),
    ("contas", "telefone-fatura.pdf", "documento", "fatura do celular pós-pago"),
    ("comprovante", "pix-joao.pdf", "documento", "comprovante de pix para joao"),
    ("comprovante", "recibo_aluguel.pdf", "documento", "recibo do aluguel de setembro"),
    ("comprovante", "pagamento-boleto.png", "imagem", "print do comprovante de pagamento"),
    ("comprovante", "transferencia.pdf", "documento", "transferência feita para minha irmã"),
    ("comprovante", "deposito.pdf", "documento", "deposito em dinheiro no banco"),
    ("comprovante", "estorno-cartao.pdf", "documento", "comprovante de estorno do cartão"),
    ("contrato", "contrato_aluguel.pdf", "documento", "contrato de aluguel assinado 2026"),
    ("contrato", "termo-servico.pdf", "documento", "termo de aceite do serviço de nuvem"),
    ("contrato", "acordo.pdf", "documento", "acordo com o fornecedor, tem assinatura"),
    ("contrato", "contrato_trabalho.pdf", "documento", "contrato de trabalho novo emprego"),
    ("contrato", "nda.pdf", "documento", "termo de confidencialidade da consultoria"),
    ("contrato", "financiamento.pdf", "documento", "contrato de financiamento do carro"),
    ("print", "print_erro.png", "imagem", "print de tela com erro do sistema"),
    ("print", "captura-conversa.png", "imagem", "captura de tela da conversa no chat"),
    ("print", "screenshot-config.png", "imagem", "print da tela de configurações"),
    ("print", "tela-planilha.png", "imagem", "captura da planilha aberta no notebook"),
    ("print", "print-email.png", "imagem", "print do e-mail do cliente"),
    ("print", "mapa.png", "imagem", "captura de tela do mapa da viagem"),
    ("foto", "IMG_1234.jpg", "imagem", "foto da praia no fim de semana"),
    ("foto", "IMG_5678.jpg", "imagem", "foto da família no aniversário"),
    ("foto", "por-do-sol.jpeg", "imagem", "registro do pôr do sol no mirante"),
    ("foto", "montanha.jpg", "imagem", "paisagem da montanha na viagem"),
    ("foto", "cachorro.jpg", "imagem", "foto do cachorro brincando"),
    ("foto", "casamento.jpg", "imagem", "foto do casamento dos amigos"),
    ("planilha", "gastos.xlsx", "planilha", "planilha de gastos de outubro"),
    ("planilha", "orcamento.csv", "planilha", "orçamento da reforma da cozinha"),
    ("planilha", "horas.xlsx", "planilha", "controle de horas do projeto"),
    ("planilha", "investimentos.xlsx", "planilha", "planilha de investimentos e rendimentos"),
    ("planilha", "estoque.xlsx", "planilha", "controle de estoque da loja"),
    ("planilha", "vendas.csv", "planilha", "tabela de vendas do trimestre"),
    ("nota", "reuniao.md", "texto", "notas da reunião de planejamento"),
    ("nota", "compras.txt", "texto", "lista de compras do supermercado"),
    ("nota", "ideias.txt", "texto", "ideias para o projeto novo"),
    ("nota", "lembretes.md", "texto", "lembretes da semana, pagar contas"),
    ("nota", "aula.md", "texto", "anotações da aula de estatística"),
    ("nota", "viagem.md", "texto", "roteiro e planejamento da viagem"),
    ("outro", "manual-movel.pdf", "documento", "manual de montagem do móvel"),
    ("outro", "apostila.pdf", "documento", "apostila do curso online"),
    ("outro", "guia-instalacao.pdf", "documento", "guia de instalação do aparelho"),
    ("outro", "receita.pdf", "documento", "receita de bolo impressa"),
    ("outro", "catalogo.pdf", "documento", "catálogo de produtos da loja"),
    ("outro", "transcricao.txt", "texto", "transcrição de um recado de voz"),
    ("outro", "folder.pdf", "documento", "folder de divulgação do evento"),
    ("outro", "treinamento.pdf", "documento", "material de treinamento da equipe"),
]


def build_rows(per_target: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for target, (kind, name_pattern, summaries) in TARGETS.items():
        for index in range(per_target):
            summary = summaries[index % len(summaries)]
            suffix = index // len(summaries)
            if suffix:
                summary = f"{summary} ({suffix + 1})"
            rows.append(
                {
                    "state": {
                        "arquivo": name_pattern.format(n=index + 1),
                        "tipo": kind,
                        "resumo": summary,
                    },
                    "target": target,
                    "source": "synthetic",
                }
            )
    return rows


def build_local_rows() -> list[dict[str, object]]:
    aliases = {
        "conta": "contas",
        "contas": "contas",
        "comprovante": "comprovantes",
        "contrato": "contratos",
        "print": "outros",
        "foto": "fotos/memorias",
        "planilha": "planilhas",
        "nota": "notas",
        "outro": "outros",
    }
    return [
        {
            "state": {"arquivo": filename, "tipo": kind, "resumo": summary},
            "target": aliases[folder],
            "source": "local-fake",
        }
        for folder, filename, kind, summary in LOCAL_CASES
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"{len(rows)} casos em {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera gold sintético e local fake")
    parser.add_argument("--out", default="evals/gold.jsonl")
    parser.add_argument("--per-target", type=int, default=50)
    parser.add_argument("--local-out", default="evals/local.fake.jsonl")
    args = parser.parse_args()
    _write(Path(args.out), build_rows(args.per_target))
    if args.local_out:
        _write(Path(args.local_out), build_local_rows())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
