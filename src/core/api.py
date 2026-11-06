from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Callable

from core import config
from core.budget import BudgetReport, build_budget
from core.fileops import FileOps
from core.model import ChoiceBackend, ModelBackend
from core.orchestrator import SortOrchestrator
from core.plans import (
    APPLICABLE_STATUSES,
    ApplyResult,
    Plan,
    PlanEntry,
    PlanError,
    PlanStore,
    compute_status,
    utc_now,
)
from core.schema import (
    FolderNode,
    SchemaIssue,
    SchemaValidationError,
    iter_leaf_folders,
    load_schema,
    parse_schema,
    sanitize_name,
    save_schema,
    validate_schema,
)

ProgressFn = Callable[[str], None]


class FileSorter:
    def __init__(
        self,
        backend: ChoiceBackend | None = None,
        store: PlanStore | None = None,
        fileops: FileOps | None = None,
        model_path: str | Path | None = None,
    ) -> None:
        self.backend = backend
        if self.backend is None and model_path is not None:
            self.backend = ModelBackend(model_path=model_path)
        self.store = store or PlanStore()
        self.fileops = fileops or FileOps()

    def load_schema(self, path: str | Path) -> list[FolderNode]:
        return load_schema(path)

    def save_schema(self, path: str | Path, folders: list[FolderNode]) -> None:
        save_schema(path, folders)

    def sanitize_name(self, name: str) -> str:
        return sanitize_name(name)

    def validate_schema(self, folders: list[FolderNode]) -> list[SchemaIssue]:
        return validate_schema(folders)

    def budget_report(self, roots: list[FolderNode]) -> BudgetReport:
        tokenizer = getattr(self.backend, "tokenizer", None)
        folders = iter_leaf_folders(roots)
        if len(folders) <= config.MAX_FLAT_FOLDERS:
            criteria = {path: prompt for path, prompt in folders}
            return build_budget(config.INSTRUCTIONS, criteria, tokenizer=tokenizer)

        reports = [self._level_budget(roots, "", tokenizer, root=True)]
        for path, node in self._walk_nodes(roots, ""):
            if node.children:
                reports.append(self._level_budget(node.children, path, tokenizer))
        return self._merge_budgets(reports)

    def _level_budget(
        self,
        nodes: list[FolderNode],
        parent: str,
        tokenizer: object,
        *,
        root: bool = False,
    ) -> BudgetReport:
        criteria = {}
        for node in nodes:
            path = f"{parent}/{node.name}" if parent else node.name
            criteria[path] = node.prompt
        if not root:
            criteria[config.KEEP] = config.KEEP_DESCRIPTION
        return build_budget(config.INSTRUCTIONS, criteria, tokenizer=tokenizer)

    def _walk_nodes(
        self, nodes: list[FolderNode], parent: str
    ) -> Iterator[tuple[str, FolderNode]]:
        for node in nodes:
            path = f"{parent}/{node.name}" if parent else node.name
            yield path, node
            yield from self._walk_nodes(node.children, path)

    @staticmethod
    def _merge_budgets(reports: list[BudgetReport]) -> BudgetReport:
        option_tokens: dict[str, int] = {}
        option_words: dict[str, int] = {}
        for report in reports:
            for option, tokens in report.option_tokens.items():
                option_tokens[option] = max(option_tokens.get(option, 0), tokens)
            for option, words in report.option_words.items():
                option_words[option] = max(option_words.get(option, 0), words)
        return BudgetReport(
            instruction_tokens=max(report.instruction_tokens for report in reports),
            option_tokens=option_tokens,
            total_tokens=max(report.total_tokens for report in reports),
            approximate=any(report.approximate for report in reports),
            instruction_words=max(report.instruction_words for report in reports),
            option_words=option_words,
            total_words=max(report.total_words for report in reports),
        )

    def is_model_loaded(self) -> bool:
        return bool(getattr(self.backend, "loaded", False))

    def model_status(self) -> str:
        if self.backend is None:
            return "ausente"
        if getattr(self.backend, "loaded", False):
            return "pronto"
        path = getattr(self.backend, "model_path", None)
        if path is not None and (Path(path) / "model.safetensors").is_file():
            return "pronto"
        return "não encontrado"

    @staticmethod
    def load_settings() -> dict[str, object]:
        return config.load_config()

    @staticmethod
    def save_settings(settings: dict[str, object]) -> Path:
        return config.save_config(settings)

    @staticmethod
    def default_model_path() -> Path:
        return config.default_model_path()

    @staticmethod
    def env_bool(name: str) -> bool | None:
        return config.env_bool(name)

    def fetch_model(self, progress: ProgressFn | None = None) -> Path:
        from core.fetch import fetch_model

        dest = getattr(self.backend, "model_path", None)
        return fetch_model(dest=dest, progress=progress)

    def plan(
        self,
        schema_path: str | Path,
        source_dir: str | Path,
        target_root: str | Path | None = None,
        include_state: bool = False,
        persist: bool = False,
        progress: ProgressFn | None = None,
    ) -> Plan:
        schema_path = Path(schema_path)
        schema_bytes = schema_path.read_bytes()
        schema_sha256 = hashlib.sha256(schema_bytes).hexdigest()
        roots = parse_schema(schema_bytes.decode("utf-8"))
        issues = validate_schema(roots)
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            raise SchemaValidationError(errors)

        orchestrator = SortOrchestrator(
            iter_leaf_folders(roots),
            schema_path=schema_path,
            schema_sha256=schema_sha256,
            roots=roots,
            backend=self.backend,
            target_root=target_root,
            include_state=include_state,
        )
        plan = orchestrator.plan(source_dir, progress=progress)
        if persist:
            self.store.save(plan)
        return plan

    def apply_plan(self, plan: Plan, progress: ProgressFn | None = None) -> ApplyResult:
        if plan.status not in APPLICABLE_STATUSES:
            raise PlanError(f"plano {plan.id} está {plan.status}; não pode ser aplicado")
        if plan.id is None:
            self.store.save(plan)

        result = plan.result or ApplyResult(started_at=utc_now())
        moved_sources = {entry.source for entry in result.moved}
        previous_failures = list(result.failed)
        non_retryable_sources = {
            failure.source for failure in previous_failures if not failure.retryable
        }
        result.failed = [failure for failure in previous_failures if not failure.retryable]

        blocked_sources = set(non_retryable_sources)
        entries_by_source = {entry.source: entry for entry in plan.entries}
        for failure in previous_failures:
            if failure.phase != "delete":
                continue
            entry = entries_by_source.get(failure.source)
            if entry is None or entry.source in moved_sources:
                continue
            recovered = self.fileops.recover_delete_failure(entry, failure)
            if recovered is None:
                result.failed.append(failure)
                blocked_sources.add(failure.source)
                continue
            result.moved.append(recovered)
            moved_sources.add(entry.source)
            plan.result = result
            plan.status = compute_status(plan.entries, result)
            self.store.save(plan)
            if progress is not None:
                progress(f"Origem removida após falha anterior: {Path(entry.source).name}")

        pending = [
            entry
            for entry in plan.entries
            if entry.source not in moved_sources
            and entry.source not in blocked_sources
        ]

        def persist(current: ApplyResult, entry: PlanEntry) -> None:
            plan.result = current
            plan.status = compute_status(plan.entries, current)
            self.store.save(plan)
            if progress is None:
                return
            if current.moved and current.moved[-1].source == entry.source:
                progress(f"Movido para {current.moved[-1].target}")
            elif current.failed and current.failed[-1].source == entry.source:
                progress(f"Falhou {Path(entry.source).name}: {current.failed[-1].error}")

        result = self.fileops.apply(pending, result=result, on_entry=persist)
        result.finished_at = utc_now()
        plan.result = result
        plan.status = compute_status(plan.entries, result)
        self.store.save(plan)
        return result

    def apply_saved(self, plan_id: int, progress: ProgressFn | None = None) -> ApplyResult:
        return self.apply_plan(self.store.load(plan_id), progress=progress)

    def list_plans(self) -> list[Plan]:
        return self.store.list_plans()

    def show_plan(self, plan_id: int) -> Plan:
        return self.store.load(plan_id)

    def forget_plan(self, plan_id: int) -> None:
        self.store.forget(plan_id)
