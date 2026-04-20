from __future__ import annotations

from ..utils.languages import LANGUAGE_OPTIONS
from ..utils.model_loader import load_llm_model, unload_model

SYSTEM_PROMPT = (
    "You are a precise multilingual translation assistant. "
    "Do not explain your reasoning. Do not show thinking. "
    "Return only the final translated text. "
    "Preserve line breaks and paragraph breaks when useful."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]


class LLMSimpleTranslateNode:
    CATEGORY = "text"
    FUNCTION = "translate_text"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("translated_text",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"default": "", "multiline": True}),
                "source_language": (LANGUAGE_OPTIONS, {"default": "Auto Detect"}),
                "target_language": (LANGUAGE_OPTIONS[1:], {"default": "Japanese"}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 512, "min": 64, "max": 8192, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _build_user_prompt(self, source_language: str, target_language: str, input_text: str) -> str:
        src = str(source_language or "Auto Detect").strip()
        tgt = str(target_language or "English").strip()
        src_line = (
            "Detect the source language automatically."
            if src == "Auto Detect"
            else f"The source language is {src}."
        )
        return (
            f"Translate the following text into {tgt}.\n"
            f"{src_line}\n"
            "Keep the original meaning, tone, and structure as naturally as possible.\n"
            "Return only the translation.\n\n"
            f"Text:\n{input_text}"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip()

    def translate_text(self, input_text, source_language, target_language, model_path, load_strategy, max_tokens, temperature, top_p):
        if not str(input_text).strip():
            return ("",)

        try:
            loaded = load_llm_model(
                local_model_path=str(model_path or ""),
                temperature=float(temperature),
            )
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": self._build_user_prompt(
                            source_language=str(source_language),
                            target_language=str(target_language),
                            input_text=str(input_text),
                        ),
                    },
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            text = self._clean_text(response["choices"][0]["message"]["content"])
            return (text,)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
