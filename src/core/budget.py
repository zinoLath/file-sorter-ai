from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from core import config

INSTRUCTION_PREFIX = "choice question: "


class Tokenizer(Protocol):
    def __call__(self, text: str, add_special_tokens: bool = False) -> Mapping[str, list[int]]: ...


class BudgetError(ValueError):
    def __init__(self, message: str, *, file: str | None = None, option: str | None = None) -> None:
        super().__init__(message)
        self.file = file
        self.option = option


@dataclass(frozen=True)
class BudgetReport:
    instruction_tokens: int
    option_tokens: dict[str, int]
    total_tokens: int
    approximate: bool
    instruction_words: int = 0
    option_words: dict[str, int] = field(default_factory=dict)
    total_words: int = 0

    @property
    def option_overflows(self) -> dict[str, int]:
        return {
            option: tokens
            for option, tokens in self.option_tokens.items()
            if tokens > config.MAX_OPTION_TOKENS
        }

    @property
    def combined_overflows(self) -> bool:
        return self.total_tokens > config.MAX_COMBINED_TOKENS

    def summary(self) -> str:
        largest = max(self.option_tokens.values(), default=0)
        kind = "aprox." if self.approximate else "exato"
        return (
            f"{self.total_words} palavras, "
            f"{self.total_tokens}/{config.MAX_COMBINED_TOKENS} tokens ({kind}); "
            f"maior opção {largest}/{config.MAX_OPTION_TOKENS}"
        )


def count_words(text: str) -> int:
    return len(text.split())


def estimate_tokens(text: str) -> int:
    words = count_words(text)
    if words == 0:
        return 0
    return math.ceil(words * config.TOKENS_PER_WORD)


def count_tokens(text: str, tokenizer: Tokenizer | None = None) -> int:
    if tokenizer is None:
        return estimate_tokens(text)
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"]
    if ids and not isinstance(ids[0], int):
        ids = ids[0]
    return len(ids)


def build_budget(
    instructions: str,
    criteria: Mapping[str, str],
    *,
    tokenizer: Tokenizer | None = None,
) -> BudgetReport:
    instruction_tokens = count_tokens(f"{INSTRUCTION_PREFIX}{instructions}", tokenizer)
    option_tokens = {
        option: count_tokens(f" {description}", tokenizer)
        for option, description in criteria.items()
    }
    option_words = {
        option: count_words(description) for option, description in criteria.items()
    }
    instruction_words = count_words(instructions)
    return BudgetReport(
        instruction_tokens=instruction_tokens,
        option_tokens=option_tokens,
        total_tokens=instruction_tokens + sum(option_tokens.values()),
        approximate=tokenizer is None,
        instruction_words=instruction_words,
        option_words=option_words,
        total_words=instruction_words + sum(option_words.values()),
    )


def check_budget(
    instructions: str,
    criteria: Mapping[str, str],
    *,
    file: str | None = None,
    tokenizer: Tokenizer | None = None,
) -> BudgetReport:
    report = build_budget(instructions, criteria, tokenizer=tokenizer)
    for option, tokens in report.option_overflows.items():
        raise BudgetError(
            f"opção {option!r} tem {tokens} tokens (teto {config.MAX_OPTION_TOKENS})",
            file=file,
            option=option,
        )
    if report.combined_overflows:
        raise BudgetError(
            f"pergunta + opções somam {report.total_tokens} tokens "
            f"(teto {config.MAX_COMBINED_TOKENS})",
            file=file,
        )
    return report
