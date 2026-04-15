from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

TIMESTAMP_SUFFIX_RE = re.compile(r"_\d{8}_\d{6}$")
TIMESTAMP_PREFIX_RE = re.compile(r"^\d{8}_\d{6}(?:_|$)")


def sanitize_save_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or ""


def has_timestamp_suffix(value: str) -> bool:
    return bool(TIMESTAMP_SUFFIX_RE.search(str(value or "").strip()))


def has_timestamp_prefix(value: str) -> bool:
    return bool(TIMESTAMP_PREFIX_RE.match(str(value or "").strip()))


def ensure_save_context(save_dir: str, save_name: str, prefix: str) -> tuple[str, str, Path]:
    base_dir = Path((save_dir or "./llm_story_outputs").strip()).expanduser()
    base_dir.mkdir(parents=True, exist_ok=True)

    clean_name = sanitize_save_name(save_name)
    if clean_name:
        if has_timestamp_suffix(clean_name) or has_timestamp_prefix(clean_name):
            final_name = clean_name
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_name = f"{timestamp}_{clean_name}"
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        final_name = f"{timestamp}_{sanitize_save_name(prefix) or 'project'}"

    return str(base_dir), final_name, base_dir


def write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")
    return str(path)


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
