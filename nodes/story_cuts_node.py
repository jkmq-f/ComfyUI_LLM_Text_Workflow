from __future__ import annotations

import json
import re

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_CUTS_SYSTEM_PROMPT = (
    "You are a visual scene planner for image-to-video and text-to-video prompting. "
    "Split the given story into sequential cuts. "
    "Each cut must be strongly visual, concrete, and directly usable as a generation prompt. "
    "Prefer visible content over abstract plot summary. "
    "If details are missing, invent visually coherent details instead of asking questions. "
    "Do not ask questions. "
    "Return only valid JSON."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]
MAX_CUTS = 8


class LLMStoryCutsNode:
    CATEGORY = "text"
    FUNCTION = "generate_cuts"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("cut_1", "cut_2", "cut_3", "cut_4", "cut_5", "cut_6", "cut_7", "cut_8", "save_name_out", "cut_count_out", "cuts_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "story_text": ("STRING", {"default": "", "multiline": True}),
                "cut_count": ("INT", {"default": 4, "min": 1, "max": MAX_CUTS, "step": 1}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "style": (["scene_description", "video_prompt", "cinematic_video_prompt", "shot_prompt_dense", "simple_beat_sheet"], {"default": "cinematic_video_prompt"}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 1280, "min": 128, "max": 4096, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.45, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _style_guide(self, style: str) -> str:
        guides = {
            "scene_description": "Each cut should be 1 to 3 sentences describing what is visibly happening in order. Focus on visible action, place, and atmosphere.",
            "video_prompt": "Each cut should read like a compact video generation prompt. Include subject, environment, visible action, mood, and one useful camera cue.",
            "cinematic_video_prompt": "Each cut should be a strong cinematic visual prompt in one dense paragraph. Include subject, wardrobe or appearance if relevant, environment, visible action, camera framing, lens or movement, lighting, color mood, and atmospheric details. Avoid abstract summary and write only things that can be seen on screen.",
            "shot_prompt_dense": "Each cut should be a dense shot prompt optimized for generation. Describe composition, foreground and background, character pose or motion, camera angle, depth, lighting, texture, and emotional tone through visible details. Write compactly but with high visual density.",
            "simple_beat_sheet": "Each cut should summarize the story beat briefly and clearly in 1 to 2 sentences. Keep it readable and sequential.",
        }
        return guides.get(str(style), guides["cinematic_video_prompt"])

    def _rules_for_style(self, style: str) -> str:
        if style == "scene_description":
            return "- Each cut should be 1 to 3 sentences\n- Describe visible events in order\n- Keep wording natural and clear\n"
        if style == "video_prompt":
            return "- Write each cut like a directly usable video prompt\n- Include visible subject, environment, action, and mood\n- Include one concise camera cue\n- Avoid plot-summary language\n"
        if style == "cinematic_video_prompt":
            return "- Write each cut as one dense visual paragraph\n- Include visible subject, setting, action, camera framing or movement, lighting, and color atmosphere\n- Favor cinematic and screen-visible details over explanation\n- Keep continuity from cut to cut\n- Avoid vague phrases like 'something happens' or 'dramatic scene'\n"
        if style == "shot_prompt_dense":
            return "- Write each cut as a dense generation-ready shot prompt\n- Include composition, angle, motion, depth, texture, and lighting\n- Make each cut self-contained and strongly visual\n- Avoid non-visual psychology unless shown through expression or action\n"
        return "- Keep each beat brief and clear\n- Preserve story order\n"

    def _build_instruction(self, story_text, cut_count, language, style, extra_requirements) -> str:
        lang = normalize_output_language(language)
        return (
            f"Split the following story into exactly {int(cut_count)} cuts.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, json_mode=True)}\n\n"
            f"Style:\n{style}\n"
            f"Guideline:\n{self._style_guide(style)}\n\n"
            "Core intent:\n"
            "Turn the story into visually strong cuts that can be reused for video generation.\n"
            "When possible, convert narration into visible staging, motion, framing, light, weather, texture, and atmosphere.\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            "Rules:\n"
            "- Return valid JSON only\n"
            '- Use this schema exactly: {"cuts": ["cut text 1", "cut text 2"]}\n'
            f"- The array must contain exactly {int(cut_count)} strings\n"
            "- Keep the cuts in story order\n"
            "- Keep the JSON keys in English exactly as shown\n"
            "- Write each cut string in the requested output language only\n"
            "- Do not add markdown fences\n"
            "- Do not add explanation\n"
            "- Do not ask for more details\n"
            "- If the story lacks visual detail, invent concrete visual detail naturally\n"
            "- Each cut should be self-contained and readable on its own\n"
            f"{self._rules_for_style(style)}"
            f"Story:\n{story_text}"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip()

    def _extract_json(self, text: str) -> dict:
        cleaned = self._clean_text(text)
        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                return json.loads(match.group(0))
            raise

    def _fallback_split(self, story_text: str, cut_count: int) -> list[str]:
        text = (story_text or "").strip()
        if not text:
            return [""] * cut_count
        normalized = text.replace("\r\n", "\n")
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", normalized) if p.strip()]
        if len(paragraphs) >= cut_count:
            base = paragraphs[:cut_count]
        else:
            sentences = [s.strip() for s in re.split(r"(?<=[。！？!?\.])\s+", normalized) if s.strip()]
            if not sentences:
                sentences = [normalized]
            groups = [[] for _ in range(cut_count)]
            for i, sentence in enumerate(sentences):
                groups[min(i * cut_count // max(len(sentences), 1), cut_count - 1)].append(sentence)
            base = [" ".join(group).strip() for group in groups]
        return [item if item else "" for item in base]

    def _normalize_cuts(self, cuts, story_text: str, cut_count: int) -> list[str]:
        if not isinstance(cuts, list):
            cuts = []
        normalized = [str(c).strip() for c in cuts if str(c).strip()]
        if len(normalized) < cut_count:
            for item in self._fallback_split(story_text, cut_count):
                if len(normalized) >= cut_count:
                    break
                if item:
                    normalized.append(item)
        normalized = normalized[:cut_count]
        while len(normalized) < cut_count:
            normalized.append("")
        return normalized

    def generate_cuts(self, story_text, cut_count, language, style, extra_requirements, save_dir, save_name, model_path, load_strategy, max_tokens, temperature, top_p):
        count = max(1, min(int(cut_count), MAX_CUTS))
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "cuts")
        json_path = str(base_dir / f"{save_name_out}_cuts.json")
        if not str(story_text).strip():
            cuts = [""] * MAX_CUTS
            write_text(base_dir / f"{save_name_out}_cuts.txt", "")
            write_json(base_dir / f"{save_name_out}_cuts.json", {"save_name": save_name_out, "node": "story_cuts", "cut_count": count, "inputs": {"save_dir": base_dir_str}, "outputs": {f"cut_{i+1}": cuts[i] for i in range(MAX_CUTS)}})
            return tuple(cuts + [save_name_out, count, json_path])
        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": f"{DEFAULT_CUTS_SYSTEM_PROMPT} {output_language_instruction(language, json_mode=True)}"},
                    {"role": "user", "content": self._build_instruction(str(story_text), count, str(language), str(style), str(extra_requirements))},
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            raw_text = response["choices"][0]["message"]["content"]
            try:
                data = self._extract_json(raw_text)
                cuts = self._normalize_cuts(data.get("cuts", []), str(story_text), count)
            except Exception:
                cuts = self._normalize_cuts([], str(story_text), count)
            while len(cuts) < MAX_CUTS:
                cuts.append("")
            txt = "\n\n".join([f"[cut_{i+1}]\n{cuts[i]}" for i in range(count) if cuts[i].strip()])
            txt_path = write_text(base_dir / f"{save_name_out}_cuts.txt", txt)
            write_json(base_dir / f"{save_name_out}_cuts.json", {
                "save_name": save_name_out,
                "node": "story_cuts",
                "cut_count": count,
                "inputs": {"language": str(language), "style": str(style), "extra_requirements": str(extra_requirements), "save_dir": base_dir_str, "model_path": str(model_path), "load_strategy": str(load_strategy), "max_tokens": int(max_tokens), "temperature": float(temperature), "top_p": float(top_p)},
                "outputs": {**{f"cut_{i+1}": cuts[i] for i in range(MAX_CUTS)}, "text_path": txt_path},
            })
            return tuple(cuts[:MAX_CUTS] + [save_name_out, count, json_path])
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
