"""Shared Google Gemini client for EduGenie.

Every AI module (Q&A, quiz, summary, learning path, explanation fallback) calls
`generate_text()` from here, so API-key handling, model selection and error
translation live in exactly one place.

Uses the current `google-genai` SDK (the older `google-generativeai` package
and the `gemini-1.5-*` models used in the original project write-up have been
retired).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("edugenie.gemini")

# Override with GEMINI_MODEL in your .env file if Google renames/retires models.
DEFAULT_MODEL = "gemini-3.5-flash"


class AIServiceError(Exception):
    """Raised when the AI backend cannot produce a usable answer."""


class MissingAPIKeyError(AIServiceError):
    """Raised when no Gemini API key has been configured."""


def get_model_name() -> str:
    return (os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _api_key() -> str:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    # Treat the placeholder from .env.example as "not set".
    if key.lower().startswith("your_") or key.lower() == "changeme":
        return ""
    return key


def is_configured() -> bool:
    return bool(_api_key())


@lru_cache(maxsize=1)
def _get_client(api_key: str):
    from google import genai  # imported lazily so tests/imports work without a key

    return genai.Client(api_key=api_key)


def generate_text(
    prompt: str,
    *,
    system: Optional[str] = None,
    json_output: bool = False,
) -> str:
    """Send `prompt` to Gemini and return the response text.

    Raises AIServiceError (or MissingAPIKeyError) with a human-readable message
    that is safe to show directly in the web UI.
    """
    key = _api_key()
    if not key:
        raise MissingAPIKeyError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env, paste your "
            "key from https://aistudio.google.com/apikey and restart the server."
        )

    from google.genai import types

    config_kwargs = {}
    if system:
        config_kwargs["system_instruction"] = system
    if json_output:
        config_kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    model = get_model_name()
    try:
        response = _get_client(key).models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as exc:  # noqa: BLE001 - translate every SDK error
        raise AIServiceError(_friendly_error(exc, model)) from exc

    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise AIServiceError(
            "Gemini returned an empty response (it may have been blocked by a "
            "safety filter). Try rephrasing your input."
        )
    return text


def _friendly_error(exc: Exception, model: str) -> str:
    code = getattr(exc, "code", None)
    detail = getattr(exc, "message", None) or str(exc)
    logger.error("Gemini request failed (%s): %s", code, detail)

    lowered = detail.lower()
    if code == 400 and ("api key" in lowered or "api_key" in lowered):
        return "Gemini rejected the API key. Check GEMINI_API_KEY in your .env file."
    if code in (401, 403):
        return (
            f"Gemini denied the request (HTTP {code}). Check that GEMINI_API_KEY is valid, "
            "the Gemini API is enabled for it, and your network can reach "
            f"generativelanguage.googleapis.com. Details: {detail}"
        )
    if code == 404:
        return (
            f"Gemini model '{model}' was not found. Set GEMINI_MODEL in your .env "
            "file to a model that is currently available (see https://ai.google.dev/gemini-api/docs/models)."
        )
    if code == 429:
        return "Gemini rate limit or quota reached. Wait a moment and try again."
    if code and int(code) >= 500:
        return "Gemini is temporarily unavailable. Please try again shortly."
    return f"Gemini request failed: {detail}"
