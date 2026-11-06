import math

import pytest

from core.model import ChoiceRequest, ModelBackend


class FakeTokenizer:
    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": list(range(len(text.split())))}


class FakeEngine:
    def __init__(self, logits=None):
        self.tokenizer = FakeTokenizer()
        self.calls = []
        self.rows = []
        self._logits = logits

    def logits(self, rows):
        self.calls.append(len(rows))
        self.rows.extend(rows)
        if self._logits is not None:
            return self._logits(rows)
        return [[0.0, 2.0, 1.0][: len(row["options"])] for row in rows]


def request(filename="a.txt"):
    return ChoiceRequest(
        state={"arquivo": filename, "tipo": "texto", "resumo": "conta de luz"},
        instructions="Escolha a pasta.",
        criteria={"documentos": "documentos", "contas": "contas", "outros": "outros"},
    )


def test_engine_logits_are_softmaxed_into_choice_answer():
    engine = FakeEngine()
    [answer] = ModelBackend(engine=engine).predict_choices([request()])
    assert answer.choice == "contas"
    assert answer.max_probability == pytest.approx(max(answer.probabilities.values()))
    assert sum(answer.probabilities.values()) == pytest.approx(1.0)
    assert answer.probabilities["contas"] == pytest.approx(
        math.exp(2) / (math.exp(0) + math.exp(2) + math.exp(1))
    )


def test_rows_match_native_runtime_contract():
    engine = FakeEngine()
    ModelBackend(engine=engine).predict_choices([request()])
    [row] = engine.rows
    assert row["state"]["arquivo"] == "a.txt"
    assert row["question"] == "Escolha a pasta."
    assert row["options"] == ["documentos", "contas", "outros"]
    assert row["type"] == "choice"


def test_batch_is_chunked_by_32():
    engine = FakeEngine()
    requests = [request(f"a{index}.txt") for index in range(33)]
    answers = ModelBackend(engine=engine).predict_choices(requests)
    assert len(answers) == 33
    assert engine.calls == [32, 1]


def test_choice_needs_two_to_twenty_options():
    backend = ModelBackend(engine=FakeEngine())
    with pytest.raises(ValueError):
        backend.predict_choices(
            [ChoiceRequest(state={}, instructions="x", criteria={"a": "a"})]
        )
    with pytest.raises(ValueError):
        backend.predict_choices(
            [
                ChoiceRequest(
                    state={},
                    instructions="x",
                    criteria={str(index): "x" for index in range(21)},
                )
            ]
        )


def test_missing_model_path_gives_fetch_instruction(tmp_path):
    backend = ModelBackend(model_path=str(tmp_path / "missing"))
    with pytest.raises(RuntimeError) as error:
        backend.load()
    assert "fsort fetch-model" in str(error.value)


def test_bad_engine_output_is_rejected():
    engine = FakeEngine(logits=lambda rows: [[0.0]])
    with pytest.raises(ValueError):
        ModelBackend(engine=engine).predict_choices([request()])
