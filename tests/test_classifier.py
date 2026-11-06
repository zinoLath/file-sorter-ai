import pytest

from core.classifier import LevelDecision, classify_many
from core.model import ChoiceAnswer
from core.schema import FolderNode, iter_folders

FOLDERS = [
    ("documentos", "docs gerais"),
    ("documentos/contas", "contas de luz e água"),
    ("outros", "arquivos diversos"),
]
STATE = {"arquivo": "conta.pdf", "tipo": "texto", "resumo": "conta de luz"}


class FakeModel:
    def __init__(self, choice: str, probability: float = 0.9) -> None:
        self.choice = choice
        self.probability = probability
        self.requests = []

    def predict_choices(self, requests):
        self.requests.extend(requests)
        answers = []
        for request in requests:
            probabilities = {option: 0.0 for option in request.criteria}
            probabilities[self.choice] = self.probability
            remainder = 1.0 - self.probability
            others = [option for option in request.criteria if option != self.choice]
            for option in others:
                probabilities[option] = remainder / len(others)
            answers.append(
                ChoiceAnswer(
                    choice=self.choice,
                    probabilities=probabilities,
                    max_probability=self.probability,
                )
            )
        return answers


def test_chosen_folder():
    classifier = FakeModel("documentos/contas")
    [classification] = classify_many([STATE], FOLDERS, backend=classifier)
    assert classification.target == "documentos/contas"
    assert classification.confidence == pytest.approx(0.9)
    assert classification.reason == "chosen"
    assert classification.trace == (
        LevelDecision(node="", choice="documentos/contas", max_probability=0.9),
    )
    assert classification.probabilities is None


def test_low_confidence_still_chooses():
    [classification] = classify_many(
        [STATE], FOLDERS, backend=FakeModel("documentos/contas", 0.5)
    )
    assert classification.target == "documentos/contas"
    assert classification.reason == "chosen"
    assert classification.confidence == pytest.approx(0.5)


def test_no_backend_returns_no_backend_for_all():
    states = [STATE, {**STATE, "arquivo": "outro.txt"}]
    results = classify_many(states, FOLDERS, backend=None)
    assert [result.reason for result in results] == ["no_backend", "no_backend"]
    assert [result.target for result in results] == [None, None]
    assert [result.trace for result in results] == [(), ()]


def test_requests_are_json_states_without_abstention():
    backend = FakeModel("documentos/contas")
    classify_many([STATE], FOLDERS, backend=backend)
    request = backend.requests[0]
    assert request.state == STATE
    assert request.criteria["documentos/contas"] == "contas de luz e água"
    assert "__abstencao__" not in request.criteria
    assert "absten" not in request.instructions.lower()


def test_probabilities_can_be_requested_for_debug():
    [classification] = classify_many(
        [STATE], FOLDERS, backend=FakeModel("documentos/contas"), include_probabilities=True
    )
    assert classification.probabilities["documentos/contas"] == pytest.approx(0.9)


class ScriptedModel:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def predict_choices(self, requests):
        self.calls.append(len(requests))
        choice, probability = self.answers.pop(0)
        results = []
        for request in requests:
            probabilities = {option: 0.0 for option in request.criteria}
            probabilities[choice] = probability
            results.append(ChoiceAnswer(choice, probabilities, probability))
        return results


def router_tree():
    documentos = FolderNode(
        "documentos",
        "documentos",
        [FolderNode(f"sub{i}", f"sub {i}") for i in range(9)],
    )
    outros = FolderNode(
        "outros",
        "outros",
        [FolderNode(f"extra{i}", f"extra {i}") for i in range(10)],
    )
    roots = [documentos, outros]
    return roots, iter_folders(roots)


def test_router_descends_to_leaf():
    roots, folders = router_tree()
    assert len(folders) > 19
    backend = ScriptedModel(("documentos", 0.9), ("documentos/sub0", 0.85))
    [classification] = classify_many([STATE], folders, roots=roots, backend=backend)
    assert classification.target == "documentos/sub0"
    assert classification.reason == "chosen"
    assert classification.confidence == pytest.approx(0.85)
    assert [step.choice for step in classification.trace] == [
        "documentos",
        "documentos/sub0",
    ]
    assert backend.calls == [1, 1]


def test_router_can_keep_current_folder():
    roots, folders = router_tree()
    backend = ScriptedModel(("documentos", 0.9), ("__manter__", 0.88))
    [classification] = classify_many([STATE], folders, roots=roots, backend=backend)
    assert classification.target == "documentos"
    assert classification.reason == "chosen"


def test_router_descends_into_low_confidence_choice():
    roots, folders = router_tree()
    backend = ScriptedModel(("documentos", 0.9), ("documentos/sub0", 0.5))
    [classification] = classify_many([STATE], folders, roots=roots, backend=backend)
    assert classification.target == "documentos/sub0"
    assert classification.reason == "chosen"
    assert classification.confidence == pytest.approx(0.5)


class MixedRouterModel:
    def predict_choices(self, requests):
        answers = []
        for request in requests:
            filename = request.state["arquivo"]
            if "__manter__" not in request.criteria:
                choice = "documentos"
            else:
                choice = "documentos/sub0" if filename == "a.txt" else "documentos/sub1"
            probabilities = {option: 0.0 for option in request.criteria}
            probabilities[choice] = 0.9
            answers.append(ChoiceAnswer(choice, probabilities, 0.9))
        return answers


def test_router_keeps_original_state_order_with_mixed_depths():
    roots, folders = router_tree()
    states = [
        {**STATE, "arquivo": "a.txt"},
        {**STATE, "arquivo": "b.txt"},
    ]
    results = classify_many(
        states, folders, roots=roots, backend=MixedRouterModel()
    )
    assert [result.target for result in results] == [
        "documentos/sub0",
        "documentos/sub1",
    ]


def test_router_requires_tree():
    folders = [(f"pasta{i}", "x") for i in range(21)]
    with pytest.raises(ValueError):
        classify_many([STATE], folders, backend=FakeModel("pasta0"))


def test_unknown_choice_is_rejected():
    with pytest.raises(ValueError):
        classify_many([STATE], FOLDERS, backend=FakeModel("inexistente"))


def test_over_budget_option_is_rejected():
    from core.budget import BudgetError

    folders = [("a", "palavra " * 40)]
    with pytest.raises(BudgetError):
        classify_many([STATE], folders, backend=FakeModel("a"))
