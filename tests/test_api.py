import os
from pathlib import Path

import pytest

from core import fileops
from core.api import FileSorter
from core.fileops import FileOpError, FileOps
from core.model import ChoiceAnswer
from core.plans import PlanError, PlanStore
from core.schema import FolderNode, SchemaValidationError

SCHEMA = """<targets>
  <documentos prompt="Documentos importantes">
    <contas prompt="Contas de luz e água" />
  </documentos>
  <outros prompt="Diversos" />
</targets>"""


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
            answers.append(ChoiceAnswer(self.choice, probabilities, self.probability))
        return answers


class FlakyFileOps(FileOps):
    def __init__(self):
        super().__init__()
        self.failed_once = False

    def move(self, source, target, expected_sha256=None):
        if not self.failed_once and Path(source).name == "b.txt":
            self.failed_once = True
            raise FileOpError("falha temporária", phase="copy", retryable=True, target=str(target))
        return super().move(source, target, expected_sha256)


@pytest.fixture
def setup(tmp_path):
    schema = tmp_path / "schema.xml"
    schema.write_text(SCHEMA, encoding="utf-8")
    source = tmp_path / "downloads"
    source.mkdir()
    (source / "a.txt").write_text("conta de luz", encoding="utf-8")
    (source / "b.txt").write_text("outra conta", encoding="utf-8")
    store = PlanStore(tmp_path / "plans")
    return schema, source, store


def test_plan_is_ephemeral_by_default(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    assert plan.id is None
    assert store.list_plans() == []


def test_plan_persist_assigns_id(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source, persist=True)
    assert plan.id == 1
    assert store.load(1).id == 1


def test_schema_errors_block_planning(tmp_path):
    schema = tmp_path / "schema.xml"
    schema.write_text('<targets><a prompt="" /></targets>', encoding="utf-8")
    source = tmp_path / "downloads"
    source.mkdir()
    with pytest.raises(SchemaValidationError):
        FileSorter(backend=None, store=PlanStore(tmp_path / "plans")).plan(schema, source)


def test_apply_moves_files_and_persists_status(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    result = sorter.apply_plan(plan)
    target = source / "documentos" / "contas"
    assert sorted(path.name for path in target.iterdir()) == ["a.txt", "b.txt"]
    assert not (source / "a.txt").exists()
    assert result.finished_at is not None
    assert len(result.moved) == 2
    saved = store.load(plan.id)
    assert saved.status == "applied"
    assert saved.result is not None
    assert len(saved.result.moved) == 2


def test_apply_uses_collision_free_target(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    existing = source / "documentos" / "contas" / "a.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("antigo", encoding="utf-8")
    plan = sorter.plan(schema, source)
    result = sorter.apply_plan(plan)
    moved = next(item for item in result.moved if item.source.endswith("a.txt"))
    assert Path(moved.target).name == "a (1).txt"


def test_apply_refuses_applied_plan(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    sorter.apply_plan(plan)
    with pytest.raises(PlanError):
        sorter.apply_plan(plan)


def test_retry_retries_only_retryable_failures(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    sorter.fileops = FlakyFileOps()
    first = sorter.apply_plan(plan)
    assert len(first.moved) == 1
    assert len(first.failed) == 1
    assert plan.status == "partial"

    sorter.fileops = FlakyFileOps()
    sorter.fileops.failed_once = True
    second = sorter.apply_plan(plan)
    assert len(second.moved) == 2
    assert second.failed == []
    assert plan.status == "applied"


def test_retry_after_delete_failure_does_not_duplicate(setup, monkeypatch):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    real_unlink = os.unlink
    failed = {"done": False}

    def flaky_unlink(path):
        if not failed["done"] and Path(path).name == "a.txt" and Path(path).parent == source:
            failed["done"] = True
            raise PermissionError("sem permissão")
        return real_unlink(path)

    monkeypatch.setattr(fileops.os, "unlink", flaky_unlink)
    first = sorter.apply_plan(plan)
    assert any(item.phase == "delete" for item in first.failed)

    monkeypatch.setattr(fileops.os, "unlink", real_unlink)
    second = sorter.apply_plan(plan)
    target_dir = source / "documentos" / "contas"
    assert sorted(path.name for path in target_dir.iterdir()) == ["a.txt", "b.txt"]
    assert not (source / "a.txt").exists()
    assert second.failed == []
    assert plan.status == "applied"


def test_unresolved_delete_failure_does_not_duplicate(setup, monkeypatch):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    real_unlink = os.unlink

    def failing_unlink(path):
        if Path(path).name == "a.txt" and Path(path).parent == source:
            raise PermissionError("sem permissão")
        return real_unlink(path)

    monkeypatch.setattr(fileops.os, "unlink", failing_unlink)
    first = sorter.apply_plan(plan)
    assert any(item.phase == "delete" for item in first.failed)

    second = sorter.apply_plan(plan)
    target_dir = source / "documentos" / "contas"
    assert sorted(path.name for path in target_dir.iterdir()) == ["a.txt", "b.txt"]
    assert any(item.phase == "delete" for item in second.failed)
    assert all("(" not in path.name for path in target_dir.iterdir())


def test_router_budget_is_computed_per_level(tmp_path):
    prompt = "palavra " * 20
    roots = [
        FolderNode(f"raiz{i}", prompt, [FolderNode(f"filha{j}", prompt) for j in range(10)])
        for i in range(3)
    ]
    report = FileSorter(store=PlanStore(tmp_path / "plans")).budget_report(roots)
    assert not report.combined_overflows
    assert report.total_tokens < 512


def test_non_retryable_hash_mismatch_requires_new_plan(setup):
    schema, source, store = setup
    sorter = FileSorter(backend=FakeModel(), store=store)
    plan = sorter.plan(schema, source)
    (source / "a.txt").write_text("mudou", encoding="utf-8")
    result = sorter.apply_plan(plan)
    failure = next(item for item in result.failed if item.source.endswith("a.txt"))
    assert failure.retryable is False
    assert failure.phase == "verify"
    assert (source / "a.txt").exists()
