from __future__ import annotations

from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_CONVERTER_SYSTEM_PROMPT = (
    "You convert story text or cut text into model-oriented prompts. "
    "Preserve the strongest visible content and compress it into a reusable output. "
    "Follow the requested target mode exactly. "
    "Return only the converted result."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]


class _ConverterBase:
    def _target_guide(self, mode: str) -> str:
        guides = {
            "Illustrious": (
                "Convert the input into one concise Illustrious-oriented prompt. "
                "Prefer short, concrete, visually specific tags or very short tag-like phrases, comma-separated. "
                "Focus on subject, appearance, clothing, setting, mood, lighting, composition, and key visible details."
            ),
            "Z-Image": (
                "Convert the input into one concise prompt for the Z-Image model. "
                "Prefer natural-language visual description over Danbooru-style tag spam. "
                "Keep the result concrete, readable, image-first, and easy to reuse in generation prompts."
            ),
            "Anima": (
                "Convert the input into one concise prompt for the Anima model. "
                "Keep it anime-oriented, visually direct, and easy to reuse. "
                "Prefer a short natural-language prompt with optional light comma structuring, but do not imitate Illustrious tag spam. "
                "Focus on anime-style character visuals, scene clarity, color, atmosphere, and readable composition."
            ),
        }
        return guides.get(str(mode), guides["Illustrious"])

    def _build_instruction(self, input_text: str, input_type: str, mode: str, language: str, extra_requirements: str, max_tags: int) -> str:
        lang = normalize_output_language(language)
        source_label = "story" if str(input_type) == "story" else "single cut"
        max_tags_rule = (
            f"- Limit the total number of tags to at most {int(max_tags)}\n"
            if str(mode) == "Illustrious" and int(max_tags) > 0
            else ""
        )
        return (
            f"Convert the following {source_label} into one prompt for the target mode.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, tag_mode=(str(mode) == 'Illustrious'))}\n\n"
            f"Target mode:\n{mode}\n\n"
            f"Target guide:\n{self._target_guide(mode)}\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            "Rules:\n"
            "- Return only the converted prompt\n"
            "- No explanations\n"
            "- No numbering\n"
            "- Preserve the core content of the source\n"
            "- Prefer concrete visible details over abstract themes\n"
            "- Match the requested output language strictly\n"
            "- If the input is a story, compress it into one strongest visual prompt direction\n"
            "- If the input is a cut, stay faithful to that single cut only\n"
            f"{max_tags_rule}"
            f"Source {source_label}:\n{input_text}"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip().strip(",")

    def _make_debug_text(self, input_type: str, mode: str, language: str, extra_requirements: str, selected_output: str, max_tags: int | None = None) -> str:
        max_tags_line = f"max_tags: {int(max_tags)}\n" if max_tags is not None else ""
        return (
            f"input_type: {input_type}\n"
            f"mode: {mode}\n"
            f"language: {language}\n"
            f"{max_tags_line}"
            f"extra_requirements: {extra_requirements}\n\n"
            f"selected_output:\n{selected_output}"
        ).strip()

    def _run_one(self, loaded, input_text: str, input_type: str, mode: str, language: str, extra_requirements: str, max_tags: int, max_tokens: int, temperature: float, top_p: float) -> str:
        response = loaded.model.create_chat_completion(
            messages=[
                {"role": "system", "content": f"{DEFAULT_CONVERTER_SYSTEM_PROMPT} {output_language_instruction(language, tag_mode=(str(mode) == 'Illustrious'))}"},
                {"role": "user", "content": self._build_instruction(str(input_text), str(input_type), str(mode), str(language), str(extra_requirements), int(max_tags))},
            ],
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            stop=STOP_TOKENS,
        )
        return self._clean_text(response["choices"][0]["message"]["content"])


class LLMPromptConverterNode(_ConverterBase):
    CATEGORY = "text"
    FUNCTION = "convert_prompt"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("selected_output", "optional_debug_text")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"default": "", "multiline": True}),
                "input_type": (["story", "cut"], {"default": "cut"}),
                "mode": (["Illustrious", "Z-Image", "Anima"], {"default": "Illustrious"}),
                "language": (["English", "Japanese"], {"default": "English"}),
                "max_tags": ("INT", {"default": 32, "min": 1, "max": 200, "step": 1}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "include_debug_text": ("BOOLEAN", {"default": True}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def convert_prompt(self, input_text, input_type, mode, language, max_tags, extra_requirements, include_debug_text, model_path, load_strategy, max_tokens, temperature, top_p):
        if not str(input_text).strip():
            return ("", "")
        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            selected_output = self._run_one(loaded, str(input_text), str(input_type), str(mode), str(language), str(extra_requirements), int(max_tags), int(max_tokens), float(temperature), float(top_p))
            debug_text = self._make_debug_text(str(input_type), str(mode), str(language), str(extra_requirements), selected_output, int(max_tags)) if bool(include_debug_text) else ""
            return (selected_output, debug_text)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()


class LLMPromptConverter8Node(_ConverterBase):
    CATEGORY = "text"
    FUNCTION = "convert_prompt_8"
    RETURN_TYPES = (
        "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING",
    )
    RETURN_NAMES = (
        "output_1", "output_2", "output_3", "output_4",
        "output_5", "output_6", "output_7", "output_8",
        "all_outputs", "optional_debug_text",
    )
    OUTPUT_NODE = False
    MAX_INPUTS = 8

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_1": ("STRING", {"default": "", "multiline": True}),
                "input_2": ("STRING", {"default": "", "multiline": True}),
                "input_3": ("STRING", {"default": "", "multiline": True}),
                "input_4": ("STRING", {"default": "", "multiline": True}),
                "input_5": ("STRING", {"default": "", "multiline": True}),
                "input_6": ("STRING", {"default": "", "multiline": True}),
                "input_7": ("STRING", {"default": "", "multiline": True}),
                "input_8": ("STRING", {"default": "", "multiline": True}),
                "input_count": ("INT", {"default": 8, "min": 1, "max": 8, "step": 1}),
                "input_type": (["story", "cut"], {"default": "cut"}),
                "mode": (["Illustrious", "Z-Image", "Anima"], {"default": "Illustrious"}),
                "language": (["English", "Japanese"], {"default": "English"}),
                "max_tags": ("INT", {"default": 32, "min": 1, "max": 200, "step": 1}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "include_debug_text": ("BOOLEAN", {"default": True}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _join_outputs(self, outputs: list[str]) -> str:
        return "\n\n".join([f"[output_{i+1}]\n{text}" for i, text in enumerate(outputs) if str(text).strip()])

    def convert_prompt_8(self, input_1, input_2, input_3, input_4, input_5, input_6, input_7, input_8, input_count, input_type, mode, language, max_tags, extra_requirements, include_debug_text, model_path, load_strategy, max_tokens, temperature, top_p):
        count = max(1, min(int(input_count), self.MAX_INPUTS))
        inputs = [str(input_1), str(input_2), str(input_3), str(input_4), str(input_5), str(input_6), str(input_7), str(input_8)][:count]
        outputs = [""] * self.MAX_INPUTS
        if not any(text.strip() for text in inputs):
            return tuple(outputs + ["", ""])
        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            for idx, input_text in enumerate(inputs):
                if str(input_text).strip():
                    outputs[idx] = self._run_one(loaded, str(input_text), str(input_type), str(mode), str(language), str(extra_requirements), int(max_tags), int(max_tokens), float(temperature), float(top_p))
            all_outputs = self._join_outputs(outputs[:count])
            debug_text = ""
            if bool(include_debug_text):
                debug_parts = [
                    f"input_count: {count}",
                    f"input_type: {input_type}",
                    f"mode: {mode}",
                    f"language: {language}",
                    f"max_tags: {int(max_tags)}",
                    f"extra_requirements: {extra_requirements}",
                    "",
                    all_outputs,
                ]
                debug_text = "\n".join(debug_parts).strip()
            return tuple(outputs + [all_outputs, debug_text])
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
