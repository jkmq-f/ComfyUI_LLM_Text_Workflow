from __future__ import annotations

import json
import re
from typing import Any, Dict

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction
from ..utils.model_loader import load_llm_model, unload_model

STOP_TOKENS = ["</s>", "<|eot_id|>", "<|end|>"]

DEFAULT_COLOR_SYSTEM_PROMPT = (
    "You rewrite outfit descriptions by adding coherent color information only. "
    "Keep garment identity, material identity, profession context, socks, accessories, and shoe identity unchanged. "
    "Do not invent new garments or change the silhouette. "
    "Return a clean JSON object only. No markdown. No explanation."
)


class LLMOutfitColorNode:
    CATEGORY = "text"
    FUNCTION = "add_color"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("colored_outfit_text", "color_summary", "color_tags")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "outfit_text": ("STRING", {"default": "", "multiline": True}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "palette_mode": (["neutral", "warm", "cool", "muted", "earth", "monotone", "high_contrast", "auto"], {"default": "auto"}),
                "color_strength": (["light", "medium", "strong"], {"default": "medium"}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 420, "min": 64, "max": 4096}),
                "temperature": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.05}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs"}),
                "save_name": ("STRING", {"default": "outfit_color"}),
            },
            "optional": {
                "custom_hint": ("STRING", {"default": "", "multiline": False}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _sanitize_model_path(self, model_path: Any) -> str:
        value = str(model_path or "").strip()
        if value in {"0", "None", "null"}:
            return ""
        return value

    def _extract_json(self, text: str) -> Dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            pass
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}

    def _fallback_result(self, outfit_text: str, language: str, palette_mode: str, custom_hint: str) -> Dict[str, Any]:
        clean = self._clean_text(outfit_text)
        lang = normalize_output_language(language)
        if lang == "Japanese":
            summary = f"配色傾向は{palette_mode}" if palette_mode != "auto" else "配色を穏やかに補う"
            if custom_hint:
                summary += f"、{custom_hint}"
            text = clean + ("。" if clean and not clean.endswith("。") else "") + f" 配色としては、{summary}。"
            return {
                "colored_outfit_text": text.strip(),
                "color_summary": summary,
                "color_tags": [palette_mode] if palette_mode != "auto" else [],
            }
        summary = f"palette: {palette_mode}" if palette_mode != "auto" else "light color enhancement"
        if custom_hint:
            summary += f", {custom_hint}"
        text = clean + ("." if clean and not clean.endswith(".") else "") + f" Color direction: {summary}."
        return {
            "colored_outfit_text": text.strip(),
            "color_summary": summary,
            "color_tags": [palette_mode] if palette_mode != "auto" else [],
        }

    def _build_instruction(self, outfit_text: str, language: str, palette_mode: str, color_strength: str, custom_hint: str) -> str:
        lang = normalize_output_language(language)
        target = "Japanese" if lang == "Japanese" else "English"
        return (
            f"Rewrite the following outfit description in {target}.\n"
            "Add coherent color information to garments, socks if present, shoes, and accessories.\n"
            "Keep clothing types, silhouette, profession context, and material details unchanged.\n"
            "Do not invent new garments or accessories.\n"
            "Do not mix Japanese and English item names. Use one language consistently.\n"
            f"Palette mode: {palette_mode}.\n"
            f"Color strength: {color_strength}.\n"
            f"Custom hint: {custom_hint or 'none'}.\n"
            "Return JSON with keys: colored_outfit_text, color_summary, color_tags. color_tags must be an array of short strings.\n"
            f"Outfit text:\n{outfit_text.strip()}"
        )

    def _run_llm_json(self, language: str, user_prompt: str, model_path: str, max_tokens: int, temperature: float, top_p: float):
        loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
        system_prompt = f"{DEFAULT_COLOR_SYSTEM_PROMPT} {output_language_instruction(language, json_mode=True)}"
        last_error = None
        attempts = [
            {"response_format": {"type": "json_object"}},
            {},
        ]
        for idx, extra in enumerate(attempts, start=1):
            try:
                response = loaded.model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=int(max_tokens),
                    temperature=float(temperature),
                    top_p=float(top_p),
                    stop=STOP_TOKENS,
                    **extra,
                )
                raw = response["choices"][0]["message"]["content"]
                parsed = self._extract_json(raw)
                if parsed:
                    return parsed, raw, {"ok": True, "attempt": idx, "used_response_format": bool(extra), "error": ""}
                last_error = "empty_or_unparseable_json"
            except Exception as e:
                last_error = repr(e)
        return None, "", {"ok": False, "attempt": len(attempts), "used_response_format": False, "error": str(last_error or "unknown_error")}

    def add_color(
        self,
        outfit_text,
        language,
        palette_mode,
        color_strength,
        model_path="",
        load_strategy="reload_every_run",
        max_tokens=512,
        temperature=0.4,
        top_p=0.9,
        save_dir="",
        save_name="",
        custom_hint="",
    ):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "outfit_color")
        json_path = base_dir / f"{save_name_out}_outfit_color.json"
        txt_path = base_dir / f"{save_name_out}_outfit_color.txt"
        raw_response = ""
        llm_meta = {"ok": False, "attempt": 0, "used_response_format": False, "error": "not_run"}
        try:
            prompt = self._build_instruction(outfit_text, language, palette_mode, color_strength, custom_hint)
            model_path = self._sanitize_model_path(model_path)
            result, raw_response, llm_meta = self._run_llm_json(language, prompt, model_path, max_tokens, temperature, top_p)
            if not result:
                result = self._fallback_result(outfit_text, language, palette_mode, custom_hint)

            colored_outfit_text = self._clean_text((result or {}).get("colored_outfit_text", ""))
            color_summary = self._clean_text((result or {}).get("color_summary", ""))
            color_tags_raw = (result or {}).get("color_tags", [])
            if isinstance(color_tags_raw, str):
                color_tags = [self._clean_text(x) for x in color_tags_raw.split(",") if self._clean_text(x)]
            else:
                color_tags = [self._clean_text(str(x)) for x in color_tags_raw if self._clean_text(str(x))]

            if not colored_outfit_text or not color_summary:
                fallback = self._fallback_result(outfit_text, language, palette_mode, custom_hint)
                colored_outfit_text = colored_outfit_text or fallback["colored_outfit_text"]
                color_summary = color_summary or fallback["color_summary"]
                if not color_tags:
                    color_tags = fallback["color_tags"]

            final_result = {
                "save_name": save_name_out,
                "node": "outfit_color",
                "inputs": {
                    "outfit_text": outfit_text,
                    "language": language,
                    "palette_mode": palette_mode,
                    "color_strength": color_strength,
                    "custom_hint": custom_hint,
                },
                "outputs": {
                    "colored_outfit_text": colored_outfit_text,
                    "color_summary": color_summary,
                    "color_tags": color_tags,
                },
                "settings": {
                    "model_path": self._sanitize_model_path(model_path),
                    "load_strategy": str(load_strategy),
                    "max_tokens": int(max_tokens),
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                    "save_dir": base_dir_str,
                },
                "llm_meta": llm_meta,
                "raw_response": raw_response,
            }
            write_text(txt_path, colored_outfit_text)
            write_json(json_path, final_result)
            return (colored_outfit_text, color_summary, ", ".join(color_tags))
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
