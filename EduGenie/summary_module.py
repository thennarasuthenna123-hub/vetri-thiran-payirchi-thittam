"""Summarization module (Google Gemini)."""

import gemini_client

SYSTEM_PROMPT = (
    "You are EduGenie, an AI study assistant. Summarize educational passages "
    "so a student can revise quickly. Keep every key fact, definition and "
    "number that matters, drop repetition, and never add information that is "
    "not in the passage."
)


def summarize_text(text: str) -> str:
    """Return a concise summary of `text` (short paragraph + key points)."""
    prompt = (
        "Summarize the passage below.\n"
        "Format: one short paragraph, then 3-5 bullet points of key takeaways "
        "(use '- ' for bullets).\n\n"
        f"Passage:\n{text}"
    )
    return gemini_client.generate_text(prompt, system=SYSTEM_PROMPT)
