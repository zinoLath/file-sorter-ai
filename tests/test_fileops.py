import os
import stat

import pytest

from core import fileops
from core.fileops import FileOpError, FileOps, sha256_file
from core.plans import PlanEntry


def make_entry(source, target, sha256=None):
    return PlanEntry(
        source=str(source),
        target=str(target),
        size=source.stat().st_size,
        sha256=sha256 or sha256_file(source),
        kind="texto",
        confidence=0.9,
        reason="chosen",
    )


def test_move_copies_verifies_and_deletes_source(tmp_path):
    source = tmp_path / "origem" / "a.txt"
    source.parent.mkdir()
    source.write_text("conteudo", encoding="utf-8")
    os.chmod(source, 0o640)
    target = tmp_path / "destino" / "documentos" / "a.txt"

    moved = FileOps().move(source, target)

    assert target.read_text(encoding="utf-8") == "conteudo"
    assert not source.exists()
    assert moved.target == str(target)
    assert moved.sha256 == sha256_file(target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert list(target.parent.glob(".fsort-tmp-*")) == []


def test_collision_uses_next_free_name(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    target = tmp_path / "destino" / "a.txt"
    target.parent.mkdir()
    target.write_text("antigo", encoding="utf-8")

    moved = FileOps().move(source, target)

    assert (target.parent / "a (1).txt").read_text(encoding="utf-8") == "novo"
    assert target.read_text(encoding="utf-8") == "antigo"
    assert moved.target.endswith("a (1).txt")
    assert not source.exists()


def test_hash_mismatch_keeps_source_and_removes_temp(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    target = tmp_path / "destino" / "a.txt"
    with pytest.raises(FileOpError) as error:
        FileOps().move(source, target, expected_sha256="errado")
    assert error.value.phase == "verify"
    assert error.value.retryable is False
    assert source.exists()
    assert not target.exists()
    assert list(target.parent.glob(".fsort-tmp-*")) == []


def test_copy_failure_keeps_source_and_removes_temp(tmp_path, monkeypatch):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    target = tmp_path / "destino" / "a.txt"

    def fail(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(fileops.shutil, "copyfileobj", fail)
    with pytest.raises(FileOpError) as error:
        FileOps().move(source, target)
    assert error.value.phase == "copy"
    assert error.value.retryable is True
    assert source.exists()
    assert list(target.parent.glob(".fsort-tmp-*")) == []


def test_delete_failure_reports_but_keeps_target(tmp_path, monkeypatch):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    target = tmp_path / "destino" / "a.txt"
    real_unlink = os.unlink

    def fail_unlink(path):
        if str(path) == str(source):
            raise PermissionError("sem permissão")
        return real_unlink(path)

    monkeypatch.setattr(fileops.os, "unlink", fail_unlink)
    with pytest.raises(FileOpError) as error:
        FileOps().move(source, target)
    assert error.value.phase == "delete"
    assert error.value.retryable is True
    assert target.exists()
    assert source.exists()


def test_chown_is_best_effort_and_optional(tmp_path, monkeypatch):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    calls = []
    monkeypatch.setattr(fileops.os, "chown", lambda path, uid, gid: calls.append((path, uid, gid)))

    FileOps(chown=True, uid=1000, gid=1000).move(source, tmp_path / "destino" / "a.txt")
    assert calls
    assert all(call[1:] == (1000, 1000) for call in calls)
    assert any(str(call[0]).endswith("destino") for call in calls)


def test_apply_returns_result_and_continues_after_failure(tmp_path, monkeypatch):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    missing = tmp_path / "missing.txt"
    entry_ok = make_entry(source, tmp_path / "destino" / "a.txt")
    entry_bad = PlanEntry(
        source=str(missing),
        target=str(tmp_path / "destino" / "missing.txt"),
        size=1,
        sha256="x",
        kind="texto",
        confidence=0.5,
        reason="chosen",
    )
    result = FileOps().apply([entry_ok, entry_bad])
    assert len(result.moved) == 1
    assert len(result.failed) == 1
    assert result.failed[0].retryable is False
    assert result.finished_at is not None


def test_chown_failure_does_not_leave_root_owned_dirs(tmp_path, monkeypatch):
    source = tmp_path / "a.txt"
    source.write_text("novo", encoding="utf-8")
    target = tmp_path / "destino" / "documentos" / "a.txt"

    def fail_chown(path, uid, gid):
        raise PermissionError("sem permissão")

    monkeypatch.setattr(fileops.os, "chown", fail_chown)
    with pytest.raises(FileOpError) as error:
        FileOps(chown=True, uid=1000, gid=1000).move(source, target)
    assert error.value.phase == "chown"
    assert source.exists()
    assert not (tmp_path / "destino").exists()
