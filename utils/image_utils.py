from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from PIL import Image, ImageEnhance
import numpy as np


@dataclass(frozen=True)
class LLMVisionBudget:
    soft_tokens: int
    approx_image_area: int


VISION_BUDGETS = {
    70: LLMVisionBudget(70, 161_000),
    140: LLMVisionBudget(140, 323_000),
    280: LLMVisionBudget(280, 645_000),
    560: LLMVisionBudget(560, 1_300_000),
    1120: LLMVisionBudget(1120, 2_600_000),
}


def round_down_multiple(value: int, multiple: int = 48) -> int:
    return max(multiple, (value // multiple) * multiple)



def fit_size_to_budget(width: int, height: int, approx_area: int) -> Tuple[int, int]:
    if width <= 0 or height <= 0:
        return 480, 480

    area = width * height
    scale = 1.0
    if area > approx_area:
        scale = (approx_area / area) ** 0.5

    new_w = max(48, int(width * scale))
    new_h = max(48, int(height * scale))
    new_w = round_down_multiple(new_w, 48)
    new_h = round_down_multiple(new_h, 48)
    return new_w, new_h



def preprocess_for_gemma4(
    image: Image.Image,
    soft_token_budget: int = 280,
    resize_mode: str = "fit",
    enhance: bool = False,
    enhance_contrast: float = 1.08,
    enhance_sharpness: float = 1.08,
) -> Image.Image:
    budget = VISION_BUDGETS.get(soft_token_budget, VISION_BUDGETS[280])
    src = image.convert("RGB")
    target_w, target_h = fit_size_to_budget(src.width, src.height, budget.approx_image_area)

    if resize_mode == "stretch":
        out = src.resize((target_w, target_h), Image.Resampling.LANCZOS)
    else:
        fit = src.copy()
        fit.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        if resize_mode == "pad":
            canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
            x = (target_w - fit.width) // 2
            y = (target_h - fit.height) // 2
            canvas.paste(fit, (x, y))
            out = canvas
        else:
            out = fit
            out = out.resize((round_down_multiple(out.width, 48), round_down_multiple(out.height, 48)), Image.Resampling.LANCZOS)

    if enhance:
        out = ImageEnhance.Contrast(out).enhance(enhance_contrast)
        out = ImageEnhance.Sharpness(out).enhance(enhance_sharpness)
    return out



def tensor_to_pil(image_tensor) -> Image.Image:
    data = image_tensor
    if hasattr(data, "detach"):
        data = data.detach().cpu().numpy()
    data = np.asarray(data)

    if data.ndim == 4:
        data = data[0]
    if data.ndim != 3:
        raise ValueError(f"Expected image tensor with 3 or 4 dims, got shape {data.shape}")

    if data.shape[0] in (1, 3, 4) and data.shape[-1] not in (1, 3, 4):
        data = np.transpose(data, (1, 2, 0))

    if data.dtype != np.uint8:
        data = np.clip(data * 255.0 if data.max() <= 1.5 else data, 0, 255).astype(np.uint8)

    if data.shape[-1] == 4:
        data = data[:, :, :3]
    if data.shape[-1] == 1:
        data = np.repeat(data, 3, axis=-1)
    return Image.fromarray(data, mode="RGB")
