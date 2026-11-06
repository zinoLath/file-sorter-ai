from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core import config
from core.budget import Tokenizer


@dataclass(frozen=True)
class ChoiceRequest:
    state: dict[str, object]
    instructions: str
    criteria: dict[str, str]


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    probabilities: dict[str, float]
    max_probability: float


class ChoiceBackend(Protocol):
    def predict_choices(self, requests: list[ChoiceRequest]) -> list[ChoiceAnswer]: ...


class LogitsEngine(Protocol):
    tokenizer: object

    def logits(self, rows: list[dict[str, object]]) -> list[list[float]]: ...


def softmax(logits: list[float]) -> list[float]:
    if not logits:
        return []
    maximum = max(logits)
    exps = [math.exp(value - maximum) for value in logits]
    total = sum(exps)
    return [value / total for value in exps]


class ModelBackend:
    def __init__(
        self,
        model_id: str = config.MODEL_ID,
        model_path: str | Path | None = None,
        revision: str | None = None,
        engine: LogitsEngine | None = None,
        device: str = "cpu",
        max_length: int = config.MAX_CONTEXT_TOKENS,
        head_length: int = config.HEAD_TOKENS,
        strict_encoding: bool = True,
        batch_size: int = config.BATCH_SIZE,
    ) -> None:
        self.model_id = model_id
        self.model_path = Path(model_path) if model_path is not None else config.default_model_path()
        self.revision = revision
        self.device = device
        self.max_length = max_length
        self.head_length = head_length
        self.strict_encoding = strict_encoding
        self.batch_size = batch_size
        self._engine = engine
        self._tokenizer: Tokenizer | None = None

    @property
    def loaded(self) -> bool:
        return self._engine is not None

    @property
    def tokenizer(self) -> Tokenizer | None:
        if self._engine is not None:
            return getattr(self._engine, "tokenizer", None)
        if self._tokenizer is not None:
            return self._tokenizer
        tokenizer_dir = self.model_path / "tokenizer"
        if not tokenizer_dir.is_dir():
            return None
        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_dir, trust_remote_code=False
            )
        except Exception:
            return None
        return self._tokenizer

    def load(self) -> LogitsEngine:
        if self._engine is not None:
            return self._engine
        weights = self.model_path / "model.safetensors"
        if not self.model_path.is_dir() or not weights.is_file():
            raise RuntimeError(
                f"modelo Julia-1 não encontrado em {self.model_path}; "
                "rode `fsort fetch-model`"
            )
        try:
            from julia import load_model
        except ImportError as error:
            raise RuntimeError(
                "runtime Julia-1 não instalado; instale o pacote `julia` do "
                "repositório baixado por `fsort fetch-model`"
            ) from error
        self._engine = load_model(
            str(self.model_path),
            device=self.device,
            backend="torch",
            strict_encoding=self.strict_encoding,
            max_length=self.max_length,
            head_length=self.head_length,
            batch_size=self.batch_size,
        )
        return self._engine

    def predict_choices(self, requests: list[ChoiceRequest]) -> list[ChoiceAnswer]:
        if not requests:
            return []
        for index, request in enumerate(requests, 1):
            self._validate(request, index)
        engine = self.load()
        answers: list[ChoiceAnswer] = []
        for start in range(0, len(requests), self.batch_size):
            chunk = requests[start : start + self.batch_size]
            rows = [
                {
                    "state": request.state,
                    "question": request.instructions,
                    "options": list(request.criteria.values()),
                    "type": "choice",
                }
                for request in chunk
            ]
            scores = engine.logits(rows)
            if len(scores) != len(chunk):
                raise ValueError(
                    f"modelo devolveu {len(scores)} respostas para {len(chunk)} linhas"
                )
            for request, row_scores in zip(chunk, scores, strict=True):
                options = list(request.criteria)
                if len(row_scores) != len(options):
                    raise ValueError(
                        f"modelo devolveu {len(row_scores)} scores para {len(options)} opções"
                    )
                probabilities = softmax([float(value) for value in row_scores])
                mapping = dict(zip(options, probabilities, strict=True))
                choice = max(mapping, key=mapping.__getitem__)
                answers.append(
                    ChoiceAnswer(
                        choice=choice,
                        probabilities=mapping,
                        max_probability=mapping[choice],
                    )
                )
        return answers

    @staticmethod
    def _validate(request: ChoiceRequest, index: int) -> None:
        options = request.criteria
        if not 2 <= len(options) <= 20:
            raise ValueError(
                f"choice {index} precisa de 2–20 opções; recebeu {len(options)}"
            )
        if any(not option.strip() for option in options):
            raise ValueError(f"choice {index} contém id de opção vazio")
        if any(not description.strip() for description in options.values()):
            raise ValueError(f"choice {index} contém descrição de opção vazia")
