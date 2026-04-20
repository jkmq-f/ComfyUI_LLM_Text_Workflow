from __future__ import annotations

import json
import re
from typing import Any, Dict

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction
from ..utils.model_loader import load_llm_model, unload_model

STOP_TOKENS = ["</s>", "<|eot_id|>", "<|end|>"]

DEFAULT_TEXTURE_SYSTEM_PROMPT = (
    "You rewrite outfit descriptions by adding material and surface information only. "
    "Keep the garment identity, profession context, socks, and shoe identity unchanged. "
    "Do not add colors unless the input already contains them or the user explicitly asks for color. "
    "Do not replace domain-specific garments such as medical, fantasy, formal, uniform, or technical wear with unrelated fabrics. "
    "Return a clean JSON object only. No markdown. No explanation."
)


class LLMOutfitTextureNode:
    CATEGORY = "text"
    FUNCTION = "add_texture"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("textured_outfit_text", "texture_summary", "material_tags")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "outfit_text": ("STRING", {"default": "", "multiline": True}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "material_focus": (["natural", "technical", "tailored", "luxury", "rugged", "medical", "fantasy", "sci_fi", "auto"], {"default": "auto"}),
                "surface_condition": (["clean", "slightly_worn", "worn", "weathered", "auto"], {"default": "auto"}),
                "texture_strength": (["light", "medium", "strong"], {"default": "medium"}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 420, "min": 64, "max": 4096}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.05}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs"}),
                "save_name": ("STRING", {"default": "outfit_texture"}),
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

    def _fallback_result(self, outfit_text: str, language: str, material_focus: str, surface_condition: str, custom_hint: str) -> Dict[str, Any]:
        lang = normalize_output_language(language)
        clean = self._clean_text(outfit_text)
        if lang == "Japanese":
            fragments = []
            if material_focus != "auto":
                fragments.append(f"素材傾向は{material_focus}")
            if surface_condition != "auto":
                fragments.append(f"表面状態は{surface_condition}")
            if custom_hint:
                fragments.append(custom_hint)
            summary = "、".join(fragments) if fragments else "素材感を軽く補う"
            text = clean + ("。" if clean and not clean.endswith("。") else "") + f" 素材感としては、{summary}。"
            return {
                "textured_outfit_text": text.strip(),
                "texture_summary": summary,
                "material_tags": [t for t in [material_focus, surface_condition] if t and t != "auto"],
            }
        fragments = []
        if material_focus != "auto":
            fragments.append(f"material direction: {material_focus}")
        if surface_condition != "auto":
            fragments.append(f"surface condition: {surface_condition}")
        if custom_hint:
            fragments.append(custom_hint)
        summary = ", ".join(fragments) if fragments else "light texture enhancement"
        text = clean + ("." if clean and not clean.endswith(".") else "") + f" Material texture: {summary}."
        return {
            "textured_outfit_text": text.strip(),
            "texture_summary": summary,
            "material_tags": [t for t in [material_focus, surface_condition] if t and t != "auto"],
        }

    def _build_instruction(self, outfit_text: str, language: str, material_focus: str, surface_condition: str, texture_strength: str, custom_hint: str) -> str:
        lang = normalize_output_language(language)
        target = "Japanese" if lang == "Japanese" else "English"
        return (
            f"Rewrite the following outfit description in {target}.\n"
            "Add plausible material, surface, and tactile detail while preserving garment types, accessories, socks, silhouette, profession context, and shoes.\n"
            "Do not invent new garment items. Do not change the clothing category.\n"
            "Do not invent colors unless they already exist in the input or the custom hint explicitly requests color.\n"
            "Do not mix Japanese and English item names in the rewritten output. Use one language consistently.\n"
            "If the outfit is medical, formal, fantasy, or sci-fi, choose materials that fit that domain.\n"
            f"Material focus: {material_focus}.\n"
            f"Surface condition: {surface_condition}.\n"
            f"Texture strength: {texture_strength}.\n"
            f"Custom hint: {custom_hint or 'none'}.\n"
            "Return JSON with keys: textured_outfit_text, texture_summary, material_tags. material_tags must be an array of short strings.\n"
            f"Outfit text:\n{outfit_text.strip()}"
        )

    def _run_llm_json(self, language: str, user_prompt: str, model_path: str, max_tokens: int, temperature: float, top_p: float):
        loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
        system_prompt = f"{DEFAULT_TEXTURE_SYSTEM_PROMPT} {output_language_instruction(language, json_mode=True)}"
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

    def add_texture(
        self,
        outfit_text,
        language,
        material_focus,
        surface_condition,
        texture_strength,
        model_path="",
        load_strategy="reload_every_run",
        max_tokens=512,
        temperature=0.4,
        top_p=0.9,
        save_dir="",
        save_name="",
        custom_hint="",
    ):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "outfit_texture")
        json_path = base_dir / f"{save_name_out}_outfit_texture.json"
        txt_path = base_dir / f"{save_name_out}_outfit_texture.txt"
        raw_response = ""
        llm_meta = {"ok": False, "attempt": 0, "used_response_format": False, "error": "not_run"}
        try:
            prompt = self._build_instruction(outfit_text, language, material_focus, surface_condition, texture_strength, custom_hint)
            model_path = self._sanitize_model_path(model_path)
            result, raw_response, llm_meta = self._run_llm_json(language, prompt, model_path, max_tokens, temperature, top_p)
            if not result:
                result = self._fallback_result(outfit_text, language, material_focus, surface_condition, custom_hint)

            textured_outfit_text = self._clean_text((result or {}).get("textured_outfit_text", ""))
            texture_summary = self._clean_text((result or {}).get("texture_summary", ""))
            material_tags_raw = (result or {}).get("material_tags", [])
            if isinstance(material_tags_raw, str):
                material_tags = [self._clean_text(x) for x in material_tags_raw.split(",") if self._clean_text(x)]
            else:
                material_tags = [self._clean_text(str(x)) for x in material_tags_raw if self._clean_text(str(x))]

            if not textured_outfit_text or not texture_summary:
                fallback = self._fallback_result(outfit_text, language, material_focus, surface_condition, custom_hint)
                textured_outfit_text = textured_outfit_text or fallback["textured_outfit_text"]
                texture_summary = texture_summary or fallback["texture_summary"]
                if not material_tags:
                    material_tags = fallback["material_tags"]

            final_result = {
                "save_name": save_name_out,
                "node": "outfit_texture",
                "inputs": {
                    "outfit_text": outfit_text,
                    "language": language,
                    "material_focus": material_focus,
                    "surface_condition": surface_condition,
                    "texture_strength": texture_strength,
                    "custom_hint": custom_hint,
                },
                "outputs": {
                    "textured_outfit_text": textured_outfit_text,
                    "texture_summary": texture_summary,
                    "material_tags": material_tags,
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
            write_text(txt_path, textured_outfit_text)
            write_json(json_path, final_result)
            return (textured_outfit_text, texture_summary, ", ".join(material_tags))
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
