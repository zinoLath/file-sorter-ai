from pathlib import Path

from core.ignore import IgnoreMatcher


def test_local_ignore_and_negation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".fsortignore").write_text("*.tmp\n!keep.tmp\n", encoding="utf-8")
    matcher = IgnoreMatcher.from_source(source, global_path=tmp_path / "missing")
    assert matcher.match("a.tmp").ignored is True
    assert matcher.match("a.tmp").pattern == "*.tmp"
    assert matcher.match("keep.tmp").ignored is False


def test_global_applies_before_local(tmp_path):
    global_ignore = tmp_path / "ignore"
    global_ignore.write_text("*.log\n", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / ".fsortignore").write_text("!importante.log\n", encoding="utf-8")
    matcher = IgnoreMatcher.from_source(source, global_path=global_ignore)
    assert matcher.match("debug.log").ignored is True
    assert matcher.match("importante.log").ignored is False


def test_fsortignore_is_never_moved(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".fsortignore").write_text("!.fsortignore\n", encoding="utf-8")
    matcher = IgnoreMatcher.from_source(source, global_path=tmp_path / "missing")
    assert matcher.match(".fsortignore").ignored is True


def test_gitignore_is_not_read(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    matcher = IgnoreMatcher.from_source(source, global_path=tmp_path / "missing")
    assert matcher.match("a.tmp").ignored is False


def test_directory_patterns_use_is_dir(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".fsortignore").write_text("build/\n", encoding="utf-8")
    matcher = IgnoreMatcher.from_source(source, global_path=tmp_path / "missing")
    assert matcher.match("build", is_dir=True).ignored is True
    assert matcher.match("build", is_dir=False).ignored is False
