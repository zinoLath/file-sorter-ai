from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

from core import config

VALID_STATUSES = frozenset({"planned", "partial", "applied", "failed", "rolled_back"})
APPLICABLE_STATUSES = frozenset({"planned", "partial", "failed"})
MAX_PLAN_ID = 9999


class PlanError(ValueError):
    pass


@dataclass
class PlanEntry:
    source: str
    target: str
    size: int
    sha256: str
    kind: str
    confidence: float
    reason: str
    route: list[dict[str, object]] = field(default_factory=list)
    state: dict[str, object] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PlanEntry":
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            size=int(data["size"]),
            sha256=str(data["sha256"]),
            kind=str(data["kind"]),
            confidence=float(data["confidence"]),
            reason=str(data["reason"]),
            route=list(data.get("route") or []),
            state=data.get("state"),
        )


@dataclass
class SkippedEntry:
    source: str
    reason: str
    detail: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SkippedEntry":
        return cls(
            source=str(data["source"]),
            reason=str(data["reason"]),
            detail=str(data.get("detail") or ""),
        )


@dataclass
class MovedEntry:
    source: str
    target: str
    size: int
    sha256: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MovedEntry":
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            size=int(data["size"]),
            sha256=str(data["sha256"]),
        )


@dataclass
class FailureRecord:
    source: str
    target: str
    error: str
    phase: str
    retryable: bool

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FailureRecord":
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            error=str(data["error"]),
            phase=str(data["phase"]),
            retryable=bool(data["retryable"]),
        )


@dataclass
class ApplyResult:
    started_at: str
    finished_at: str | None = None
    moved: list[MovedEntry] = field(default_factory=list)
    failed: list[FailureRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "moved": [asdict(entry) for entry in self.moved],
            "failed": [asdict(entry) for entry in self.failed],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "ApplyResult | None":
        if data is None:
            return None
        return cls(
            started_at=str(data["started_at"]),
            finished_at=data.get("finished_at"),
            moved=[MovedEntry.from_dict(entry) for entry in data.get("moved") or []],
            failed=[FailureRecord.from_dict(entry) for entry in data.get("failed") or []],
        )


@dataclass
class Plan:
    id: int | None
    created_at: str
    status: str
    source: str
    target: str
    schema_path: str
    schema_sha256: str
    model_id: str
    entries: list[PlanEntry]
    skipped: list[SkippedEntry]
    result: ApplyResult | None = None
    model_revision: str | None = None
    version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "id": self.id,
            "created_at": self.created_at,
            "status": self.status,
            "source": self.source,
            "target": self.target,
            "schema_path": self.schema_path,
            "schema_sha256": self.schema_sha256,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "entries": [
                {
                    **asdict(entry),
                    "route": list(entry.route),
                    "state": entry.state,
                }
                for entry in self.entries
            ],
            "skipped": [asdict(entry) for entry in self.skipped],
            "result": self.result.to_dict() if self.result is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Plan":
        return cls(
            version=int(data.get("version", 1)),
            id=int(data["id"]) if data.get("id") is not None else None,
            created_at=str(data["created_at"]),
            status=str(data["status"]),
            source=str(data["source"]),
            target=str(data["target"]),
            schema_path=str(data["schema_path"]),
            schema_sha256=str(data["schema_sha256"]),
            model_id=str(data["model_id"]),
            model_revision=data.get("model_revision"),
            entries=[PlanEntry.from_dict(entry) for entry in data.get("entries") or []],
            skipped=[SkippedEntry.from_dict(entry) for entry in data.get("skipped") or []],
            result=ApplyResult.from_dict(data.get("result")),
        )


def compute_status(entries: list[PlanEntry], result: ApplyResult | None) -> str:
    if result is None:
        return "planned"
    moved = len(result.moved)
    failed = len(result.failed)
    if failed == 0 and moved >= len(entries):
        return "applied"
    if failed == 0 and moved == 0:
        return "planned"
    if moved == 0:
        return "failed"
    return "partial"


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class PlanStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else config.plans_dir()

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    @contextmanager
    def _lock(self, exclusive: bool = True) -> Iterator[None]:
        self._ensure()
        fd = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _ids(self) -> list[int]:
        if not self.root.exists():
            return []
        ids: list[int] = []
        for path in self.root.glob("*.json"):
            try:
                ids.append(int(path.stem))
            except ValueError:
                continue
        return sorted(ids)

    def _last_sequence(self) -> int:
        path = self.root / ".seq"
        try:
            return int(path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            return 0

    def _next_id(self) -> int:
        ids = self._ids()
        next_id = max(max(ids) if ids else 0, self._last_sequence()) + 1
        if next_id > MAX_PLAN_ID:
            raise PlanError(f"limite de {MAX_PLAN_ID} planos atingido")
        return next_id

    def _write_sequence(self, plan_id: int) -> None:
        path = self.root / ".seq"
        fd, temp_name = tempfile.mkstemp(prefix=".seq-", dir=self.root)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"{plan_id}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def _resolve_id(self, plan_id: int) -> int:
        if plan_id != 0:
            return plan_id
        ids = self._ids()
        if not ids:
            raise PlanError("nenhum plano encontrado")
        return max(ids)

    def path_for(self, plan_id: int) -> Path:
        return self.root / f"{plan_id:04d}.json"

    def _write(self, plan: Plan) -> None:
        path = self.path_for(plan.id or 0)
        fd, temp_name = tempfile.mkstemp(prefix=".plan-", suffix=".json", dir=self.root)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(plan.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def save(self, plan: Plan) -> Plan:
        with self._lock():
            if plan.id is None:
                plan.id = self._next_id()
            elif plan.id > MAX_PLAN_ID:
                raise PlanError(f"id de plano inválido: {plan.id}")
            if plan.status not in VALID_STATUSES:
                raise PlanError(f"status de plano inválido: {plan.status}")
            self._write(plan)
            self._write_sequence(plan.id)
            return plan

    def load(self, plan_id: int) -> Plan:
        with self._lock(exclusive=False):
            resolved = self._resolve_id(plan_id)
            path = self.path_for(resolved)
            if not path.exists():
                raise PlanError(f"plano {resolved} não encontrado")
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise PlanError(f"plano {resolved} ilegível: {error}") from error
            return Plan.from_dict(data)

    def list_plans(self) -> list[Plan]:
        with self._lock(exclusive=False):
            return [self._load_unlocked(plan_id) for plan_id in reversed(self._ids())]

    def _load_unlocked(self, plan_id: int) -> Plan:
        path = self.path_for(plan_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PlanError(f"plano {plan_id} ilegível: {error}") from error
        return Plan.from_dict(data)

    def chown_tree(self, uid: int, gid: int) -> None:
        with self._lock():
            paths = [self.root, self.root / ".lock", self.root / ".seq"]
            paths.extend(self.path_for(plan_id) for plan_id in self._ids())
            for path in paths:
                if path.exists():
                    try:
                        os.chown(path, uid, gid)
                    except OSError:
                        pass

    def forget(self, plan_id: int) -> None:
        with self._lock():
            resolved = self._resolve_id(plan_id)
            plan = self._load_unlocked(resolved)
            if plan.status != "planned":
                raise PlanError(
                    f"plano {resolved} está {plan.status}; só planos 'planned' podem ser removidos"
                )
            path = self.path_for(resolved)
            path.unlink()
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
