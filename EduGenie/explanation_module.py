"""Concept explanation module.

Primary engine : MBZUAI/LaMini-Flan-T5-783M running locally (CPU-friendly).
Fallback engine: Google Gemini, used when the local model's dependencies
                 (torch / transformers) are not installed or the model fails.

Choose the engine with EXPLAINER_BACKEND in .env:
    auto   (default) - local model if installed, otherwise Gemini
    local            - local model only (errors if it cannot run)
    gemini           - Gemini only (no model download needed)
"""

from __future__ import annotations

import importlib.util
import logging
import os
import threading

import gemini_client
from gemini_client import AIServiceError

logger = logging.getLogger("edugenie.explanation")

LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "MBZUAI/LaMini-Flan-T5-783M")

_lock = threading.Lock()
_tokenizer = None
_model = None


def _backend() -> str:
    value = os.getenv("EXPLAINER_BACKEND", "auto").strip().lower()
    return value if value in {"auto", "local", "gemini"} else "auto"


def local_model_available() -> bool:
    """True if the optional local-model dependencies are installed."""
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


def _load_local_model():
    """Lazily load the tokenizer/model once (first call downloads ~3 GB)."""
    global _tokenizer, _model
    with _lock:
        if _model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            logger.info("Loading local model %s (first run downloads it)...", LOCAL_MODEL_NAME)
            _tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_NAME)
            _model = AutoModelForSeq2SeqLM.from_pretrained(LOCAL_MODEL_NAME)
            _model.eval()
    return _tokenizer, _model


def _explain_local(topic: str) -> str:
    import torch

    tokenizer, model = _load_local_model()
    prompt = f"Explain {topic} in simple words so a beginner student can understand it."
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            num_beams=4,
            no_repeat_ngram_size=3,  # avoids the repeated sentences small models produce
            repetition_penalty=1.2,
            early_stopping=True,
        )
    text = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
    if not text:
        raise AIServiceError("The local model returned an empty explanation.")
    return text


def _explain_gemini(topic: str) -> str:
    return gemini_client.generate_text(
        f"Explain '{topic}' in simple, beginner-friendly language in one or two "
        "short paragraphs. Use a relatable analogy if it helps.",
        system="You are EduGenie, an AI tutor who explains concepts clearly and simply.",
    )


def explain(topic: str) -> tuple[str, str]:
    """Return (explanation, engine) where engine is 'local' or 'gemini'."""
    backend = _backend()

    if backend == "gemini":
        return _explain_gemini(topic), "gemini"

    if backend == "local":
        if not local_model_available():
            raise AIServiceError(
                "EXPLAINER_BACKEND=local but torch/transformers are not installed. "
                "Run: pip install -r requirements-local.txt"
            )
        return _explain_local(topic), "local"

    # auto
    if local_model_available():
        try:
            return _explain_local(topic), "local"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Local explainer failed (%s); falling back to Gemini.", exc)
    return _explain_gemini(topic), "gemini"


def explain_topic(topic: str) -> str:
    """Return a simple explanation of `topic` (engine chosen automatically)."""
    return explain(topic)[0]
