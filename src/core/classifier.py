from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from core import config
from core.budget import check_budget
from core.model import ChoiceAnswer, ChoiceBackend, ChoiceRequest
from core.schema import FolderNode

Reason = Literal["chosen", "no_backend"]


@dataclass(frozen=True)
class LevelDecision:
    node: str
    choice: str
    max_probability: float


@dataclass(frozen=True)
class Classification:
    target: str | None
    confidence: float
    reason: Reason
    trace: tuple[LevelDecision, ...]
    probabilities: dict[str, float] | None = None


def _request(state: dict[str, object], criteria: dict[str, str]) -> ChoiceRequest:
    return ChoiceRequest(state=state, instructions=config.INSTRUCTIONS, criteria=criteria)


def _path(parent: str, name: str) -> str:
    return f"{parent}/{name}" if parent else name


def _no_backend(states: list[dict[str, object]]) -> list[Classification]:
    return [
        Classification(target=None, confidence=0.0, reason="no_backend", trace=())
        for _ in states
    ]


def _final(
    answer: ChoiceAnswer,
    trace: tuple[LevelDecision, ...],
    *,
    target: str | None,
    reason: Reason,
    include_probabilities: bool,
) -> Classification:
    return Classification(
        target=target,
        confidence=answer.max_probability,
        reason=reason,
        trace=trace,
        probabilities=answer.probabilities if include_probabilities else None,
    )


def _flat_classify(
    states: list[dict[str, object]],
    folders: list[tuple[str, str]],
    backend: ChoiceBackend,
    include_probabilities: bool,
) -> list[Classification]:
    criteria = {path: prompt for path, prompt in folders}
    check_budget(
        config.INSTRUCTIONS,
        criteria,
        file=str(states[0].get("arquivo")) if states else None,
        tokenizer=getattr(backend, "tokenizer", None),
    )
    answers = backend.predict_choices([_request(state, criteria) for state in states])
    if len(answers) != len(states):
        raise ValueError(
            f"backend devolveu {len(answers)} respostas para {len(states)} estados"
        )

    results: list[Classification] = []
    for answer in answers:
        trace = (LevelDecision("", answer.choice, answer.max_probability),)
        if answer.choice not in criteria:
            raise ValueError(f"backend devolveu opção desconhecida: {answer.choice!r}")
        results.append(_final(
            answer, trace, target=answer.choice, reason="chosen",
            include_probabilities=include_probabilities,
        ))
    return results


@dataclass
class _RouterState:
    index: int
    state: dict[str, object]
    node: FolderNode | None
    node_path: str
    trace: list[LevelDecision] = field(default_factory=list)

    def decision(self, answer: ChoiceAnswer) -> tuple[LevelDecision, ...]:
        self.trace.append(
            LevelDecision(self.node_path, answer.choice, answer.max_probability)
        )
        return tuple(self.trace)


def _router_classify(
    states: list[dict[str, object]],
    roots: list[FolderNode],
    backend: ChoiceBackend,
    include_probabilities: bool,
) -> list[Classification]:
    active = [
        _RouterState(index=index, state=state, node=None, node_path="")
        for index, state in enumerate(states)
    ]
    results: list[Classification | None] = [None] * len(states)
    while active:
        groups: dict[str, list[_RouterState]] = {}
        for item in active:
            groups.setdefault(item.node_path, []).append(item)
        next_active: list[_RouterState] = []
        for node_path, members in groups.items():
            node = members[0].node
            children = roots if node is None else node.children
            child_by_path = {_path(node_path, child.name): child for child in children}
            criteria = {
                path: child.prompt for path, child in child_by_path.items()
            }
            if node is not None:
                criteria[config.KEEP] = config.KEEP_DESCRIPTION
            check_budget(
                config.INSTRUCTIONS,
                criteria,
                file=str(members[0].state.get("arquivo")),
                tokenizer=getattr(backend, "tokenizer", None),
            )
            answers = backend.predict_choices(
                [_request(item.state, criteria) for item in members]
            )
            if len(answers) != len(members):
                raise ValueError(
                    f"backend devolveu {len(answers)} respostas para {len(members)} estados"
                )
            for item, answer in zip(members, answers, strict=True):
                trace = item.decision(answer)
                if node is not None and answer.choice == config.KEEP:
                    results[item.index] = _final(
                        answer, trace, target=node_path, reason="chosen",
                        include_probabilities=include_probabilities,
                    )
                elif answer.choice in child_by_path:
                    child = child_by_path[answer.choice]
                    if child.children:
                        item.node = child
                        item.node_path = answer.choice
                        next_active.append(item)
                    else:
                        results[item.index] = _final(
                            answer, trace, target=answer.choice, reason="chosen",
                            include_probabilities=include_probabilities,
                        )
                else:
                    raise ValueError(
                        f"backend devolveu opção desconhecida: {answer.choice!r}"
                    )
        active = next_active
    if any(result is None for result in results):
        raise RuntimeError("router não classificou todos os estados")
    return [result for result in results if result is not None]


def classify_many(
    states: list[dict[str, object]],
    folders: list[tuple[str, str]],
    *,
    roots: list[FolderNode] | None = None,
    backend: ChoiceBackend | None = None,
    include_probabilities: bool = False,
) -> list[Classification]:
    if not states:
        return []
    if backend is None or not folders:
        return _no_backend(states)
    if len(folders) <= config.MAX_FLAT_FOLDERS:
        return _flat_classify(
            states, folders, backend, include_probabilities
        )
    if roots is None:
        raise ValueError("router hierárquico requer a árvore do schema")
    return _router_classify(
        states, roots, backend, include_probabilities
    )
