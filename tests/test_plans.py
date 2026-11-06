import json
import stat

import pytest

from core.plans import (
    ApplyResult,
    FailureRecord,
    MovedEntry,
    Plan,
    PlanEntry,
    PlanError,
    PlanStore,
    SkippedEntry,
    compute_status,
)

SCHEMA = "/tmp/schema.xml"


def make_plan(entries=None, skipped=None, **overrides):
    values = dict(
        id=None,
        created_at="2026-10-29T12:00:00+00:00",
        status="planned",
        source="/tmp/origem",
        target="/tmp/destino",
        schema_path=SCHEMA,
        schema_sha256="abc",
        model_id="SupersonicLabs/Julia-1",
        model_revision=None,
        entries=entries or [],
        skipped=skipped or [],
        result=None,
    )
    values.update(overrides)
    return Plan(**values)


def make_entry(name="a.txt"):
    return PlanEntry(
        source=f"/tmp/origem/{name}",
        target=f"/tmp/destino/documentos/{name}",
        size=3,
        sha256="def",
        kind="texto",
        confidence=0.9,
        reason="chosen",
        route=[{"node": "", "choice": "documentos", "max_probability": 0.9}],
    )


def test_save_assigns_monotonic_ids(tmp_path):
    store = PlanStore(tmp_path / "plans")
    first = store.save(make_plan())
    second = store.save(make_plan())
    assert (first.id, second.id) == (1, 2)
    assert (tmp_path / "plans" / "0001.json").exists()
    assert (tmp_path / "plans" / "0002.json").exists()


def test_plan_zero_loads_latest(tmp_path):
    store = PlanStore(tmp_path / "plans")
    store.save(make_plan())
    latest = store.save(make_plan())
    assert store.load(0).id == latest.id


def test_list_is_newest_first(tmp_path):
    store = PlanStore(tmp_path / "plans")
    store.save(make_plan())
    store.save(make_plan())
    assert [plan.id for plan in store.list_plans()] == [2, 1]


def test_round_trip_preserves_entries_and_skipped(tmp_path):
    store = PlanStore(tmp_path / "plans")
    plan = store.save(
        make_plan(
            entries=[make_entry()],
            skipped=[SkippedEntry(source="/tmp/origem/link", reason="symlink", detail="link")],
        )
    )
    loaded = store.load(plan.id)
    assert loaded.entries[0].source.endswith("a.txt")
    assert loaded.skipped[0].reason == "symlink"


def test_plan_files_are_private(tmp_path):
    root = tmp_path / "plans"
    store = PlanStore(root)
    plan = store.save(make_plan())
    assert stat.S_IMODE((root / "0001.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert plan.id == 1


def test_forget_only_removes_planned(tmp_path):
    store = PlanStore(tmp_path / "plans")
    planned = store.save(make_plan())
    store.forget(planned.id)
    assert store.list_plans() == []

    applied = store.save(make_plan(status="applied"))
    with pytest.raises(PlanError):
        store.forget(applied.id)


def test_forgotten_ids_are_not_reused(tmp_path):
    store = PlanStore(tmp_path / "plans")
    store.save(make_plan())
    latest = store.save(make_plan())
    store.forget(latest.id)
    assert store.save(make_plan()).id == 3


def test_load_missing_plan_is_clear(tmp_path):
    store = PlanStore(tmp_path / "plans")
    with pytest.raises(PlanError):
        store.load(0)


def test_status_rules():
    entries = [make_entry("a.txt"), make_entry("b.txt")]
    assert compute_status(entries, None) == "planned"
    moved = MovedEntry("/a", "/b", 1, "x")
    failure = FailureRecord("/c", "/d", "erro", "copy", True)
    assert compute_status(entries, ApplyResult("s", "f", [moved, moved], [])) == "applied"
    assert compute_status(entries, ApplyResult("s", "f", [moved], [failure])) == "partial"
    assert compute_status(entries, ApplyResult("s", "f", [], [failure])) == "failed"


def test_to_dict_includes_version_and_json_fields(tmp_path):
    store = PlanStore(tmp_path / "plans")
    plan = store.save(make_plan(entries=[make_entry()]))
    data = json.loads((tmp_path / "plans" / "0001.json").read_text())
    assert data["version"] == 1
    assert data["id"] == plan.id
    assert data["entries"][0]["route"][0]["choice"] == "documentos"


def test_chown_tree_covers_plan_files(tmp_path, monkeypatch):
    store = PlanStore(tmp_path / "plans")
    plan = store.save(make_plan())
    calls = []
    monkeypatch.setattr("core.plans.os.chown", lambda path, uid, gid: calls.append((str(path), uid, gid)))
    store.chown_tree(1000, 1000)
    assert any(path.endswith("0001.json") for path, _, _ in calls)
    assert any(path.endswith(".seq") for path, _, _ in calls)
    assert plan.id == 1
