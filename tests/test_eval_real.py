import os
from pathlib import Path

import pytest

from core.eval import run_eval
from core.model import ModelBackend

pytestmark = pytest.mark.eval


def test_synthetic_eval_with_real_model():
    model_path = os.environ.get("FSORT_MODEL_PATH")
    if not model_path or not (Path(model_path) / "model.safetensors").is_file():
        pytest.skip("defina FSORT_MODEL_PATH com o Julia-1 baixado")
    report = run_eval(
        "evals/schema.xml",
        "evals/gold.jsonl",
        backend=ModelBackend(model_path=model_path, batch_size=16),
    )
    assert report.total == 400
    assert 0.0 <= report.accuracy <= 1.0
