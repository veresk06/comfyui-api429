import base64
import io
import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from .client import API429Error, Client


class API429GenerateImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "gemini-3.1-flash-image"}),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A ceramic mug on a light studio table, no text",
                    },
                ),
                "size": (["1024x1024", "1536x1024", "1024x1536", "2048x2048"],),
                "run_id": ("STRING", {"default": "image-001"}),
                "allow_paid_generation": ("BOOLEAN", {"default": False}),
            },
            "optional": {"quality": (["default", "low", "medium", "high"],)},
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "API429"
    DESCRIPTION = "One paid image per new run ID. Key is read from API429_API_KEY, never saved in a workflow."

    def generate(
        self, model, prompt, size, run_id, allow_paid_generation, quality="default"
    ):
        if (
            not model.strip()
            or not prompt.strip()
            or size not in self.INPUT_TYPES()["required"]["size"][0]
        ):
            raise API429Error("Model, prompt and a supported size are required.")
        directory = os.environ.get(
            "API429_STATE_DIR", str(Path.home() / ".api429-comfyui")
        )
        payload = {
            "model": model.strip(),
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        if quality != "default":
            payload["quality"] = quality
        response = Client(os.environ.get("API429_API_KEY", ""), directory).generate(
            payload, run_id, allow_paid_generation
        )
        return decode_image(response)


def decode_image(response):
    try:
        data = response["data"]
        if len(data) != 1 or not isinstance(data[0].get("b64_json"), str):
            raise ValueError()
        raw = base64.b64decode(data[0]["b64_json"], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 32_000_000:
                raise ValueError()
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            tensor = torch.from_numpy(
                np.asarray(rgb, dtype=np.float32).copy() / 255.0
            ).unsqueeze(0)
        return (tensor,)
    except (KeyError, TypeError, ValueError, OSError, Image.DecompressionBombError):
        raise API429Error(
            "Expected one base64 image. Original response is saved; no new generation is needed. URL-only responses are not supported in this preview."
        ) from None


class API429EditImage:
    @classmethod
    def INPUT_TYPES(cls):
        fields = API429GenerateImage.INPUT_TYPES()
        fields["required"]["image"] = ("IMAGE",)
        return fields

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "edit"
    CATEGORY = "API429"
    DESCRIPTION = "Edit one reference image via API429. Uses your API429 balance; key stays in the server environment."

    def edit(
        self,
        model,
        prompt,
        size,
        run_id,
        allow_paid_generation,
        image,
        quality="default",
    ):
        if image.shape[0] != 1:
            raise API429Error(
                "Connect one reference image; split batches before this node."
            )
        buffer = io.BytesIO()
        pixels = (
            (image[0].detach().cpu().clamp(0, 1).numpy() * 255).round().astype(np.uint8)
        )
        Image.fromarray(pixels).save(buffer, format="PNG")
        payload = {
            "model": model.strip(),
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
            "_image_b64": base64.b64encode(buffer.getvalue()).decode(),
        }
        if quality != "default":
            payload["quality"] = quality
        client = Client(
            os.environ.get("API429_API_KEY", ""),
            os.environ.get("API429_STATE_DIR", str(Path.home() / ".api429-comfyui")),
        )
        return decode_image(
            client.generate(
                payload, run_id, allow_paid_generation, endpoint="/v1/images/edits"
            )
        )


class API429ImageQueue:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "gemini-3.1-flash-image"}),
                "prompts": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A ceramic mug on a light studio table\nA ceramic mug on a blue studio table",
                    },
                ),
                "size": API429GenerateImage.INPUT_TYPES()["required"]["size"],
                "run_id": ("STRING", {"default": "batch-001"}),
                "max_images": ("INT", {"default": 2, "min": 1, "max": 100}),
                "allow_paid_generation": ("BOOLEAN", {"default": False}),
                "quality": (["default", "low", "medium", "high"],),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "generate_queue"
    CATEGORY = "API429"
    DESCRIPTION = "One prompt per line, processed sequentially. Each result is saved before the next request. Same batch ID resumes saved results; this is not a spending cap."

    def generate_queue(
        self,
        model,
        prompts,
        size,
        run_id,
        max_images,
        allow_paid_generation,
        quality="default",
    ):
        lines = [line.strip() for line in prompts.splitlines() if line.strip()]
        if not lines or len(lines) > max_images or not 1 <= max_images <= 100:
            raise API429Error(
                "Prompt count must be between 1 and max_images (maximum 100). No requests sent."
            )
        if len(run_id) > 70:
            raise API429Error("Queue run ID must be at most 70 characters.")
        result = []
        node = API429GenerateImage()
        for index, prompt in enumerate(lines):
            result.append(
                node.generate(
                    model,
                    prompt,
                    size,
                    f"{run_id}-{index + 1:03}",
                    allow_paid_generation,
                    quality,
                )[0]
            )
        return (result,)


class API429PriceQuote:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "gemini-3.1-flash-image"}),
                "images": ("INT", {"default": 1, "min": 1, "max": 100000}),
                "refresh_id": ("INT", {"default": 0, "min": 0}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "quote"
    CATEGORY = "API429"
    OUTPUT_NODE = True
    DESCRIPTION = "Read current public image rates without a key. Increment refresh_id to refresh. Conditions and extra charges matter; this quote is not an enforced budget."

    def quote(self, model, images, refresh_id):
        import json
        import urllib.request

        from .client import NoRedirect

        with urllib.request.build_opener(NoRedirect).open(
            "https://gateway.api429.com/api/public/catalog", timeout=20
        ) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise API429Error("Catalog response too large.")
        catalog = json.loads(raw)
        item = next((m for m in catalog["models"] if m["id"] == model.strip()), None)
        if not item:
            raise API429Error("Model not found in the public catalog.")
        from decimal import Decimal

        rates = item["pricing"].get("rates", [])
        lines = [f"{model} — public rates as of {catalog['generated_at']}"]
        for rate in rates:
            if rate["metric"] == "image":
                unit = Decimal(rate["amount"]) / Decimal(str(rate["per"]))
                lines.append(
                    f"{rate.get('condition', 'see model documentation')}: ${unit} per output; {images} outputs = ${unit * images}"
                )
        if len(lines) == 1:
            lines.append("No per-image estimate available for this model.")
        lines.append(
            "Output-image estimate only. Input tokens, references, retries and other operations may add charges. Select the exact condition for your request; this is not a spending limit."
        )
        text = "\n".join(lines)
        return {"ui": {"text": [text]}, "result": (text,)}
