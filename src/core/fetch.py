from __future__ import annotations

from pathlib import Path
from typing import Callable

from core import config

REQUIRED = ("model.safetensors", "julia_config.json", "tokenizer", "pyproject.toml")
VISION_REQUIRED = (
    "config.json",
    "model.safetensors",
    "preprocessor_config.json",
    "processing_florence2.py",
    "modeling_florence2.py",
    "tokenizer.json",
    "vocab.json",
)
VISION_ALLOW_PATTERNS = [
    "*.json",
    "*.py",
    "*.safetensors",
    "vocab.json",
    "LICENSE",
    "README.md",
]

ProgressFn = Callable[[str], None]


def _download(dest: str, revision: str | None) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=config.MODEL_ID,
        revision=revision,
        local_dir=dest,
    )


def fetch_model(
    dest: str | Path | None = None,
    revision: str | None = None,
    progress: ProgressFn | None = None,
) -> Path:
    target = Path(dest) if dest is not None else config.default_model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress(f"Baixando {config.MODEL_ID} para {target}")
    _download(str(target), revision)
    missing = [name for name in REQUIRED if not (target / name).exists()]
    if missing:
        raise RuntimeError(
            f"download incompleto em {target}; faltam: {', '.join(missing)}"
        )
    if progress is not None:
        progress(f"Modelo disponível em {target}")
    return target


def _vision_download(dest: str, model_id: str, revision: str | None) -> str:
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=model_id,
        revision=revision,
        local_dir=dest,
        allow_patterns=VISION_ALLOW_PATTERNS,
    )


def fetch_vision_model(
    dest: str | Path | None = None,
    model_id: str | None = None,
    revision: str | None = None,
    progress: ProgressFn | None = None,
) -> Path:
    target = Path(dest) if dest is not None else config.vision_model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    active_model = model_id or config.VISION_MODEL_ID
    if progress is not None:
        progress(f"Baixando {active_model} para {target}")
    _vision_download(str(target), active_model, revision)
    missing = [name for name in VISION_REQUIRED if not (target / name).exists()]
    if missing:
        raise RuntimeError(
            f"download incompleto em {target}; faltam: {', '.join(missing)}"
        )
    if progress is not None:
        progress(f"Modelo de visão disponível em {target}")
    return target
