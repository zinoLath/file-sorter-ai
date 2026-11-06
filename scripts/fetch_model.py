from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core import config
from core.fetch import fetch_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa o runtime e os pesos do Julia-1")
    parser.add_argument("--dest", default=None)
    parser.add_argument("--revision", default=None)
    args = parser.parse_args()
    settings = config.load_config()
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


if __name__ == "__main__":
    raise SystemExit(main())
