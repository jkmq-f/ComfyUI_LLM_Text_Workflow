from __future__ import annotations

from pathlib import Path

from ..utils.io_utils import sanitize_save_name, write_json, write_text


class LLMSaveTextNode:
    CATEGORY = "text"
    FUNCTION = "save_text"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("saved_text", "saved_path")
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True}),
                "save_name": ("STRING", {"default": "llm_text", "multiline": False}),
                "output_dir": ("STRING", {"default": "./llm_saved_text", "multiline": False}),
                "extension": (["txt", "md", "json"], {"default": "txt"}),
                "add_timestamp": ("BOOLEAN", {"default": True}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _resolve_path(self, output_dir: str, save_name: str, extension: str, add_timestamp: bool) -> Path:
        out_dir = Path(str(output_dir or "./llm_saved_text")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        base_name = sanitize_save_name(save_name) or "llm_text"
        if add_timestamp:
            from datetime import datetime
            base_name = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return out_dir / f"{base_name}.{extension}"

    def save_text(self, text, save_name, output_dir, extension, add_timestamp):
        path = self._resolve_path(output_dir, save_name, extension, bool(add_timestamp))
        content = str(text or "")
        if str(extension) == "json":
            write_json(path, {"text": content})
        else:
            write_text(path, content)
        return (content, str(path))


class LLMSaveText8Node:
    CATEGORY = "text"
    FUNCTION = "save_text_8"
    RETURN_TYPES = (
        "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING",
    )
    RETURN_NAMES = (
        "path_1", "path_2", "path_3", "path_4",
        "path_5", "path_6", "path_7", "path_8",
        "all_paths", "summary_text",
    )
    OUTPUT_NODE = True
    MAX_INPUTS = 8

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_1": ("STRING", {"default": "", "multiline": True}),
                "text_2": ("STRING", {"default": "", "multiline": True}),
                "text_3": ("STRING", {"default": "", "multiline": True}),
                "text_4": ("STRING", {"default": "", "multiline": True}),
                "text_5": ("STRING", {"default": "", "multiline": True}),
                "text_6": ("STRING", {"default": "", "multiline": True}),
                "text_7": ("STRING", {"default": "", "multiline": True}),
                "text_8": ("STRING", {"default": "", "multiline": True}),
                "input_count": ("INT", {"default": 8, "min": 1, "max": 8, "step": 1}),
                "base_name": ("STRING", {"default": "llm_text", "multiline": False}),
                "output_dir": ("STRING", {"default": "./llm_saved_text", "multiline": False}),
                "extension": (["txt", "md", "json"], {"default": "txt"}),
                "add_timestamp": ("BOOLEAN", {"default": True}),
                "skip_empty": ("BOOLEAN", {"default": True}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _path_for_index(self, output_dir: str, base_name: str, extension: str, add_timestamp: bool, index: int) -> Path:
        out_dir = Path(str(output_dir or "./llm_saved_text")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        base = sanitize_save_name(base_name) or "llm_text"
        if add_timestamp:
            from datetime import datetime
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base = f"{base}_{stamp}"
        return out_dir / f"{base}_{index}.{extension}"

    def save_text_8(self, text_1, text_2, text_3, text_4, text_5, text_6, text_7, text_8, input_count, base_name, output_dir, extension, add_timestamp, skip_empty):
        texts = [str(text_1), str(text_2), str(text_3), str(text_4), str(text_5), str(text_6), str(text_7), str(text_8)]
        count = max(1, min(int(input_count), self.MAX_INPUTS))
        paths = [""] * self.MAX_INPUTS
        summary = []
        for i, content in enumerate(texts[:count], start=1):
            if bool(skip_empty) and not content.strip():
                continue
            path = self._path_for_index(output_dir, base_name, extension, bool(add_timestamp), i)
            if str(extension) == "json":
                write_json(path, {"index": i, "text": content})
            else:
                write_text(path, content)
            paths[i-1] = str(path)
            summary.append(f"[{i}] {path}")
        all_paths = "\n".join([p for p in paths[:count] if p])
        summary_text = "\n".join(summary)
        return tuple(paths + [all_paths, summary_text])
