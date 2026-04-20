from __future__ import annotations

import json
import re
from typing import Any

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_LYRICS_SYSTEM_PROMPT = (
    "You convert story material into singable song lyrics. "
    "Timing matters. Respect the requested total duration and section timing. "
    "Write natural lyrics, not a plot summary. "
    "Preserve emotional flow and strong hooks. "
    "Return only valid JSON."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]
DEFAULT_SECTION_PRESETS = {
    "short_hook_loop": [("intro", 6), ("verse_1", 18), ("chorus", 18), ("verse_2", 18), ("chorus_2", 18), ("outro", 6)],
    "verse_chorus": [("verse_1", 24), ("chorus", 20), ("verse_2", 24), ("final_chorus", 32)],
    "verse_verse_chorus": [("verse_1", 18), ("verse_2", 18), ("chorus", 20), ("verse_3", 18), ("final_chorus", 26)],
    "verse_chorus_verse_chorus": [("verse_1", 22), ("chorus", 18), ("verse_2", 22), ("final_chorus", 28)],
    "verse_chorus_bridge": [("verse_1", 20), ("chorus", 20), ("verse_2", 20), ("chorus_2", 20), ("bridge", 15), ("final_chorus", 25)],
    "verse_prechorus_chorus": [("verse_1", 22), ("prechorus", 12), ("chorus", 20), ("verse_2", 22), ("prechorus_2", 12), ("final_chorus", 32)],
    "verse_prechorus_chorus_outro": [("verse_1", 20), ("prechorus", 10), ("chorus", 18), ("verse_2", 20), ("prechorus_2", 10), ("final_chorus", 24), ("outro", 8)],
    "intro_verse_prechorus_chorus": [("intro", 8), ("verse_1", 20), ("prechorus", 10), ("chorus", 18), ("verse_2", 20), ("prechorus_2", 10), ("final_chorus", 24)],
    "intro_verse_chorus_verse_chorus_bridge_final": [("intro", 8), ("verse_1", 18), ("chorus", 16), ("verse_2", 18), ("chorus_2", 16), ("bridge", 12), ("final_chorus", 22)],
    "full_jpop": [("intro", 8), ("verse_1", 20), ("prechorus", 12), ("chorus", 20), ("verse_2", 20), ("prechorus_2", 12), ("bridge", 16), ("final_chorus", 28), ("outro", 8)],
    "hook_verse_hook": [("hook", 12), ("verse", 24), ("hook_2", 14), ("verse_2", 24), ("final_hook", 16)],
    "spoken_verse_chorus": [("spoken_intro", 10), ("verse_1", 20), ("chorus", 18), ("spoken_break", 10), ("verse_2", 18), ("final_chorus", 24)],
    "ambient_intro_verse_drop_outro": [("ambient_intro", 12), ("verse", 22), ("drop", 20), ("verse_2", 18), ("final_drop", 24), ("outro", 8)],
    "free": [("part_1", 30), ("part_2", 30), ("part_3", 30)],
}


