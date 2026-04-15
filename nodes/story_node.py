from __future__ import annotations

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_STORY_SYSTEM_PROMPT = (
    "You are a fiction writer. "
    "Write the requested story directly. "
    "If details are missing, make reasonable creative assumptions. "
    "Do not ask follow-up questions. "
    "Do not explain what you can do. "
    "Return only the final story text."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]


class LLMStoryNode:
    CATEGORY = "text"
    FUNCTION = "generate_story"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("story_text", "save_name_out", "story_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "idea": ("STRING", {"default": "", "multiline": True}),
                "genre": ("STRING", {"default": "fantasy", "multiline": False}),
                "setting": ("STRING", {"default": "", "multiline": True}),
                "protagonist": ("STRING", {"default": "", "multiline": True}),
                "tone": ("STRING", {"default": "quiet, mysterious, elegant", "multiline": False}),
                "length": (["very_short", "short", "medium", "long"], {"default": "short"}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _length_guide(self, length: str) -> str:
        mapping = {
            "very_short": "around 150 to 300 words",
            "short": "around 400 to 800 words",
            "medium": "around 900 to 1500 words",
            "long": "around 1600 to 2600 words",
        }
        return mapping.get(str(length), "around 400 to 800 words")

    def _build_instruction(self, idea, genre, setting, protagonist, tone, length, language, extra_requirements) -> str:
        lang = normalize_output_language(language)
        return (
            f"Write an original {genre} story.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang)}\n\n"
            f"Core idea:\n{idea}\n\n"
            f"Setting:\n{setting}\n\n"
            f"Protagonist:\n{protagonist}\n\n"
            f"Tone:\n{tone}\n\n"
            f"Target length:\n{self._length_guide(length)}\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            "Rules:\n"
            "- Begin with the actual scene, not with an explanation about the task\n"
            "- If information is incomplete, invent the missing details naturally\n"
            "- Do not ask questions\n"
            "- Do not include notes, headers, bullet points, or meta commentary\n"
            "- Return only the final story text\n"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip()

    def generate_story(self, idea, genre, setting, protagonist, tone, length, language, extra_requirements, save_dir, save_name, model_path, load_strategy, max_tokens, temperature, top_p):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "story")
        json_path = str(base_dir / f"{save_name_out}_story.json")
        if not str(idea).strip() and not str(setting).strip() and not str(protagonist).strip():
            write_text(base_dir / f"{save_name_out}_story.txt", "")
            write_json(base_dir / f"{save_name_out}_story.json", {
                "save_name": save_name_out,
                "node": "story",
                "inputs": {"idea": str(idea), "genre": str(genre), "setting": str(setting), "protagonist": str(protagonist), "tone": str(tone), "length": str(length), "language": str(language), "extra_requirements": str(extra_requirements), "save_dir": base_dir_str},
                "outputs": {"story_text": ""},
            })
            return ("", save_name_out, json_path)
        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": f"{DEFAULT_STORY_SYSTEM_PROMPT} {output_language_instruction(language)}"},
                    {"role": "user", "content": self._build_instruction(str(idea), str(genre), str(setting), str(protagonist), str(tone), str(length), str(language), str(extra_requirements))},
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            text = self._clean_text(response["choices"][0]["message"]["content"])
            txt_path = write_text(base_dir / f"{save_name_out}_story.txt", text)
            write_json(base_dir / f"{save_name_out}_story.json", {
                "save_name": save_name_out,
                "node": "story",
                "inputs": {"idea": str(idea), "genre": str(genre), "setting": str(setting), "protagonist": str(protagonist), "tone": str(tone), "length": str(length), "language": str(language), "extra_requirements": str(extra_requirements), "save_dir": base_dir_str, "model_path": str(model_path), "load_strategy": str(load_strategy), "max_tokens": int(max_tokens), "temperature": float(temperature), "top_p": float(top_p)},
                "outputs": {"story_text": text, "text_path": txt_path},
            })
            return (text, save_name_out, json_path)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
