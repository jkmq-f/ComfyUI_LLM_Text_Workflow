from __future__ import annotations

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_TAGS_SYSTEM_PROMPT = (
    "You convert story text into concise tags. "
    "Infer concrete visual, thematic, and character keywords from the story. "
    "Return only tags in the requested format. "
    "Do not explain."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]


class LLMStoryTagsNode:
    CATEGORY = "text"
    FUNCTION = "generate_tags"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("tags_text", "save_name_out", "tags_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "story_text": ("STRING", {"default": "", "multiline": True}),
                "tag_mode": (["general_keywords", "image_prompt_tags", "video_prompt_tags", "character_tags"], {"default": "image_prompt_tags"}),
                "language": (["English", "Japanese"], {"default": "English"}),
                "max_tags": ("INT", {"default": 24, "min": 3, "max": 100, "step": 1}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.4, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _mode_guide(self, tag_mode: str) -> str:
        guides = {
            "general_keywords": "Create broad story keywords covering setting, mood, themes, characters, and notable objects.",
            "image_prompt_tags": "Create visually concrete comma-separated prompt tags suitable for image generation.",
            "video_prompt_tags": "Create visually concrete comma-separated prompt tags with motion, atmosphere, camera, and scene cues suitable for video generation.",
            "character_tags": "Focus on appearance, clothing, personality cues, role, and signature motifs of the main character or characters.",
        }
        return guides.get(str(tag_mode), guides["image_prompt_tags"])

    def _build_instruction(self, story_text, tag_mode, language, max_tags, extra_requirements) -> str:
        lang = normalize_output_language(language)
        return (
            f"Read the following story and convert it into concise tags.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, tag_mode=True)}\n\n"
            f"Mode:\n{tag_mode}\n"
            f"Guideline:\n{self._mode_guide(tag_mode)}\n\n"
            f"Maximum tag count:\n{int(max_tags)}\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            "Rules:\n"
            "- Return one single comma-separated line\n"
            "- No numbering\n"
            "- No explanation\n"
            "- Avoid duplicates\n"
            "- Prefer concrete and reusable tags\n"
            "- Match the requested output language strictly\n\n"
            f"Story:\n{story_text}"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip().strip(",")

    def generate_tags(self, story_text, tag_mode, language, max_tags, extra_requirements, save_dir, save_name, model_path, load_strategy, max_tokens, temperature, top_p):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "tags")
        json_path = str(base_dir / f"{save_name_out}_tags.json")
        if not str(story_text).strip():
            write_text(base_dir / f"{save_name_out}_tags.txt", "")
            write_json(base_dir / f"{save_name_out}_tags.json", {"save_name": save_name_out, "node": "story_tags", "inputs": {"save_dir": base_dir_str}, "outputs": {"tags_text": ""}})
            return ("", save_name_out, json_path)
        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": f"{DEFAULT_TAGS_SYSTEM_PROMPT} {output_language_instruction(language, tag_mode=True)}"},
                    {"role": "user", "content": self._build_instruction(str(story_text), str(tag_mode), str(language), int(max_tags), str(extra_requirements))},
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            text = self._clean_text(response["choices"][0]["message"]["content"])
            txt_path = write_text(base_dir / f"{save_name_out}_tags.txt", text)
            write_json(base_dir / f"{save_name_out}_tags.json", {
                "save_name": save_name_out,
                "node": "story_tags",
                "inputs": {"tag_mode": str(tag_mode), "language": str(language), "max_tags": int(max_tags), "extra_requirements": str(extra_requirements), "save_dir": base_dir_str, "model_path": str(model_path), "load_strategy": str(load_strategy), "max_tokens": int(max_tokens), "temperature": float(temperature), "top_p": float(top_p)},
                "outputs": {"tags_text": text, "text_path": txt_path},
            })
            return (text, save_name_out, json_path)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
