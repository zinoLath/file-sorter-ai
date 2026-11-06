from __future__ import annotations

import argparse
import json
import os
import pwd
import sys
from pathlib import Path

from core import config
from core.api import FileSorter
from core.fileops import FileOps
from core.model import ChoiceBackend, ModelBackend
from core.plans import Plan, PlanError, PlanStore
from core.schema import SchemaValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fsort", description="Organizador de arquivos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="gera um plano de organização")
    plan.add_argument("--schema", required=True, help="schema XML-like")
    plan.add_argument("--source", required=True, help="pasta de origem")
    plan.add_argument("--target", default=None, help="raiz de destino (padrão: origem)")
    plan.add_argument("--model-path", default=None)
    plan.add_argument("--include-state", action="store_true")
    plan.add_argument("--ephemeral", action="store_true", help="não persistir o plano")
    plan.add_argument("--json", action="store_true")

    apply = subparsers.add_parser("apply", help="aplica um plano")
    apply.add_argument("--plan", type=int, required=True, help="id do plano (0 = mais novo)")
    apply.add_argument("--nochown", action="store_true")

    listing = subparsers.add_parser("list", help="lista planos (mais novo primeiro)")
    listing.add_argument("--json", action="store_true")

    show = subparsers.add_parser("show", help="mostra um plano")
    show.add_argument("--plan", type=int, required=True)
    show.add_argument("--json", action="store_true")

    forget = subparsers.add_parser("forget", help="remove um plano não aplicado")
    forget.add_argument("--plan", type=int, required=True)

    fetch = subparsers.add_parser("fetch-model", help="baixa o Julia-1")
    fetch.add_argument("--dest", default=None)
    fetch.add_argument("--revision", default=None)

    fetch_vision = subparsers.add_parser("fetch-vision", help="baixa o Florence-2")
    fetch_vision.add_argument("--dest", default=None)
    fetch_vision.add_argument("--model-id", default=None)
    fetch_vision.add_argument("--revision", default=None)

    evaluate = subparsers.add_parser("eval", help="roda o gold set")
    evaluate.add_argument("--schema", required=True)
    evaluate.add_argument("--gold", action="append", default=None)
    evaluate.add_argument("--local", default=None)
    evaluate.add_argument("--model-path", default=None)
    evaluate.add_argument("--json", action="store_true")

    return parser


def _settings(user_home: Path | None = None) -> dict[str, object]:
    if user_home is None:
        return config.load_config()
    return config.load_config(user_home / ".config" / "fsort" / "config.toml")


def _user_home(uid: int) -> Path:
    return Path(pwd.getpwuid(uid).pw_dir)


def _user_plans_dir(uid: int) -> Path:
    return _user_home(uid) / ".local" / "state" / "fsort" / "plans"


def _model_path(args: argparse.Namespace, settings: dict[str, object]) -> Path:
    value = args.model_path or os.environ.get("FSORT_MODEL_PATH") or settings.get("model_path")
    return Path(value).expanduser() if value else config.default_model_path()


def _include_state(args: argparse.Namespace, settings: dict[str, object]) -> bool:
    if args.include_state:
        return True
    from_env = config.env_bool("FSORT_INCLUDE_STATE")
    if from_env is not None:
        return from_env
    return bool(settings.get("include_state", False))


def _print_plan(plan: Plan) -> None:
    identifier = f"{plan.id:04d}" if plan.id is not None else "ephemeral"
    print(
        f"Plano {identifier}: {len(plan.entries)} arquivo(s), "
        f"{len(plan.skipped)} pulado(s) — {plan.status}"
    )
    for entry in plan.entries:
        print(f"  {entry.source} -> {entry.target} ({entry.reason}, {entry.confidence:.2f})")
    for skipped in plan.skipped:
        print(f"  pulado: {skipped.source} ({skipped.reason}: {skipped.detail})")


