from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch

try:
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None

ENV_LOCAL_MODEL = "LLM_MODEL_PATH"


@dataclass
class LoadedLLM:
    model: object
    model_path: str
    n_ctx: int
    n_gpu_layers: int
    threads: int
    temperature: float


_CURRENT: Optional[LoadedLLM] = None


def unload_model() -> None:
    global _CURRENT
    if _CURRENT is not None:
        try:
            del _CURRENT.model
        except Exception:
            pass
        _CURRENT = None
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass


def clear_model_cache() -> None:
    unload_model()


def resolve_model_path(local_model_path: str = "") -> str:
    explicit = Path((local_model_path or "").strip()).expanduser()
    if str(explicit):
        if explicit.is_file() and explicit.suffix.lower() == ".gguf":
            return str(explicit)
        if explicit.exists() and explicit.is_dir():
            raise FileNotFoundError(
                f"model_path must point to a .gguf file, not a directory: {explicit}"
            )
        raise FileNotFoundError(
            f"Model file was not found: {explicit}"
        )

    import os
    env_path = Path(os.environ.get(ENV_LOCAL_MODEL, "").strip()).expanduser()
    if str(env_path):
        if env_path.is_file() and env_path.suffix.lower() == ".gguf":
            return str(env_path)
        raise FileNotFoundError(
            f"{ENV_LOCAL_MODEL} must point to a .gguf file: {env_path}"
        )

    raise FileNotFoundError(
        "No model file was provided. Set model_path to a .gguf file."
    )


def load_llm_model(
    local_model_path: str,
    n_ctx: int = 8192,
    n_gpu_layers: int = -1,
    threads: int = 0,
    temperature: float = 0.2,
) -> LoadedLLM:
    global _CURRENT

    if Llama is None:
        raise RuntimeError(
            "llama_cpp is not installed. Install llama-cpp-python in the ComfyUI environment first."
        )

    model_path = resolve_model_path(local_model_path)
    use_threads = max(int(threads), 0)

    if (
        _CURRENT is not None
        and _CURRENT.model_path == model_path
        and _CURRENT.n_ctx == int(n_ctx)
        and _CURRENT.n_gpu_layers == int(n_gpu_layers)
        and _CURRENT.threads == use_threads
    ):
        return _CURRENT

    unload_model()

    kwargs = {
        "model_path": model_path,
        "n_ctx": int(n_ctx),
        "n_gpu_layers": int(n_gpu_layers),
        "verbose": False,
        "logits_all": False,
    }
    if use_threads > 0:
        kwargs["n_threads"] = use_threads
        kwargs["n_threads_batch"] = use_threads

    model = Llama(**kwargs)
    _CURRENT = LoadedLLM(
        model=model,
        model_path=model_path,
        n_ctx=int(n_ctx),
        n_gpu_layers=int(n_gpu_layers),
        threads=use_threads,
        temperature=float(temperature),
    )
    return _CURRENT
