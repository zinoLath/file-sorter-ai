from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from core.plans import ApplyResult, FailureRecord, MovedEntry, PlanEntry

CHUNK = 1024 * 1024


class FileOpError(Exception):
    def __init__(
        self,
        message: str,
        *,
        phase: str,
        retryable: bool,
        target: str | None = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.retryable = retryable
        self.target = target


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileOps:
    def __init__(
        self,
        *,
        chown: bool = False,
        uid: int | None = None,
        gid: int | None = None,
    ) -> None:
        self.chown = chown
        self.uid = uid
        self.gid = gid

    def move(
        self,
        source: str | Path,
        target: str | Path,
        expected_sha256: str | None = None,
    ) -> MovedEntry:
        source_path = Path(source)
        target_path = Path(target)
        try:
            source_stat = source_path.stat()
            source_hash = sha256_file(source_path)
        except FileNotFoundError as error:
            raise FileOpError(
                f"origem não encontrada: {source_path}",
                phase="verify",
                retryable=False,
                target=str(target_path),
            ) from error
        except OSError as error:
            raise FileOpError(
                f"falha ao ler origem: {error}",
                phase="verify",
                retryable=True,
                target=str(target_path),
            ) from error

        if expected_sha256 is not None and source_hash != expected_sha256:
            raise FileOpError(
                f"hash da origem divergiu: {source_path}",
                phase="verify",
                retryable=False,
                target=str(target_path),
            )

        if source_path.resolve() == target_path.resolve():
            return MovedEntry(
                source=str(source_path),
                target=str(target_path),
                size=source_stat.st_size,
                sha256=source_hash,
            )

        try:
            self._ensure_parent(target_path.parent)
        except FileOpError:
            raise
        except OSError as error:
            raise FileOpError(
                f"falha ao criar destino: {error}",
                phase="mkdir",
                retryable=True,
                target=str(target_path),
            ) from error

        fd, temp_name = tempfile.mkstemp(prefix=".fsort-tmp-", dir=target_path.parent)
        temp_path = Path(temp_name)
        try:
            try:
                with source_path.open("rb") as reader, os.fdopen(fd, "wb") as writer:
                    shutil.copyfileobj(reader, writer, CHUNK)
                    writer.flush()
                    os.fsync(writer.fileno())
            except OSError as error:
                raise FileOpError(
                    f"falha ao copiar: {error}",
                    phase="copy",
                    retryable=True,
                    target=str(target_path),
                ) from error

            temp_hash = sha256_file(temp_path)
            if temp_hash != source_hash:
                raise FileOpError(
                    f"hash da cópia divergiu: {source_path}",
                    phase="verify",
                    retryable=False,
                    target=str(target_path),
                )

            try:
                os.chmod(temp_path, stat.S_IMODE(source_stat.st_mode))
                os.utime(
                    temp_path,
                    ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
                )
            except OSError:
                pass

            if self.chown and self.uid is not None and self.gid is not None:
                try:
                    os.chown(temp_path, self.uid, self.gid)
                except OSError as error:
                    raise FileOpError(
                        f"falha ao ajustar dono: {error}",
                        phase="chown",
                        retryable=True,
                        target=str(target_path),
                    ) from error

            effective = unique_path(target_path)
            try:
                os.replace(temp_path, effective)
            except OSError as error:
                raise FileOpError(
                    f"falha ao renomear: {error}",
                    phase="rename",
                    retryable=True,
                    target=str(effective),
                ) from error
            self._fsync_dir(effective.parent)

            try:
                os.unlink(source_path)
            except OSError as error:
                raise FileOpError(
                    f"falha ao remover origem após cópia: {error}",
                    phase="delete",
                    retryable=True,
                    target=str(effective),
                ) from error

            return MovedEntry(
                source=str(source_path),
                target=str(effective),
                size=source_stat.st_size,
                sha256=source_hash,
            )
        finally:
            if temp_path.exists():
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def recover_delete_failure(
        self, entry: PlanEntry, failure: FailureRecord
    ) -> MovedEntry | None:
        if failure.phase != "delete":
            return None
        source = Path(entry.source)
        target = Path(failure.target)
        try:
            if not target.is_file():
                return None
            if entry.sha256 and sha256_file(target) != entry.sha256:
                return None
            if source.exists():
                if entry.sha256 and sha256_file(source) != entry.sha256:
                    return None
                os.unlink(source)
            return MovedEntry(
                source=entry.source,
                target=str(target),
                size=entry.size,
                sha256=entry.sha256,
            )
        except OSError:
            return None

    def apply(
        self,
        entries: Iterable[PlanEntry],
        *,
        result: ApplyResult | None = None,
        on_entry: Callable[[ApplyResult, PlanEntry], None] | None = None,
    ) -> ApplyResult:
        result = result or ApplyResult(started_at=_now())
        for entry in entries:
            try:
                moved = self.move(
                    entry.source,
                    entry.target,
                    expected_sha256=entry.sha256 or None,
                )
                result.moved.append(moved)
            except FileOpError as error:
                retryable = error.retryable
                if isinstance(error.__cause__, FileNotFoundError):
                    retryable = False
                result.failed.append(
                    FailureRecord(
                        source=entry.source,
                        target=error.target or entry.target,
                        error=str(error),
                        phase=error.phase,
                        retryable=retryable,
                    )
                )
            if on_entry is not None:
                on_entry(result, entry)
        result.finished_at = _now()
        return result

    def _ensure_parent(self, parent: Path) -> None:
        missing: list[Path] = []
        current = parent
        while not current.exists() and current.parent != current:
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            directory.mkdir(exist_ok=True)
            if self.chown and self.uid is not None and self.gid is not None:
                try:
                    os.chown(directory, self.uid, self.gid)
                except OSError as error:
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
                    raise FileOpError(
                        f"falha ao ajustar dono do diretório: {error}",
                        phase="chown",
                        retryable=True,
                        target=str(directory),
                    ) from error

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        try:
            directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return
        try:
            os.fsync(directory)
        except OSError:
            pass
        finally:
            os.close(directory)