class LLMStoryToLyricsNode:
    CATEGORY = "text"
    FUNCTION = "generate_lyrics"
    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING", "STRING")
    RETURN_NAMES = ("lyrics_text", "timing_text", "total_duration_sec", "save_name_out", "lyrics_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "story_text": ("STRING", {"default": "", "multiline": True}),
                "target_duration_sec": ("INT", {"default": 90, "min": 10, "max": 600, "step": 1}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "song_structure": ([
                    "short_hook_loop",
                    "verse_chorus",
                    "verse_verse_chorus",
                    "verse_chorus_verse_chorus",
                    "verse_chorus_bridge",
                    "verse_prechorus_chorus",
                    "verse_prechorus_chorus_outro",
                    "intro_verse_prechorus_chorus",
                    "intro_verse_chorus_verse_chorus_bridge_final",
                    "full_jpop",
                    "hook_verse_hook",
                    "spoken_verse_chorus",
                    "ambient_intro_verse_drop_outro",
                    "free",
                ], {"default": "verse_prechorus_chorus"}),
                "syllable_density": (["sparse", "balanced", "dense"], {"default": "balanced"}),
                "theme_focus": ("STRING", {"default": "core emotion, memorable hook, singable lines", "multiline": True}),
                "include_section_labels": ("BOOLEAN", {"default": True}),
                "section_label_style": (["internal_keys", "bracket_pretty", "ace_suno"], {"default": "ace_suno"}),
                "extra_requirements": ("STRING", {"default": "", "multiline": True}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 2048, "min": 128, "max": 8192, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
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
        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                return json.loads(match.group(0))
            raise

    def _scaled_sections(self, target_duration_sec: int, song_structure: str) -> list[dict[str, Any]]:
        preset = DEFAULT_SECTION_PRESETS.get(str(song_structure), DEFAULT_SECTION_PRESETS["verse_prechorus_chorus"])
        base_total = sum(max(1, int(sec)) for _, sec in preset)
        target = max(1, int(target_duration_sec))
        scaled: list[dict[str, Any]] = []
        used = 0
        for index, (name, sec) in enumerate(preset):
            if index == len(preset) - 1:
                duration = max(1, target - used)
            else:
                ratio = float(sec) / float(base_total)
                duration = max(1, int(round(target * ratio)))
                used += duration
            scaled.append({"name": str(name), "duration_sec": int(duration)})
        current_total = sum(item["duration_sec"] for item in scaled)
        if current_total != target and scaled:
            scaled[-1]["duration_sec"] = max(1, scaled[-1]["duration_sec"] + (target - current_total))
        return scaled

    def _build_instruction(
        self,
        story_text: str,
        target_duration_sec: int,
        language: str,
        song_structure: str,
        syllable_density: str,
        theme_focus: str,
        extra_requirements: str,
    ) -> str:
        lang = normalize_output_language(language)
        sections = self._scaled_sections(target_duration_sec, song_structure)
        section_lines = "\n".join([f"- {item['name']}: {item['duration_sec']} sec" for item in sections])
        density_rule = {
            "sparse": "Use fewer words per line, more breathing room, and simple repetition.",
            "balanced": "Keep line lengths moderate and singable.",
            "dense": "Use tighter phrasing and more words per section while staying singable.",
        }.get(str(syllable_density), "Keep line lengths moderate and singable.")
        return (
            f"Convert the following story into song lyrics.\n\n"
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, json_mode=True)}\n\n"
            f"Target total duration: {int(target_duration_sec)} seconds\n"
            f"Song structure: {song_structure}\n"
            f"Section timing plan:\n{section_lines}\n\n"
            f"Theme focus:\n{theme_focus}\n\n"
            f"Extra requirements:\n{extra_requirements}\n\n"
            f"Story source:\n{story_text}\n\n"
            "Rules:\n"
            "- Return valid JSON only\n"
            "- Keep the JSON keys in English exactly as shown\n"
            "- Section names like verse_1, chorus, prechorus_2, final_chorus are valid internal names\n"
            "- Do not add markdown fences\n"
            "- Do not explain\n"
            "- Do not ask questions\n"
            "- Lyrics must sound singable, not like a synopsis\n"
            "- Preserve emotional progression and a memorable hook\n"
            "- Respect the target duration and section timing as closely as possible\n"
            f"- {density_rule}\n"
            "- If the story is underspecified, invent details naturally\n"
            "- Use this exact schema: "
            '{"title":"...","total_duration_sec":90,"sections":[{"name":"verse_1","duration_sec":20,"lyrics":"..."}],"full_lyrics":"..."}'
        )

    def _normalize_sections(self, sections: Any, target_duration_sec: int, song_structure: str) -> list[dict[str, Any]]:
        planned = self._scaled_sections(target_duration_sec, song_structure)
        if not isinstance(sections, list):
            sections = []
        normalized = []
        for index, plan in enumerate(planned):
            raw = sections[index] if index < len(sections) and isinstance(sections[index], dict) else {}
            name = str(raw.get("name") or plan["name"]).strip() or plan["name"]
            lyrics = str(raw.get("lyrics") or "").strip()
            duration = raw.get("duration_sec", plan["duration_sec"])
            try:
                duration = int(duration)
            except Exception:
                duration = int(plan["duration_sec"])
            normalized.append({
                "name": name,
                "duration_sec": max(1, duration),
                "lyrics": lyrics,
            })
        total = sum(item["duration_sec"] for item in normalized)
        target = max(1, int(target_duration_sec))
        if normalized and total != target:
            normalized[-1]["duration_sec"] = max(1, normalized[-1]["duration_sec"] + (target - total))
        return normalized

    def _pretty_section_label(self, name: str, style: str) -> str:
        raw = str(name or "").strip()
        if not raw:
            return "Section"
        if str(style) == "internal_keys":
            return raw

        normalized = raw.replace("-", "_")
        pieces = [piece for piece in normalized.split("_") if piece]
        mapping = {
            "prechorus": "Pre-Chorus",
            "chorus": "Chorus",
            "verse": "Verse",
            "intro": "Intro",
            "outro": "Outro",
            "bridge": "Bridge",
            "hook": "Hook",
            "spoken": "Spoken",
            "drop": "Drop",
            "ambient": "Ambient",
            "final": "Final",
            "part": "Part",
            "break": "Break",
        }
        pretty_parts = []
        for piece in pieces:
            if piece.isdigit():
                pretty_parts.append(piece)
            else:
                pretty_parts.append(mapping.get(piece.lower(), piece.title()))
        pretty = " ".join(pretty_parts).strip()
        pretty = re.sub(r"\bPre Chorus\b", "Pre-Chorus", pretty, flags=re.IGNORECASE)
        pretty = re.sub(r"\s+", " ", pretty).strip()
        return pretty or raw

    def _full_lyrics_from_sections(self, sections: list[dict[str, Any]], include_section_labels: bool, section_label_style: str) -> str:
        blocks = []
        for item in sections:
            lyrics = str(item.get("lyrics") or "").strip()
            if not lyrics:
                continue
            if bool(include_section_labels):
                label = self._pretty_section_label(str(item.get("name") or ""), str(section_label_style))
                blocks.append(f"[{label}]\n{lyrics}")
            else:
                blocks.append(lyrics)
        return "\n\n".join(blocks).strip()

    def _timing_text(self, sections: list[dict[str, Any]]) -> str:
        lines = []
        cursor = 0
        for item in sections:
            start_sec = cursor
            end_sec = cursor + int(item["duration_sec"])
            lines.append(f"{item['name']}: {start_sec}-{end_sec}s ({item['duration_sec']}s)")
            cursor = end_sec
        return "\n".join(lines)

    def generate_lyrics(
        self,
        story_text,
        target_duration_sec,
        language,
        song_structure,
        syllable_density,
        theme_focus,
        include_section_labels,
        section_label_style,
        extra_requirements,
        save_dir,
        save_name,
        model_path,
        load_strategy,
        max_tokens,
        temperature,
        top_p,
    ):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "lyrics")
        json_path = str(base_dir / f"{save_name_out}_lyrics.json")
        target_duration_sec = int(target_duration_sec)

        if not str(story_text).strip():
            empty_sections = self._scaled_sections(target_duration_sec, str(song_structure))
            lyrics_text = self._full_lyrics_from_sections(empty_sections, bool(include_section_labels), str(section_label_style))
            timing_text = self._timing_text(empty_sections)
            write_text(base_dir / f"{save_name_out}_lyrics.txt", lyrics_text)
            write_json(
                base_dir / f"{save_name_out}_lyrics.json",
                {
                    "save_name": save_name_out,
                    "node": "story_to_lyrics",
                    "inputs": {
                        "story_text": "",
                        "target_duration_sec": target_duration_sec,
                        "song_structure": str(song_structure),
                        "include_section_labels": bool(include_section_labels),
                        "section_label_style": str(section_label_style),
                    },
                    "outputs": {
                        "lyrics_text": lyrics_text,
                        "timing_text": timing_text,
                        "total_duration_sec": target_duration_sec,
                        "sections": empty_sections,
                    },
                },
            )
            return (lyrics_text, timing_text, target_duration_sec, save_name_out, json_path)

        try:
            loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
            response = loaded.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": f"{DEFAULT_LYRICS_SYSTEM_PROMPT} {output_language_instruction(language, json_mode=True)}"},
                    {
                        "role": "user",
                        "content": self._build_instruction(
                            str(story_text),
                            target_duration_sec,
                            str(language),
                            str(song_structure),
                            str(syllable_density),
                            str(theme_focus),
                            str(extra_requirements),
                        ),
                    },
                ],
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                stop=STOP_TOKENS,
            )
            raw_text = response["choices"][0]["message"]["content"]
            try:
                data = self._extract_json(raw_text)
            except Exception:
                data = {}

            sections = self._normalize_sections(data.get("sections", []), target_duration_sec, str(song_structure))
            lyrics_text = str(data.get("full_lyrics") or "").strip()
            if not lyrics_text or bool(include_section_labels):
                lyrics_text = self._full_lyrics_from_sections(sections, bool(include_section_labels), str(section_label_style))
            timing_text = self._timing_text(sections)

            txt_path = write_text(base_dir / f"{save_name_out}_lyrics.txt", lyrics_text)
            timing_path = write_text(base_dir / f"{save_name_out}_lyrics_timing.txt", timing_text)
            write_json(
                base_dir / f"{save_name_out}_lyrics.json",
                {
                    "save_name": save_name_out,
                    "node": "story_to_lyrics",
                    "inputs": {
                        "story_text": str(story_text),
                        "target_duration_sec": int(target_duration_sec),
                        "language": str(language),
                        "song_structure": str(song_structure),
                        "syllable_density": str(syllable_density),
                        "theme_focus": str(theme_focus),
                        "include_section_labels": bool(include_section_labels),
                        "section_label_style": str(section_label_style),
                        "extra_requirements": str(extra_requirements),
                        "save_dir": base_dir_str,
                        "model_path": str(model_path),
                        "load_strategy": str(load_strategy),
                        "max_tokens": int(max_tokens),
                        "temperature": float(temperature),
                        "top_p": float(top_p),
                    },
                    "outputs": {
                        "title": str(data.get("title") or ""),
                        "total_duration_sec": int(target_duration_sec),
                        "sections": sections,
                        "formatted_sections": [
                            {
                                "name": s["name"],
                                "display_label": self._pretty_section_label(s["name"], str(section_label_style)),
                                "duration_sec": s["duration_sec"],
                                "lyrics": s["lyrics"],
                            }
                            for s in sections
                        ],
                        "lyrics_text": lyrics_text,
                        "timing_text": timing_text,
                        "text_path": txt_path,
                        "timing_path": timing_path,
                        "raw_model_output": self._clean_text(raw_text),
                    },
                },
            )
            return (lyrics_text, timing_text, int(target_duration_sec), save_name_out, json_path)
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
