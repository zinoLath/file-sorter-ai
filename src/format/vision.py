from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol

from core import config
from format.base import FileDescription

CAPTION_TASK = "<DETAILED_CAPTION>"
OCR_TASK = "<OCR>"


def _transformers_version() -> tuple[int, int] | None:
    try:
        import transformers
    except ImportError:
        return None
    parts = transformers.__version__.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def _inprocess_compatible() -> bool:
    version = _transformers_version()
    return version is not None and version < (4, 46)


def _vision_python() -> Path:
    explicit = os.environ.get("FSORT_VISION_PYTHON")
    if explicit:
        return Path(explicit).expanduser()
    default = config.vision_venv_python()
    if default.is_file():
        return default
    return Path(sys.executable)


class VisionBackend(Protocol):
    def run(self, image: object, task: str) -> str: ...


class Florence2Backend:
    def __init__(
        self,
        model_id: str = config.VISION_MODEL_ID,
        model_path: str | Path | None = None,
        device: str | None = None,
        max_new_tokens: int = config.VISION_MAX_NEW_TOKENS,
        num_beams: int = config.VISION_NUM_BEAMS,
    ) -> None:
        self.model_id = model_id
        self.model_path = (
            Path(model_path) if model_path is not None else config.vision_model_path()
        )
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams
        self._model = None
        self._processor = None
        self._torch = None

    def _source(self) -> str:
        if (self.model_path / "config.json").is_file():
            return str(self.model_path)
        return self.model_id

    def _load(self) -> tuple[object, object, object]:
        if self._model is not None and self._processor is not None and self._torch is not None:
            return self._processor, self._model, self._torch
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as error:
            raise RuntimeError(
                "dependências de visão ausentes; rode "
                "`python scripts/setup_vision_env.py`"
            ) from error
        source = self._source()
        device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        try:
            self._processor = AutoProcessor.from_pretrained(
                source, trust_remote_code=True
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                source, torch_dtype=dtype, trust_remote_code=True
            ).to(device)
            self._model.eval()
        except Exception as error:
            raise RuntimeError(
                "não foi possível carregar Florence-2; rode `fsort fetch-vision` "
                f"ou verifique {self.model_path}"
            ) from error
        self._torch = torch
        self.device = device
        return self._processor, self._model, self._torch

    def run(self, image: object, task: str) -> str:
        processor, model, torch = self._load()
        inputs = processor(text=task, images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        inputs["pixel_values"] = inputs["pixel_values"].to(
            torch.float16 if self.device and self.device.startswith("cuda") else torch.float32
        )
        with torch.inference_mode():
            generated = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=self.max_new_tokens,
                num_beams=self.num_beams,
                do_sample=False,
            )
        text = processor.batch_decode(generated, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(
            text, task=task, image_size=(image.width, image.height)
        )
        value = parsed.get(task) if isinstance(parsed, dict) else parsed
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            labels = value.get("labels")
            if isinstance(labels, list):
                return " ".join(str(label) for label in labels).strip()
        return str(value or "").strip()


class SubprocessFlorence2Backend:
    def __init__(
        self,
        model_id: str = config.VISION_MODEL_ID,
        model_path: str | Path | None = None,
        device: str | None = None,
        max_new_tokens: int = config.VISION_MAX_NEW_TOKENS,
        num_beams: int = config.VISION_NUM_BEAMS,
        python: str | Path | None = None,
        worker: str | Path | None = None,
    ) -> None:
        self.model_id = model_id
        self.model_path = (
            Path(model_path) if model_path is not None else config.vision_model_path()
        )
        self.device = device or "cpu"
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams
        self.python = Path(python) if python is not None else _vision_python()
        self.worker = (
            Path(worker)
            if worker is not None
            else Path(__file__).with_name("florence_worker.py")
        )
        self._process: subprocess.Popen[str] | None = None

    def _start(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        command = [
            str(self.python),
            str(self.worker),
            "--model-path",
            str(self.model_path),
            "--model-id",
            self.model_id,
            "--device",
            self.device,
            "--max-new-tokens",
            str(self.max_new_tokens),
            "--num-beams",
            str(self.num_beams),
        ]
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as error:
            raise RuntimeError(
                "não foi possível iniciar o worker de visão; rode "
                "`python scripts/setup_vision_env.py`"
            ) from error
        return self._process

    def run(self, image: object, task: str) -> str:
        process = self._start()
        assert process.stdin is not None and process.stdout is not None
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
            image.save(temp.name, format="PNG")
            image_path = temp.name
        try:
            process.stdin.write(json.dumps({"path": image_path, "task": task}) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                error = process.stderr.read() if process.stderr is not None else ""
                raise RuntimeError(
                    "worker de visão falhou; rode `python scripts/setup_vision_env.py` "
                    f"e `fsort fetch-vision`. {error.strip()}"
                )
            response = json.loads(line)
            if "error" in response:
                raise RuntimeError(str(response["error"]))
            return str(response.get("text", "")).strip()
        finally:
            try:
                os.unlink(image_path)
            except OSError:
                pass

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        self._process = None


class VisionExtractor:
    extensions = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".avif")
    kind = "imagem"

    def __init__(
        self,
        backend: VisionBackend | None = None,
        *,
        ocr: bool | None = None,
    ) -> None:
        self._backend = backend
        self.enabled = config.env_bool("FSORT_VISION") is not False
        self._closed = False
        atexit.register(self.close)
        if ocr is None:
            env_ocr = config.env_bool("FSORT_VISION_OCR")
            self.ocr = True if env_ocr is None else env_ocr
        else:
            self.ocr = ocr

    def describe(self, path: Path) -> FileDescription:
        if not self.enabled:
            raise NotImplementedError("extração de imagens desativada por FSORT_VISION")
        from PIL import Image

        with Image.open(path) as opened:
            image = opened.convert("RGB")
            backend = self._backend or self._default_backend()
            caption = backend.run(
                image, os.environ.get("FSORT_VISION_TASK", CAPTION_TASK)
            )
            parts = [caption.strip()] if caption.strip() else []
            if self.ocr:
                text = backend.run(image, OCR_TASK).strip()
                if text and text != caption.strip():
                    parts.append(f"Texto visível: {text}")
        summary = " ".join(" ".join(parts).split())
        if not summary:
            summary = f"Imagem {path.name}"
        return FileDescription(
            path=path,
            kind=self.kind,
            summary=summary[: config.MAX_DESCRIPTION_CHARS],
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._backend, "close", None)
        if callable(close):
            close()

    def _default_backend(self) -> VisionBackend:
        if self._backend is None:
            model_id = os.environ.get("FSORT_VISION_MODEL_ID", config.VISION_MODEL_ID)
            model_path = os.environ.get("FSORT_VISION_MODEL_PATH")
            device = os.environ.get("FSORT_VISION_DEVICE")
            isolated = bool(os.environ.get("FSORT_VISION_PYTHON")) or (
                config.vision_venv_python().is_file()
            )
            max_tokens = int(
                os.environ.get("FSORT_VISION_MAX_TOKENS", config.VISION_MAX_NEW_TOKENS)
            )
            beams = int(
                os.environ.get("FSORT_VISION_NUM_BEAMS", config.VISION_NUM_BEAMS)
            )
            if _inprocess_compatible() and not isolated:
                self._backend = Florence2Backend(
                    model_id=model_id,
                    model_path=model_path,
                    device=device,
                    max_new_tokens=max_tokens,
                    num_beams=beams,
                )
            else:
                self._backend = SubprocessFlorence2Backend(
                    model_id=model_id,
                    model_path=model_path,
                    device=device,
                    max_new_tokens=max_tokens,
                    num_beams=beams,
                )
        return self._backend
