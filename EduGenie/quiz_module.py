"""Quiz generation module (Google Gemini).

Produces exactly three multiple-choice questions, each with four options and a
correct answer that is guaranteed to match one of the options.
"""

from __future__ import annotations

import json
import re
from typing import Any

import gemini_client
from gemini_client import AIServiceError

NUM_QUESTIONS = 3
NUM_OPTIONS = 4


class QuizGenerationError(AIServiceError):
    """Raised when the model's quiz output cannot be parsed or validated."""


SYSTEM_PROMPT = "You are a quiz generator for students. You output only valid JSON."


def clean_json_block(text: str) -> str:
    """Strip Markdown code fences (```json ... ```) and surrounding noise."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    # If there is still prose around the JSON, keep only the outermost [...] array.
    if not text.startswith("["):
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return text.strip()


def _validate(raw: Any) -> list[dict]:
    if isinstance(raw, dict):  # tolerate {"quiz": [...]} / {"questions": [...]}
        raw = raw.get("quiz") or raw.get("questions") or []
    if not isinstance(raw, list) or not raw:
        raise QuizGenerationError("The model did not return a list of questions.")

    quiz: list[dict] = []
    for i, item in enumerate(raw[:NUM_QUESTIONS], start=1):
        if not isinstance(item, dict):
            raise QuizGenerationError(f"Question {i} is not an object.")
        question = str(item.get("question", "")).strip()
        options = [str(o).strip() for o in (item.get("options") or [])]
        answer = str(item.get("answer", "")).strip()

        if not question:
            raise QuizGenerationError(f"Question {i} has no text.")
        if len(options) != NUM_OPTIONS or len(set(options)) != NUM_OPTIONS:
            raise QuizGenerationError(f"Question {i} must have {NUM_OPTIONS} distinct options.")

        # Make sure `answer` is exactly one of the options.
        if answer not in options:
            lowered = {o.lower(): o for o in options}
            letter = re.fullmatch(r"\(?([A-Da-d])[\).:]?", answer)
            if answer.lower() in lowered:
                answer = lowered[answer.lower()]
            elif letter:
                answer = options["ABCD".index(letter.group(1).upper())]
            else:
                raise QuizGenerationError(f"Question {i}'s answer does not match any option.")

        quiz.append({"question": question, "options": options, "answer": answer})

    if len(quiz) < NUM_QUESTIONS:
        raise QuizGenerationError(
            f"Expected {NUM_QUESTIONS} questions but the model returned {len(quiz)}."
        )
    return quiz


def generate_quiz(text: str) -> list[dict]:
    """Generate a 3-question MCQ quiz from a topic or passage.

    Returns a list like:
        [{"question": "...", "options": ["A", "B", "C", "D"], "answer": "A"}, ...]
    """
    prompt = f"""From the following topic or passage, create {NUM_QUESTIONS} multiple-choice questions.
Each question must include:
- "question": the question text
- "options": a list of exactly {NUM_OPTIONS} different answer choices (plausible distractors, no "A)"/"B)" prefixes)
- "answer": the correct answer, which must exactly match one of the options

If the input is only a short topic, base the questions on well-established facts about it.

Format your output as valid JSON only (no commentary, no Markdown), like this:
[
  {{
    "question": "What is ...?",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "answer": "Option 1"
  }}
]

Topic or passage:
{text}
"""

    last_error: Exception | None = None
    for _attempt in range(2):  # one retry if the model returns malformed JSON
        quiz_text = gemini_client.generate_text(prompt, system=SYSTEM_PROMPT, json_output=True)
        try:
            return _validate(json.loads(clean_json_block(quiz_text)))
        except (json.JSONDecodeError, QuizGenerationError) as exc:
            last_error = exc

    raise QuizGenerationError(
        f"Could not generate a valid quiz: {last_error}. Please try again."
    )
