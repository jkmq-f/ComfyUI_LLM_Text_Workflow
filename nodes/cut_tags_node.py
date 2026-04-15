from __future__ import annotations

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_CUT_TAGS_SYSTEM_PROMPT = (
    "You convert cut descriptions into concise reusable tags. "
    "Infer concrete visual, thematic, motion, atmosphere, and character keywords from each cut. "
    "Return only tags in the requested format. "
    "Do not explain."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]
MAX_CUTS = 8


class LLMCutTagsNode:
    CATEGORY = "text"
    FUNCTION = "generate_cut_tags"
    RETURN_TYPES = (
        "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "INT", "STRING",
    )
    RETURN_NAMES = (
        "tag_1", "tag_2", "tag_3", "tag_4",
        "tag_5", "tag_6", "tag_7", "tag_8",
        "all_cut_tags", "save_name_out", "cut_count_out", "cut_tags_json_path",
    )
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "cut_1": ("STRING", {"default": "", "multiline": True}),
                "cut_2": ("STRING", {"default": "", "multiline": True}),
                "cut_3": ("STRING", {"default": "", "multiline": True}),
                "cut_4": ("STRING", {"default": "", "multiline": True}),
                "cut_5": ("STRING", {"default": "", "multiline": True}),
                "cut_6": ("STRING", {"default": "", "multiline": True}),
                "cut_7": ("STRING", {"default": "", "multiline": True}),
                "cut_8": ("STRING", {"default": "", "multiline": True}),
                "cut_count": ("INT", {"default": 4, "min": 1, "max": MAX_CUTS, "step": 1}),
                "tag_mode": (["general_keywords", "image_prompt_tags", "video_prompt_tags", "character_tags"], {"default": "video_prompt_tags"}),
                "language": (["English", "Japanese"], {"default": "English"}),
                "max_tags_per_cut": ("INT", {"default": 20, "min": 3, "max": 100, "step": 1}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 1024, "min": 64, "max": 4096, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.4, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _mode_guide(self, tag_mode: str) -> str:
        guides = {
            "general_keywords": "Create broad cut-level keywords covering setting, mood, themes, characters, and notable objects.",
            "image_prompt_tags": "Create visually concrete comma-separated prompt tags suitable for image generation from a single cut.",
            "video_prompt_tags": "Create visually concrete comma-separated prompt tags with motion, atmosphere, camera, and scene cues suitable for video generation from a single cut.",
            "character_tags": "Focus on appearance, clothing, personality cues, role, and signature motifs of the visible main character or characters in the cut.",
        }
        return guides.get(str(tag_mode), guides["video_prompt_tags"])

    def _build_instruction(self, cut_text, tag_mode, language, max_tags_per_cut, extra_requirements) -> str:
        lang = normalize_output_language(language)
        return (
            f"Read the following cut description and convert it into concise tags.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, tag_mode=True)}\n\n"
            f"Mode:\n{tag_mode}\n"
            f"Guideline:\n{self._mode_guide(tag_mode)}\n\n"
            f"Maximum tag count:\n{int(max_tags_per_cut)}\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            "Rules:\n"
            "- Return one single comma-separated line\n"
            "- No numbering\n"
            "- No explanation\n"
            "- Avoid duplicates\n"
            "- Prefer concrete and reusable tags\n"
            "- Focus only on this single cut\n"
            "- Match the requested output language strictly\n\n"
            f"Cut:\n{cut_text}"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip().strip(",")

    def _join_all_tags(self, tags: list[str]) -> str:
        return "\n\n".join([f"[tag_{i+1}]\n{tag}" for i, tag in enumerate(tags) if tag.strip()])

    def _generate_one(self, loaded, cut_text, tag_mode, language, max_tags_per_cut, extra_requirements, max_tokens, temperature, top_p):
        if not str(cut_text).strip():
            return ""
        response = loaded.model.create_chat_completion(
            messages=[
                {"role": "system", "content": f"{DEFAULT_CUT_TAGS_SYSTEM_PROMPT} {output_language_instruction(language, tag_mode=True)}"},
                {"role": "user", "content": self._build_instruction(str(cut_text), str(tag_mode), str(language), int(max_tags_per_cut), str(extra_requirements))},
            ],
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            stop=STOP_TOKENS,
        )
        return self._clean_text(response["choices"][0]["message"]["content"])

    def generate_cut_tags(self, cut_1, cut_2, cut_3, cut_4, cut_5, cut_6, cut_7, cut_8, cut_count, tag_mode, language, max_tags_per_cut, extra_requirements, save_dir, save_name, model_path, load_strategy, max_tokens, temperature, top_p):
        count = max(1, min(int(cut_count), MAX_CUTS))
        cuts = [str(cut_1).strip(), str(cut_2).strip(), str(cut_3).strip(), str(cut_4).strip(), str(cut_5).strip(), str(cut_6).strip(), str(cut_7).strip(), str(cut_8).strip()][:count]
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "cut_tags")
        json_path = str(base_dir / f"{save_name_out}_cut_tags.json")
        if not any(c.strip() for c in cuts):
            tags = [""] * MAX_CUTS
            write_text(base_dir / f"{save_name_out}_cut_tags.txt", "")
            write_json(base_dir / f"{save_name_out}_cut_tags.json", {
                "save_name": save_name_out,
                "node": "cut_tags",
                "cut_count": count,
                "inputs": {"save_dir": base_dir_str},
                "outputs": {f"tag_{i+1}": tags[i] for i in range(MAX_CUTS)},
            })
            return tuple(tags + ["", save_name_out, count, json_path])

        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            tags = []
            for cut_text in cuts:
                tags.append(self._generate_one(loaded, cut_text, tag_mode, language, max_tags_per_cut, extra_requirements, max_tokens, temperature, top_p))
            while len(tags) < MAX_CUTS:
                tags.append("")
            all_cut_tags = self._join_all_tags(tags[:count])
            txt_path = write_text(base_dir / f"{save_name_out}_cut_tags.txt", all_cut_tags)
            write_json(base_dir / f"{save_name_out}_cut_tags.json", {
                "save_name": save_name_out,
                "node": "cut_tags",
                "cut_count": count,
                "inputs": {
                    "tag_mode": str(tag_mode),
                    "language": str(language),
                    "max_tags_per_cut": int(max_tags_per_cut),
                    "extra_requirements": str(extra_requirements),
                    "save_dir": base_dir_str,
                    "model_path": str(model_path),
                    "load_strategy": str(load_strategy),
                    "max_tokens": int(max_tokens),
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                },
                "outputs": {**{f"tag_{i+1}": tags[i] for i in range(MAX_CUTS)}, "all_cut_tags": all_cut_tags, "text_path": txt_path},
            })
            return tuple(tags[:MAX_CUTS] + [all_cut_tags, save_name_out, count, json_path])
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
