from __future__ import annotations

import os
from pathlib import Path

MODEL_ID = "SupersonicLabs/Julia-1"
MAX_DESCRIPTION_CHARS = 2000

FALLBACK_FOLDER = "_nao_classificados"
KEEP = "__manter__"
RESERVED_NAMES = frozenset({KEEP, FALLBACK_FOLDER})

INSTRUCTIONS = "Escolha a pasta de destino mais adequada para o arquivo."
KEEP_DESCRIPTION = "manter nesta pasta"

MAX_FLAT_FOLDERS = 20
MAX_ROOT_CHILDREN = 20
MAX_NON_ROOT_CHILDREN = 19
BATCH_SIZE = 32

MAX_COMBINED_TOKENS = 512
MAX_OPTION_TOKENS = 48
MAX_CONTEXT_TOKENS = 8192
HEAD_TOKENS = 512
TOKENS_PER_WORD = 1.6

VISION_MODEL_ID = "microsoft/Florence-2-base"
VISION_MAX_NEW_TOKENS = 256
VISION_NUM_BEAMS = 3


def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "fsort"


def state_dir() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "fsort"


def plans_dir() -> Path:
    return state_dir() / "plans"


def data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "fsort"


def default_model_path() -> Path:
    return data_dir() / "Julia-1"


def vision_model_path() -> Path:
    return data_dir() / "Florence-2-base"


def vision_venv_dir() -> Path:
    return data_dir() / "vision-venv"


def vision_venv_python() -> Path:
    return vision_venv_dir() / "bin" / "python"


def env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(path: str | Path | None = None) -> dict[str, object]:
    target = Path(path) if path is not None else settings_path()
    if not target.is_file():
        return {}
    import tomllib

    data = tomllib.loads(target.read_text(encoding="utf-8"))
    result: dict[str, object] = {}
    if "chown" in data:
        result["chown"] = bool(data["chown"])
    if "model_path" in data and data["model_path"]:
        result["model_path"] = str(data["model_path"])
    if "include_state" in data:
        result["include_state"] = bool(data["include_state"])
    return result


def save_config(settings: dict[str, object], path: str | Path | None = None) -> Path:
    import json

    target = Path(path) if path is not None else settings_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines: list[str] = []
    if "chown" in settings:
        lines.append(f"chown = {'true' if settings['chown'] else 'false'}")
    if settings.get("model_path"):
        lines.append(f"model_path = {json.dumps(str(settings['model_path']))}")
    if "include_state" in settings:
        lines.append(
            f"include_state = {'true' if settings['include_state'] else 'false'}"
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(target, 0o600)
    return target


def ignore_path() -> Path:
    return config_dir() / "ignore"


def settings_path() -> Path:
    return config_dir() / "config.toml"