def _cmd_plan(
    args: argparse.Namespace,
    backend: ChoiceBackend | None,
    store: PlanStore,
    settings: dict[str, object],
) -> int:
    model_path = _model_path(args, settings)
    active_backend = backend or ModelBackend(model_path=model_path)
    sorter = FileSorter(
        backend=active_backend,
        store=store,
    )
    try:
        plan = sorter.plan(
            args.schema,
            args.source,
            target_root=args.target,
            include_state=_include_state(args, settings),
            persist=not args.ephemeral,
        )
    except (SchemaValidationError, OSError, ValueError, RuntimeError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_plan(plan)
    return 0


def _privileged_owner() -> tuple[int, int] | None:
    if os.geteuid() != 0:
        return None
    uid = os.environ.get("SUDO_UID")
    gid = os.environ.get("SUDO_GID")
    if uid is None or gid is None:
        return None
    return int(uid), int(gid)


def _cmd_apply(args: argparse.Namespace, store: PlanStore, settings: dict[str, object]) -> int:
    owner = _privileged_owner()
    chown = bool(settings.get("chown", True)) and not args.nochown and owner is not None
    uid, gid = owner if owner is not None else (None, None)
    fileops = FileOps(chown=chown, uid=uid, gid=gid)
    sorter = FileSorter(store=store, fileops=fileops)
    try:
        result = sorter.apply_saved(args.plan)
    except (PlanError, OSError, ValueError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    if chown and owner is not None:
        store.chown_tree(*owner)
    print(f"Movidos: {len(result.moved)}; falhas: {len(result.failed)}")
    for failure in result.failed:
        print(
            f"  Falhou: {failure.source}: {failure.error} "
            f"({failure.phase}, {'retryable' if failure.retryable else 'novo plano'})"
        )
    retryable = [failure for failure in result.failed if failure.retryable]
    blocked = [failure for failure in result.failed if not failure.retryable]
    if retryable:
        if owner is None:
            print(f"Tente com privilégio: sudo fsort apply --plan {args.plan}")
        else:
            print(f"Reexecute: fsort apply --plan {args.plan}")
    if blocked:
        print("Entradas não recuperáveis exigem um novo plano.")
    return 1 if result.failed else 0


def _cmd_list(args: argparse.Namespace, store: PlanStore) -> int:
    try:
        plans = FileSorter(store=store).list_plans()
    except PlanError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([plan.to_dict() for plan in plans], ensure_ascii=False, indent=2))
        return 0
    if not plans:
        print("nenhum plano")
        return 0
    for plan in plans:
        print(
            f"{plan.id:04d}  {plan.status:<12}  {plan.created_at}  "
            f"{len(plan.entries)} arquivo(s)  {Path(plan.source).name} -> "
            f"{Path(plan.target).name}"
        )
    return 0


def _cmd_show(args: argparse.Namespace, store: PlanStore) -> int:
    try:
        plan = FileSorter(store=store).show_plan(args.plan)
    except PlanError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_plan(plan)
    return 0


def _cmd_forget(args: argparse.Namespace, store: PlanStore) -> int:
    try:
        FileSorter(store=store).forget_plan(args.plan)
    except PlanError as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    print(f"plano {args.plan} removido")
    return 0


def _cmd_fetch(args: argparse.Namespace, settings: dict[str, object]) -> int:
    from core.fetch import fetch_model

    destination = (
        args.dest
        or os.environ.get("FSORT_MODEL_PATH")
        or settings.get("model_path")
    )
    try:
        target = fetch_model(destination, args.revision, progress=print)
    except Exception as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    print(f"Modelo em {target}")
    print(f"Instale o runtime com: python -m pip install -e {target}")
    return 0


def _cmd_fetch_vision(args: argparse.Namespace) -> int:
    from core.fetch import fetch_vision_model

    try:
        target = fetch_vision_model(
            args.dest,
            args.model_id,
            args.revision,
            progress=print,
        )
    except Exception as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    print(f"Modelo de visão em {target}")
    print("Crie o ambiente de visão com: python scripts/setup_vision_env.py")
    return 0


def _cmd_eval(
    args: argparse.Namespace,
    backend: ChoiceBackend | None,
    settings: dict[str, object],
) -> int:
    from core.eval import run_eval

    active_backend = backend or ModelBackend(model_path=_model_path(args, settings))
    gold_paths: list[str | Path] = list(args.gold or ["evals/gold.jsonl"])
    local = Path(args.local) if args.local else Path("evals/local.jsonl")
    if local.is_file():
        gold_paths = [*gold_paths, local]
    try:
        report = run_eval(
            schema_path=args.schema,
            gold_path=gold_paths,
            backend=active_backend,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.summary())
    return 0


def main(
    argv: list[str] | None = None,
    *,
    backend: ChoiceBackend | None = None,
    store: PlanStore | None = None,
) -> int:
    args = _parser().parse_args(argv)
    owner = _privileged_owner()
    if store is not None:
        plans = store
    elif owner is not None:
        plans = PlanStore(_user_plans_dir(owner[0]))
    else:
        plans = PlanStore()
    settings = _settings(_user_home(owner[0]) if owner is not None else None)
    if args.command == "plan":
        return _cmd_plan(args, backend, plans, settings)
    if args.command == "apply":
        return _cmd_apply(args, plans, settings)
    if args.command == "list":
        return _cmd_list(args, plans)
    if args.command == "show":
        return _cmd_show(args, plans)
    if args.command == "forget":
        return _cmd_forget(args, plans)
    if args.command == "fetch-model":
        return _cmd_fetch(args, settings)
    if args.command == "fetch-vision":
        return _cmd_fetch_vision(args)
    if args.command == "eval":
        return _cmd_eval(args, backend, settings)
    return 2
