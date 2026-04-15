from __future__ import annotations

import json
import re

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT = (
    "You turn cut descriptions into strong video generation prompts. "
    "Prioritize visible, filmable details. "
    "If details are missing, infer coherent details instead of asking questions. "
    "Keep each prompt self-contained and useful for generation. "
    "Return only valid JSON."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]
MAX_CUTS = 8


class LLMVideoPromptNode:
    CATEGORY = "text"
    FUNCTION = "generate_video_prompts"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("prompt_1", "prompt_2", "prompt_3", "prompt_4", "prompt_5", "prompt_6", "prompt_7", "prompt_8", "all_prompts", "save_name_out", "cut_count_out", "video_prompts_json_path")
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
                "language": (["Japanese", "English"], {"default": "English"}),
                "prompt_style": (["cinematic_video_prompt", "shot_prompt_dense", "simple_visual_prompt", "sora_like", "ltx_like"], {"default": "cinematic_video_prompt"}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 2048, "min": 128, "max": 8192, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.45, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _style_guide(self, prompt_style: str) -> str:
        guides = {
            "cinematic_video_prompt": "Each prompt should be a dense cinematic paragraph. Include subject, environment, visible action, framing, camera behavior, lighting, color mood, and atmospheric details.",
            "shot_prompt_dense": "Each prompt should be a compact but high-density shot prompt. Include composition, foreground and background, motion, depth, texture, and lighting.",
            "simple_visual_prompt": "Each prompt should be clean and simple. Focus on who or what is visible, where it is, and what is happening.",
            "sora_like": "Each prompt should read like a polished text-to-video prompt. Favor visible staging, camera phrasing, environmental motion, and precise image-first wording.",
            "ltx_like": "Each prompt should read like a practical image-to-video or video model prompt. Use direct and concrete visual wording, strong subject clarity, and controllable camera details.",
        }
        return guides.get(str(prompt_style), guides["cinematic_video_prompt"])

    def _style_rules(self, prompt_style: str) -> str:
        if prompt_style == "cinematic_video_prompt":
            return "- Write one dense paragraph per cut\n- Include visible subject, environment, action, framing, camera, lighting, and color mood\n- Favor concrete filmable detail over explanation\n"
        if prompt_style == "shot_prompt_dense":
            return "- Write compact, dense generation-ready shot prompts\n- Include composition, angle, motion, depth, texture, and light\n- Keep every prompt self-contained\n"
        if prompt_style == "simple_visual_prompt":
            return "- Keep prompts simple and direct\n- Use clear visual nouns and verbs\n- Avoid unnecessary flourish\n"
        if prompt_style == "sora_like":
            return "- Write image-first prompts that feel immediately visual\n- Include staging, camera, light, atmosphere, and visible motion\n- Avoid bullet points or labels\n"
        return "- Write practical controllable prompts\n- Keep the subject clear and visible\n- Include concise camera and motion cues\n"

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

    def _build_instruction(self, cuts: list[str], language: str, prompt_style: str, extra_requirements: str) -> str:
        lang = normalize_output_language(language)
        cuts_block = "\n".join(f"{i+1}. {cut}" for i, cut in enumerate(cuts))
        return (
            f"Convert the following cut descriptions into exactly {len(cuts)} video prompts.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, json_mode=True)}\n\n"
            f"Style:\n{prompt_style}\n"
            f"Guideline:\n{self._style_guide(prompt_style)}\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            "Rules:\n"
            "- Return valid JSON only\n"
            "- Use this schema exactly: {\"prompts\": [\"prompt 1\", \"prompt 2\"]}\n"
            f"- The array must contain exactly {len(cuts)} strings\n"
            "- Keep the prompts aligned with the same cut order\n"
            "- Keep the JSON keys in English exactly as shown\n"
            "- Write each prompt string in the requested output language only\n"
            "- Do not add markdown fences\n"
            "- Do not explain\n"
            "- Do not ask questions\n"
            "- If a cut is underspecified, invent coherent visual detail naturally\n"
            "- Each prompt must be usable on its own\n"
            f"{self._style_rules(prompt_style)}"
            f"Cuts:\n{cuts_block}"
        )

    def _normalize_prompts(self, prompts, cuts: list[str]) -> list[str]:
        if not isinstance(prompts, list):
            prompts = []
        normalized = [str(p).strip() for p in prompts if str(p).strip()]
        if len(normalized) < len(cuts):
            for item in cuts:
                if len(normalized) >= len(cuts):
                    break
                if item.strip():
                    normalized.append(item.strip())
        normalized = normalized[: len(cuts)]
        while len(normalized) < len(cuts):
            normalized.append("")
        return normalized

    def _join_all_prompts(self, prompts: list[str]) -> str:
        return "\n\n".join([f"[prompt_{i+1}]\n{p}" for i, p in enumerate(prompts) if p.strip()])

    def generate_video_prompts(self, cut_1, cut_2, cut_3, cut_4, cut_5, cut_6, cut_7, cut_8, cut_count, language, prompt_style, extra_requirements, save_dir, save_name, model_path, load_strategy, max_tokens, temperature, top_p):
        count = max(1, min(int(cut_count), MAX_CUTS))
        cuts = [str(cut_1).strip(), str(cut_2).strip(), str(cut_3).strip(), str(cut_4).strip(), str(cut_5).strip(), str(cut_6).strip(), str(cut_7).strip(), str(cut_8).strip()][:count]
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "video_prompts")
        json_path = str(base_dir / f"{save_name_out}_video_prompts.json")
        if not any(c.strip() for c in cuts):
            prompts = [""] * MAX_CUTS
            write_text(base_dir / f"{save_name_out}_video_prompts.txt", "")
            write_json(base_dir / f"{save_name_out}_video_prompts.json", {"save_name": save_name_out, "node": "video_prompts", "cut_count": count, "inputs": {"save_dir": base_dir_str}, "outputs": {f"prompt_{i+1}": prompts[i] for i in range(MAX_CUTS)}})
            return tuple(prompts + ["", save_name_out, count, json_path])
        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": f"{DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT} {output_language_instruction(language, json_mode=True)}"},
                    {"role": "user", "content": self._build_instruction(cuts, str(language), str(prompt_style), str(extra_requirements))},
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            raw_text = response["choices"][0]["message"]["content"]
            try:
                data = self._extract_json(raw_text)
                prompts = self._normalize_prompts(data.get("prompts", []), cuts)
            except Exception:
                prompts = self._normalize_prompts([], cuts)
            while len(prompts) < MAX_CUTS:
                prompts.append("")
            all_prompts = self._join_all_prompts(prompts[:count])
            txt_path = write_text(base_dir / f"{save_name_out}_video_prompts.txt", all_prompts)
            write_json(base_dir / f"{save_name_out}_video_prompts.json", {
                "save_name": save_name_out,
                "node": "video_prompts",
                "cut_count": count,
                "inputs": {"language": str(language), "prompt_style": str(prompt_style), "extra_requirements": str(extra_requirements), "save_dir": base_dir_str, "model_path": str(model_path), "load_strategy": str(load_strategy), "max_tokens": int(max_tokens), "temperature": float(temperature), "top_p": float(top_p)},
                "outputs": {**{f"prompt_{i+1}": prompts[i] for i in range(MAX_CUTS)}, "all_prompts": all_prompts, "text_path": txt_path},
            })
            return tuple(prompts[:MAX_CUTS] + [all_prompts, save_name_out, count, json_path])
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
