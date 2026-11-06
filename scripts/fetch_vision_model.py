from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.fetch import fetch_vision_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa o Florence-2 para visão")
    parser.add_argument("--dest", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--revision", default=None)
    args = parser.parse_args()
    try:
        target = fetch_vision_model(
            args.dest, args.model_id, args.revision, progress=print
        )
    except Exception as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    print(f"Modelo de visão em {target}")
    print("Crie o ambiente de visão com: python scripts/setup_vision_env.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
