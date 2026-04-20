from __future__ import annotations

import json
from typing import Any

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_CHARACTER_SYSTEM_PROMPT = (
    "You design fictional characters for creative workflows. "
    "Use only the fields that are actually provided. "
    "If a field is empty, missing, or set to unspecified, do not mention it, do not infer it, and do not compensate for it. "
    "Write natural, readable character prose rather than analytic or technical descriptions. "
    "Do not dump raw attribute tags into the paragraph. Integrate them into smooth prose. "
    "When hairstyle contains multiple tags, merge them into one natural hairstyle description and remove contradictions. "
    "Avoid sales-like phrasing, avoid specification-like phrasing, and avoid overexplaining. "
    "Return a clean JSON object only. No markdown. No explanation."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]
UNSPECIFIED_VALUES = {"", "none", "null", "unspecified", "auto", "any", "未指定", "なし", "空"}


class LLMCharacterGeneratorNode:
    CATEGORY = "text"
    FUNCTION = "generate_character"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("character_text", "character_json", "save_name_out", "character_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "gender": ("STRING", {"default": "", "multiline": False}),
                "age": ("STRING", {"default": "", "multiline": False}),
                "personality": ("STRING", {"default": "", "multiline": True}),
                "clothing": ("STRING", {"default": "", "multiline": True}),
                "hairstyle": ("STRING", {"default": "", "multiline": True}),
                "occupation": ("STRING", {"default": "", "multiline": False}),
                "appearance": ("STRING", {"default": "", "multiline": True}),
                "atmosphere": ("STRING", {"default": "", "multiline": True}),
                "speech_style": ("STRING", {"default": "", "multiline": True}),
                "world_type": ("STRING", {"default": "", "multiline": False}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "save_dir": ("STRING", {"default": "./llm_character_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 768, "min": 128, "max": 8192, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _is_blank(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in UNSPECIFIED_VALUES
        if isinstance(value, (list, tuple, set)):
            return len(value) == 0
        if isinstance(value, dict):
            return len(value) == 0
        return False

    def _split_items(self, text: str) -> list[str]:
        if self._is_blank(text):
            return []
        raw = str(text).replace("\n", ",")
        parts = []
        for item in raw.split(","):
            cleaned = item.strip()
            if cleaned:
                parts.append(cleaned)
        return parts

    def _clean_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            if self._is_blank(value):
                continue
            if isinstance(value, dict):
                nested = self._clean_payload(value)
                if nested:
                    result[key] = nested
                continue
            if isinstance(value, list):
                filtered = [item for item in value if not self._is_blank(item)]
                if filtered:
                    result[key] = filtered
                continue
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    result[key] = cleaned
                continue
            result[key] = value
        return result

    def _base_inputs(
        self,
        gender,
        age,
        personality,
        clothing,
        hairstyle,
        occupation,
        appearance,
        atmosphere,
        speech_style,
        world_type,
        extra_requirements,
    ) -> dict[str, Any]:
        return self._clean_payload(
            {
                "gender": gender,
                "age": age,
                "personality": self._split_items(personality),
                "clothing": clothing,
                "hairstyle": hairstyle,
                "occupation": occupation,
                "appearance": appearance,
                "atmosphere": self._split_items(atmosphere),
                "speech_style": speech_style,
                "world_type": world_type,
                "extra_requirements": extra_requirements,
            }
        )

    def _build_instruction(self, payload: dict[str, Any], language: str) -> str:
        lang = normalize_output_language(language)
        schema = {
            "character_text": "one compact descriptive paragraph",
            "profile": {
                "gender": "string if provided",
                "age": "string if provided",
                "personality": ["strings only if provided"],
                "clothing": "string if provided",
                "hairstyle": "string if provided",
                "occupation": "string if provided",
                "appearance": "string if provided",
                "atmosphere": ["strings only if provided"],
                "speech_style": "string if provided",
                "world_type": "string if provided",
                "extra_requirements": "string if provided",
            },
            "used_fields": ["names of fields actually used"],
        }
        return (
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang)}\n\n"
            "Task:\n"
            "Generate a fictional character profile from the provided inputs.\n"
            "Absolutely do not use or mention any field that is empty or missing.\n"
            "Do not infer hidden details from omitted fields.\n"
            "Use the given details faithfully and keep the result usable for prompt workflows.\n\n"
            f"Provided inputs JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"Return JSON schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            "Rules:\n"
            "- Return JSON only\n"
            "- No markdown\n"
            "- No comments\n"
            "- Omit empty keys from profile\n"
            "- used_fields must list only keys that were actually present in the provided inputs\n"
            "- character_text must mention only provided fields\n"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip()

    def _extract_json(self, text: str) -> dict[str, Any]:
        raw = self._clean_text(text)
        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start:end + 1])
            raise ValueError("Model did not return valid JSON.")

    def _format_japanese_age_gender(self, payload: dict[str, Any]) -> str:
        gender = str(payload.get("gender", "")).strip()
        age = str(payload.get("age", "")).strip()
        if age and gender:
            return f"{age}の{gender}"
        return age or gender

    def _normalize_hairstyle_ja(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        s = raw
        replacements = {
            "medium wolf cut": "ミディアム寄りのウルフカット",
            "classic wolf cut": "ウルフカット",
            "defined curl": "はっきりしたカール感",
            "heavy bangs": "重めの前髪",
            "middle part": "センターパート",
            "medium ": "ミディアム",
        }
        for k, v in replacements.items():
            s = s.replace(k, v)
        parts = [part.strip() for part in s.replace("、", ",").split(",") if part.strip()]
        unique = []
        for part in parts:
            if part not in unique:
                unique.append(part)
        wolf = any("ウルフ" in p for p in unique)
        curls = [p for p in unique if "カール" in p]
        bangs = [p for p in unique if "前髪" in p]
        parts_misc = [p for p in unique if p not in curls + bangs and "ウルフ" not in p]
        chunks = []
        if wolf:
            chunks.append("ミディアム寄りのウルフカット")
        if curls:
            chunks.append(curls[0])
        if bangs:
            chunks.append(bangs[0])
        for p in parts_misc:
            if p == "センターパート" and bangs:
                continue
            chunks.append(p)
        if not chunks:
            return raw
        if len(chunks) == 1:
            return chunks[0]
        return "、".join(chunks[:-1]) + "を合わせたスタイル"

    def _naturalize_personality_ja(self, values: list[str]) -> str:
        if not values:
            return ""
        joined = "、".join(values)
        replacements = [
            ("予期せぬ状況に直面すると、自己防衛のために極端に合理的な論理を構築しようとする傾向があり", "予期せぬ状況に直面すると、とっさに感情を表に出すより先に理屈で状況を整理し、自分を守ろうとするところがある"),
            ("傾向があり", "ところがある"),
            ("自己防衛のために", "自分を守るために"),
        ]
        for a, b in replacements:
            joined = joined.replace(a, b)
        return joined

    def _naturalize_speech_ja(self, text: str) -> str:
        s = str(text or "").strip()
        if not s:
            return ""
        s = s.replace("常に一文を長く引き延ばし、結論に至るまでに不必要なほどの詳細な前提条件を列挙する", "前置きが長く、結論に入る前に細かな条件や理由を丁寧に並べがち")
        s = s.replace("常に", "")
        s = s.replace("不必要なほどの", "")
        return s.strip("、。 ")

    def _fallback_result(self, payload: dict[str, Any], language: str) -> dict[str, Any]:
        lang = normalize_output_language(language)
        used_fields = list(payload.keys())
        if lang.lower() == "japanese":
            sentences = []
            intro = self._format_japanese_age_gender(payload)
            if intro:
                sentences.append(f"{intro}。")
            personality = self._naturalize_personality_ja(payload.get("personality", [])) if isinstance(payload.get("personality"), list) else ""
            if personality:
                sentences.append(f"{personality}。")
            hairstyle = self._normalize_hairstyle_ja(payload.get("hairstyle", ""))
            if hairstyle:
                sentences.append(f"髪型は{hairstyle}。")
            occupation = str(payload.get("occupation", "")).strip()
            if occupation:
                sentences.append(f"{occupation}としての印象を持つ。")
            clothing = str(payload.get("clothing", "")).strip()
            if clothing:
                sentences.append(f"服装は{clothing}。")
            appearance = str(payload.get("appearance", "")).strip()
            if appearance:
                sentences.append(f"外見は{appearance}。")
            atmosphere = payload.get("atmosphere", [])
            if isinstance(atmosphere, list) and atmosphere:
                sentences.append(f"全体の雰囲気は{'、'.join(atmosphere)}。")
            speech_style = self._naturalize_speech_ja(payload.get("speech_style", ""))
            if speech_style:
                sentences.append(f"話し方は{speech_style}。")
            world_type = str(payload.get("world_type", "")).strip()
            if world_type:
                sentences.append(f"世界観は{world_type}。")
            extra = str(payload.get("extra_requirements", "")).strip()
            if extra:
                sentences.append(f"補足として{extra}。")
            text = "".join(sentences).strip()
        else:
            pieces = []
            for key in used_fields:
                value = payload[key]
                if isinstance(value, list):
                    pieces.append(f"{key}: {', '.join(value)}")
                else:
                    pieces.append(f"{key}: {value}")
            text = "; ".join(pieces)
        return {
            "character_text": text,
            "profile": payload,
            "used_fields": used_fields,
        }

    def generate_character(
        self,
        gender,
        age,
        personality,
        clothing,
        hairstyle,
        occupation,
        appearance,
        atmosphere,
        speech_style,
        world_type,
        extra_requirements,
        language,
        save_dir,
        save_name,
        model_path,
        load_strategy,
        max_tokens,
        temperature,
        top_p,
    ):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "character")
        json_path = str(base_dir / f"{save_name_out}_character.json")
        payload = self._base_inputs(
            gender,
            age,
            personality,
            clothing,
            hairstyle,
            occupation,
            appearance,
            atmosphere,
            speech_style,
            world_type,
            extra_requirements,
        )

        if not payload:
            empty_result = {
                "save_name": save_name_out,
                "node": "character_generator",
                "inputs": {},
                "outputs": {"character_text": "", "profile": {}, "used_fields": []},
            }
            write_text(base_dir / f"{save_name_out}_character.txt", "")
            write_json(base_dir / f"{save_name_out}_character.json", empty_result)
            return ("", "{}", save_name_out, json_path)

        result = None
        try:
            try:
                loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
                response = loaded.model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": f"{DEFAULT_CHARACTER_SYSTEM_PROMPT} {output_language_instruction(language)}"},
                        {"role": "user", "content": self._build_instruction(payload, str(language))},
                    ],
                    max_tokens=int(max_tokens),
                    temperature=float(temperature),
                    top_p=float(top_p),
                    stop=STOP_TOKENS,
                    response_format={"type": "json_object"},
                )
                result = self._extract_json(response["choices"][0]["message"]["content"])
            except Exception:
                result = self._fallback_result(payload, str(language))

            profile = self._clean_payload(result.get("profile", {})) if isinstance(result, dict) else payload
            used_fields = [key for key in result.get("used_fields", []) if key in profile] if isinstance(result, dict) else list(profile.keys())
            character_text = self._clean_text(str((result or {}).get("character_text", "")))
            if not character_text:
                character_text = self._fallback_result(profile, str(language))["character_text"]
            if not used_fields:
                used_fields = list(profile.keys())

            final_result = {
                "save_name": save_name_out,
                "node": "character_generator",
                "inputs": payload,
                "outputs": {
                    "character_text": character_text,
                    "profile": profile,
                    "used_fields": used_fields,
                },
                "settings": {
                    "language": str(language),
                    "save_dir": base_dir_str,
                    "model_path": str(model_path),
                    "load_strategy": str(load_strategy),
                    "max_tokens": int(max_tokens),
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                },
            }
            write_text(base_dir / f"{save_name_out}_character.txt", character_text)
            write_json(base_dir / f"{save_name_out}_character.json", final_result)
            return (character_text, json.dumps(final_result["outputs"], ensure_ascii=False, indent=2), save_name_out, json_path)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
