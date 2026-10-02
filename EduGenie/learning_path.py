"""Learning path / recommendations module (Google Gemini)."""

import gemini_client

SYSTEM_PROMPT = (
    "You are EduGenie, an AI tutor who designs practical, structured study "
    "plans. Be specific and realistic. Recommend only well-known resource "
    "types or widely recognized titles and platforms; do not invent URLs."
)


def get_learning_recommendations(topic: str) -> str:
    """Return a beginner -> advanced learning path for `topic` as Markdown."""
    prompt = f"""The student wants to learn about: {topic}.

Create a structured, adaptive learning path with these sections:
## Beginner
## Intermediate
## Advanced

For each level include: key topics (in the order to learn them), an estimated
time to complete, one practice idea, and useful resources (videos, articles,
books or courses). Finish with a short "Adaptive learning tips" list.
Use Markdown headings and '- ' bullets."""
    return gemini_client.generate_text(prompt, system=SYSTEM_PROMPT)
