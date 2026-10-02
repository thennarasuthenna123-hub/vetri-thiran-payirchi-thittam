"""Question answering module (Google Gemini)."""

import gemini_client

SYSTEM_PROMPT = (
    "You are EduGenie, a friendly and accurate AI tutor for students of all "
    "levels. Answer the student's question clearly and concisely (usually 2-5 "
    "sentences). If a short example helps, include one. If the question is "
    "ambiguous, answer the most likely meaning and say so. Plain text or light "
    "Markdown only."
)


def answer_question_with_gemini(question: str) -> str:
    """Return a concise, student-friendly answer to `question`."""
    return gemini_client.generate_text(
        f"Student question: {question}", system=SYSTEM_PROMPT
    )
