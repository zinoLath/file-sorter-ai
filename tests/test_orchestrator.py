from pathlib import Path

from core.ignore import IgnoreMatcher
from core.model import ChoiceAnswer
from core.orchestrator import SortOrchestrator

FOLDERS = [("documentos/contas", "contas de luz"), ("outros", "diversos")]


class FakeModel:
    def __init__(self, choice="documentos/contas", probability=0.9):
        self.choice = choice
        self.probability = probability
        self.model_id = "fake-model"

    def predict_choices(self, requests):
        answers = []
        for request in requests:
            probabilities = {option: 0.0 for option in request.criteria}
            probabilities[self.choice] = self.probability
            answers.append(
                ChoiceAnswer(self.choice, probabilities, self.probability)
            )
        return answers


def make_orchestrator(tmp_path, **kwargs):
    return SortOrchestrator(
        FOLDERS,
        schema_path=tmp_path / "schema.xml",
        schema_sha256="abc",
        target_root=tmp_path / "sorted",
        **kwargs,
    )


def test_plan_records_classification_and_hashes(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / "conta-luz.txt").write_text("Conta de luz de janeiro", encoding="utf-8")

    plan = make_orchestrator(tmp_path, backend=FakeModel()).plan(source)

    assert plan.id is None
    assert plan.status == "planned"
    assert len(plan.entries) == 1
    entry = plan.entries[0]
    assert entry.source == str(source / "conta-luz.txt")
    assert entry.target == str(tmp_path / "sorted" / "documentos/contas" / "conta-luz.txt")
    assert entry.kind == "texto"
    assert entry.reason == "chosen"
    assert entry.confidence == 0.9
    assert entry.sha256
    assert entry.size > 0
    assert entry.route[0]["choice"] == "documentos/contas"
    assert entry.state is None


def test_plan_without_backend_uses_fallback(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / "arquivo.txt").write_text("qualquer coisa", encoding="utf-8")

    plan = make_orchestrator(tmp_path, backend=None).plan(source)

    entry = plan.entries[0]
    assert entry.reason == "no_backend"
    assert Path(entry.target).parent.name == "_nao_classificados"


def test_include_state_is_opt_in(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / "arquivo.txt").write_text("conteudo", encoding="utf-8")

    plan = make_orchestrator(tmp_path, backend=FakeModel(), include_state=True).plan(source)

    assert plan.entries[0].state == {
        "arquivo": "arquivo.txt",
        "tipo": "texto",
        "resumo": "conteudo",
    }


def test_hidden_files_enter_plan_directories_and_symlinks_do_not(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / ".oculto.txt").write_text("oculto", encoding="utf-8")
    (source / "subpasta").mkdir()
    target = source / "subpasta" / "arquivo.txt"
    target.write_text("x", encoding="utf-8")
    (source / "link.txt").symlink_to(target)

    plan = make_orchestrator(tmp_path, backend=FakeModel()).plan(source)

    assert [Path(entry.source).name for entry in plan.entries] == [".oculto.txt"]
    assert [skipped.reason for skipped in plan.skipped] == ["symlink"]
    assert Path(plan.skipped[0].source).name == "link.txt"


def test_empty_source_produces_valid_empty_plan(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    plan = make_orchestrator(tmp_path, backend=FakeModel()).plan(source)
    assert plan.entries == []
    assert plan.skipped == []


def test_ignore_and_negation_are_recorded_as_skipped(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / ".fsortignore").write_text("*.tmp\n!keep.tmp\n", encoding="utf-8")
    (source / "a.tmp").write_text("x", encoding="utf-8")
    (source / "keep.tmp").write_text("y", encoding="utf-8")

    plan = make_orchestrator(tmp_path, backend=FakeModel()).plan(source)

    assert [Path(entry.source).name for entry in plan.entries] == ["keep.tmp"]
    skipped = {Path(item.source).name: item for item in plan.skipped}
    assert skipped["a.tmp"].reason == "ignored"
    assert skipped["a.tmp"].detail == "*.tmp"
    assert skipped[".fsortignore"].reason == "ignored"


def test_ignored_directories_do_not_enter_skipped(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / ".fsortignore").write_text("build/\n", encoding="utf-8")
    (source / "build").mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")

    plan = make_orchestrator(tmp_path, backend=FakeModel()).plan(source)

    assert [Path(entry.source).name for entry in plan.entries] == ["a.txt"]
    assert all(Path(item.source).name != "build" for item in plan.skipped)


def test_global_ignore_applies_before_local(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / ".fsortignore").write_text("!importante.log\n", encoding="utf-8")
    global_ignore = tmp_path / "ignore"
    global_ignore.write_text("*.log\n", encoding="utf-8")
    (source / "debug.log").write_text("x", encoding="utf-8")
    (source / "importante.log").write_text("y", encoding="utf-8")

    matcher = IgnoreMatcher.from_source(source, global_path=global_ignore)
    plan = make_orchestrator(tmp_path, backend=FakeModel(), ignore=matcher).plan(source)

    assert [Path(entry.source).name for entry in plan.entries] == ["importante.log"]


def test_target_defaults_to_source(tmp_path):
    source = tmp_path / "downloads"
    source.mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")
    orchestrator = SortOrchestrator(
        FOLDERS,
        schema_path=tmp_path / "schema.xml",
        schema_sha256="abc",
        backend=FakeModel(),
    )
    plan = orchestrator.plan(source)
    assert plan.target == str(source.resolve())
