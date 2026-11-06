from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image


def _text_from_generation(processor, text: str, task: str, size: tuple[int, int]) -> str:
    parsed = processor.post_process_generation(text, task=task, image_size=size)
    value = parsed.get(task) if isinstance(parsed, dict) else parsed
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        labels = value.get("labels")
        if isinstance(labels, list):
            return " ".join(str(label) for label in labels).strip()
    return str(value or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker persistente do Florence-2")
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--model-id", default="microsoft/Florence-2-base")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--num-beams", type=int, default=3)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    source = args.model_path
    if not source or not (Path(source) / "config.json").is_file():
        source = args.model_id
    dtype = torch.float16 if args.device.startswith("cuda") else torch.float32
    try:
        model = AutoModelForCausalLM.from_pretrained(
            source, torch_dtype=dtype, trust_remote_code=True
        ).to(args.device)
        model.eval()
        processor = AutoProcessor.from_pretrained(source, trust_remote_code=True)
    except Exception as error:
        print(json.dumps({"error": f"falha ao carregar Florence-2: {error}"}), flush=True)
        return 1

    for line in sys.stdin:
        try:
            request = json.loads(line)
            image = Image.open(request["path"]).convert("RGB")
            task = request["task"]
            inputs = processor(text=task, images=image, return_tensors="pt")
            inputs = {key: value.to(args.device) for key, value in inputs.items()}
            inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
            with torch.inference_mode():
                generated = model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=args.max_new_tokens,
                    num_beams=args.num_beams,
                    do_sample=False,
                )
            text = processor.batch_decode(generated, skip_special_tokens=False)[0]
            print(
                json.dumps(
                    {
                        "text": _text_from_generation(
                            processor, text, task, (image.width, image.height)
                        )
                    }
                ),
                flush=True,
            )
        except Exception as error:
            print(json.dumps({"error": str(error)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
