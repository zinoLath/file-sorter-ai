from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from core import config
from core.classifier import classify_many
from core.model import ChoiceBackend
from core.schema import iter_leaf_folders, parse_schema, validate_schema

TARGETS = {"synthetic": 0.90, "local": 0.70}

@dataclass(frozen=True)
class GoldCase:
    state: dict[str, object]
    target: str
    source: str = "synthetic"


@dataclass
class EvalReport:
    total: int
    correct: int
    confusion: dict[str, dict[str, int]]
    confidence_buckets: dict[str, int]
    by_source: dict[str, dict[str, float | int]] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "confusion": self.confusion,
            "confidence_buckets": self.confidence_buckets,
            "by_source": self.by_source,
        }

    def summary(self) -> str:
        lines = [f"acurácia={self.accuracy:.1%} ({self.correct}/{self.total})"]
        for source, data in sorted(self.by_source.items()):
            goal = TARGETS.get(source)
            goal_text = f" meta={goal:.0%}" if goal is not None else ""
            lines.append(
                f"  {source}: {data['accuracy']:.1%} "
                f"({data['correct']}/{data['total']}){goal_text}"
            )
        lines.append("  confiança:")
        for bucket, count in sorted(self.confidence_buckets.items()):
            lines.append(f"    {bucket}: {count}")
        lines.append("  confusão:")
        for expected, predictions in sorted(self.confusion.items()):
            for predicted, count in sorted(predictions.items()):
                lines.append(f"    {expected} -> {predicted}: {count}")
        return "\n".join(lines)


def load_gold(path: str | Path) -> list[GoldCase]:
    cases: list[GoldCase] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: JSON inválido: {error.msg}") from error
            if not isinstance(data, dict) or not isinstance(data.get("state"), dict):
                raise ValueError(f"{path}:{line_number}: state deve ser um objeto")
            if not isinstance(data.get("target"), str) or not data["target"]:
                raise ValueError(f"{path}:{line_number}: target obrigatório")
            source = str(data.get("source", "synthetic"))
            cases.append(GoldCase(state=data["state"], target=data["target"], source=source))
    if not cases:
        raise ValueError(f"{path}: gold set vazio")
    return cases


def _bucket(confidence: float) -> str:
    if confidence < 0.2:
        return "0.0-0.2"
    if confidence < 0.4:
        return "0.2-0.4"
    if confidence < 0.6:
        return "0.4-0.6"
    if confidence < 0.8:
        return "0.6-0.8"
    if confidence < 0.9:
        return "0.8-0.9"
    return "0.9-1.0"


def _load_gold_paths(gold_path: str | Path | list[str | Path]) -> list[GoldCase]:
    if isinstance(gold_path, (list, tuple)):
        cases: list[GoldCase] = []
        for path in gold_path:
            cases.extend(load_gold(path))
        return cases
    return load_gold(gold_path)


def run_eval(
    schema_path: str | Path,
    gold_path: str | Path | list[str | Path],
    *,
    backend: ChoiceBackend,
) -> EvalReport:
    roots = parse_schema(Path(schema_path).read_text(encoding="utf-8"))
    errors = [issue for issue in validate_schema(roots) if issue.severity == "error"]
    if errors:
        raise ValueError(f"schema inválido: {errors[0].message}")
    folders = iter_leaf_folders(roots)
    cases = _load_gold_paths(gold_path)
    states = [case.state for case in cases]
    primary = classify_many(
        states,
        folders,
        roots=roots,
        backend=backend,
    )

    confusion: dict[str, dict[str, int]] = defaultdict(Counter)
    confidence_buckets: Counter[str] = Counter()
    source_correct: Counter[str] = Counter()
    source_total: Counter[str] = Counter()
    correct = 0
    for case, result in zip(cases, primary, strict=True):
        predicted = result.target or config.FALLBACK_FOLDER
        confusion[case.target][predicted] += 1
        confidence_buckets[_bucket(result.confidence)] += 1
        source_total[case.source] += 1
        if result.target == case.target:
            correct += 1
            source_correct[case.source] += 1
    by_source = {
        source: {
            "correct": source_correct[source],
            "total": source_total[source],
            "accuracy": source_correct[source] / source_total[source],
        }
        for source in sorted(source_total)
    }
    return EvalReport(
        total=len(cases),
        correct=correct,
        confusion={key: dict(value) for key, value in confusion.items()},
        confidence_buckets=dict(confidence_buckets),
        by_source=by_source,
    )


def main(argv: list[str] | None = None) -> int:
    from core.cli import main as cli_main

    arguments = sys.argv[1:] if argv is None else argv
    return cli_main(["eval", *arguments])


if __name__ == "__main__":
    raise SystemExit(main())
