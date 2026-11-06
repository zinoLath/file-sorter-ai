import sys
from pathlib import Path

import pytest
from PIL import Image

from format import describe_file
from format.vision import (
    CAPTION_TASK,
    OCR_TASK,
    SubprocessFlorence2Backend,
    VisionExtractor,
)


class FakeBackend:
    def __init__(self, caption="Uma foto de família na praia", text="CONTA DE LUZ"):
        self.caption = caption
        self.text = text
        self.calls = []

    def run(self, image, task):
        self.calls.append(task)
        return self.caption if task == CAPTION_TASK else self.text


def make_image(tmp_path):
    path = tmp_path / "foto.png"
    Image.new("RGB", (32, 24), "white").save(path)
    return path


def test_describe_combines_caption_and_ocr(tmp_path):
    path = make_image(tmp_path)
    backend = FakeBackend()
    description = VisionExtractor(backend=backend).describe(path)
    assert description.kind == "imagem"
    assert "Uma foto de família na praia" in description.summary
    assert "Texto visível: CONTA DE LUZ" in description.summary
    assert backend.calls == [CAPTION_TASK, OCR_TASK]


def test_ocr_can_be_disabled(tmp_path):
    path = make_image(tmp_path)
    backend = FakeBackend()
    description = VisionExtractor(backend=backend, ocr=False).describe(path)
    assert "CONTA DE LUZ" not in description.summary
    assert backend.calls == [CAPTION_TASK]


def test_blank_ocr_is_not_appended(tmp_path):
    path = make_image(tmp_path)
    backend = FakeBackend(text="   ")
    description = VisionExtractor(backend=backend).describe(path)
    assert "Texto visível" not in description.summary


def test_disabled_vision_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FSORT_VISION", "0")
    with pytest.raises(NotImplementedError):
        VisionExtractor(backend=FakeBackend()).describe(make_image(tmp_path))


def test_describe_file_falls_back_when_backend_fails(tmp_path, monkeypatch):
    import format as format_package

    path = make_image(tmp_path)

    class Failing(FakeBackend):
        def run(self, image, task):
            raise RuntimeError("sem modelo")

    extractors = tuple(
        VisionExtractor(backend=Failing()) if isinstance(item, VisionExtractor) else item
        for item in format_package.EXTRACTORS
    )
    monkeypatch.setattr(format_package, "EXTRACTORS", extractors)
    description = describe_file(path)
    assert description.kind == "imagem"
    assert "indisponível" in description.summary


def test_subprocess_backend_protocol(tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        '    print(json.dumps({"text": "ok " + request["task"]}), flush=True)\n',
        encoding="utf-8",
    )
    backend = SubprocessFlorence2Backend(
        python=sys.executable,
        worker=worker,
    )
    image = Image.new("RGB", (16, 16), "white")
    try:
        assert backend.run(image, CAPTION_TASK) == f"ok {CAPTION_TASK}"
        assert backend.run(image, OCR_TASK) == f"ok {OCR_TASK}"
    finally:
        backend.close()
