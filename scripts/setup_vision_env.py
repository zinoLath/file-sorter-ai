from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core import config

PACKAGES = [
    "transformers==4.45.2",
    "timm>=0.9",
    "einops>=0.7",
    "Pillow>=10",
    "sentencepiece",
]
CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"


def _compatible(python: str) -> bool:
    try:
        output = subprocess.check_output(
            [python, "-c", "import sys; print(sys.version_info[:2])"],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return output.strip() in {"(3, 11)", "(3, 12)"}


def _find_python(explicit: str | None) -> str:
    if explicit:
        return explicit
    candidates = [sys.executable, shutil.which("python3.12"), shutil.which("python3.11")]
    for candidate in candidates:
        if candidate and _compatible(candidate):
            return candidate
    return ""


def _install_uv(dest: Path, python: str, cuda: bool) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    subprocess.run([uv, "venv", "--python", python, str(dest)], check=True)
    target = dest / "bin" / "python"
    if cuda:
        subprocess.run(
            [uv, "pip", "install", "--python", str(target), "torch>=2.2"],
            check=True,
        )
    else:
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--python",
                str(target),
                "torch>=2.2",
                "--index-url",
                CPU_TORCH_INDEX,
            ],
            check=True,
        )
    subprocess.run(
        [uv, "pip", "install", "--python", str(target), *PACKAGES],
        check=True,
    )
    # O par torch/torchvision precisa vir junto e do mesmo índice: instalar timm
    # depois pode promover torch a uma versão incompatível com a torchvision.
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(target),
            "torch>=2.2",
            "torchvision>=0.17",
            "--index-url",
            CPU_TORCH_INDEX if not cuda else "https://download.pytorch.org/whl/cu121",
        ],
        check=True,
    )


def _install_pip(dest: Path, python: str, cuda: bool) -> None:
    subprocess.run([python, "-m", "venv", str(dest)], check=True)
    target = dest / "bin" / "python"
    subprocess.run([str(target), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    if cuda:
        subprocess.run([str(target), "-m", "pip", "install", "torch>=2.2"], check=True)
    else:
        subprocess.run(
            [
                str(target),
                "-m",
                "pip",
                "install",
                "torch>=2.2",
                "--index-url",
                CPU_TORCH_INDEX,
            ],
            check=True,
        )
    subprocess.run([str(target), "-m", "pip", "install", *PACKAGES], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cria um venv isolado para o Florence-2 (transformers 4.45)"
    )
    parser.add_argument("--dest", default=str(config.vision_venv_dir()))
    parser.add_argument("--python", default=None, help="interpretador 3.11/3.12")
    parser.add_argument("--cuda", action="store_true", help="instala torch com CUDA")
    args = parser.parse_args()

    dest = Path(args.dest).expanduser()
    python = _find_python(args.python)
    uv = shutil.which("uv")
    if uv is None and not python:
        print(
            "erro: instale Python 3.11/3.12 ou uv, ou passe --python",
            file=sys.stderr,
        )
        return 1
    print(f"Criando venv de visão em {dest}")
    if uv is not None:
        _install_uv(dest, args.python or "3.12", args.cuda)
    else:
        _install_pip(dest, python, args.cuda)
    print(f"Pronto: {dest / 'bin' / 'python'}")
    print("O fsort detecta esse caminho automaticamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
