from __future__ import annotations

import json
import re
from typing import Any

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]

DEFAULT_SYSTEM_PROMPT = (
    "You generate a random character core for downstream creative workflows. "
    "Return only valid JSON with exactly two fields: personality and speech_style. "
    "Do not add explanations, markdown, code fences, notes, titles, or extra keys."
)


class LLMRandomPersonaSpeechNode:
    CATEGORY = "text"
    FUNCTION = "generate_random_persona_speech"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("personality", "speech_style", "save_name_out", "persona_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647, "step": 1}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_persona_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 384, "min": 64, "max": 2048, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip()

    def _extract_json(self, text: str) -> dict[str, Any]:
        cleaned = self._clean_text(text)
        if not cleaned:
            return {}

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        personality = ""
        speech_style = ""
        for line in cleaned.splitlines():
            low = line.lower().strip()
            if low.startswith("personality"):
                personality = line.split(":", 1)[-1].strip()
            elif low.startswith("speech_style") or low.startswith("speech style"):
                speech_style = line.split(":", 1)[-1].strip()
        return {
            "personality": personality,
            "speech_style": speech_style,
        }

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        personality = str(payload.get("personality", "") or "").strip()
        speech_style = str(payload.get("speech_style", "") or "").strip()
        return {
            "personality": personality,
            "speech_style": speech_style,
        }

    def _build_instruction(self, seed: int, language: str, extra_requirements: str) -> str:
        lang = normalize_output_language(language)
        return (
            "Generate one random character core.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang)}\n\n"
            f"Random seed reference: {int(seed)}\n\n"
            "Output JSON schema:\n"
            "{\n"
            '  "personality": "...",\n'
            '  "speech_style": "..."\n'
            "}\n\n"
            "Hard rules:\n"
            "- Return JSON only\n"
            "- Exactly two keys: personality, speech_style\n"
            "- Generate a different random person each run\n"
            "- personality must be one concrete sentence about behavioral bias, reaction pattern, interpersonal friction, or emotional processing\n"
            "- Do not use thin label-style personality text such as 'kind', 'calm', 'honest', 'awkward but sincere'\n"
            "- Do not use cliché contrast patterns\n"
            "- speech_style must be one concrete sentence about how the person actually speaks: pacing, wording, distance, hesitation, structure, tone shifts, or collapse under pressure\n"
            "- personality and speech_style must feel related to the same person\n"
            "- Avoid praise-oriented summaries and avoid exaggerated villain/saint framing\n"
            "- Keep both outputs reusable for character generation downstream\n\n"
            f"Extra requirements:\n{extra_requirements}\n"
        )

    def generate_random_persona_speech(self, seed, language, extra_requirements, save_dir, save_name, model_path, load_strategy, max_tokens, temperature, top_p):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "persona")
        json_path = str(base_dir / f"{save_name_out}_persona.json")

        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": f"{DEFAULT_SYSTEM_PROMPT} {output_language_instruction(language)}"},
                    {"role": "user", "content": self._build_instruction(int(seed), str(language), str(extra_requirements))},
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            raw_text = self._clean_text(response["choices"][0]["message"]["content"])
            payload = self._normalize_payload(self._extract_json(raw_text))

            personality = payload["personality"]
            speech_style = payload["speech_style"]
            combined_text = (
                f"personality:\n{personality}\n\n"
                f"speech_style:\n{speech_style}\n"
            )
            txt_path = write_text(base_dir / f"{save_name_out}_persona.txt", combined_text)
            write_json(base_dir / f"{save_name_out}_persona.json", {
                "save_name": save_name_out,
                "node": "random_persona_speech",
                "inputs": {
                    "seed": int(seed),
                    "language": str(language),
                    "extra_requirements": str(extra_requirements),
                    "save_dir": base_dir_str,
                    "model_path": str(model_path),
                    "load_strategy": str(load_strategy),
                    "max_tokens": int(max_tokens),
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                },
                "outputs": {
                    "personality": personality,
                    "speech_style": speech_style,
                    "text_path": txt_path,
                },
                "raw_response": raw_text,
            })
            return (personality, speech_style, save_name_out, json_path)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
