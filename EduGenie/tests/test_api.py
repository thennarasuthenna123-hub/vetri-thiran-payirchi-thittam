"""EduGenie tests. Gemini is mocked, so no API key or network is needed."""

import json

import pytest
from fastapi.testclient import TestClient

import gemini_client
import quiz_module
from gemini_client import AIServiceError, MissingAPIKeyError
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def force_gemini_explainer(monkeypatch):
    """Keep tests fast: never load the local T5 model."""
    monkeypatch.setenv("EXPLAINER_BACKEND", "gemini")


@pytest.fixture
def fake_gemini(monkeypatch):
    """Replace gemini_client.generate_text with a stub that records prompts."""
    calls = []

    def _install(reply):
        def fake(prompt, *, system=None, json_output=False):
            calls.append({"prompt": prompt, "system": system, "json_output": json_output})
            return reply(prompt) if callable(reply) else reply

        monkeypatch.setattr(gemini_client, "generate_text", fake)
        return calls

    return _install


GOOD_QUIZ = [
    {"question": f"Question {i}?", "options": ["A1", "B1", "C1", "D1"], "answer": "B1"}
    for i in range(1, 4)
]


# ---------------------------------------------------------------- pages
def test_home_page_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "EduGenie" in r.text
    assert "/static/script.js" in r.text


def test_static_assets_served():
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/script.js").status_code == 200


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {"gemini_configured", "gemini_model", "local_model_installed"} <= body.keys()


# ---------------------------------------------------------------- /qa
def test_qa_returns_answer(fake_gemini):
    calls = fake_gemini("The Pacific Ocean.")
    r = client.get("/qa", params={"question": "Which is the largest ocean?"})
    assert r.status_code == 200
    assert r.json()["answer"] == "The Pacific Ocean."
    assert "largest ocean" in calls[0]["prompt"]


def test_qa_requires_question():
    assert client.get("/qa").status_code == 400
    assert client.get("/qa", params={"question": "   "}).status_code == 400


# ---------------------------------------------------------------- /explain
def test_explain_ok_with_and_without_trailing_slash(fake_gemini):
    fake_gemini("Photosynthesis is how plants make food from light.")
    for url in ("/explain", "/explain/"):
        r = client.post(url, json={"topic": "Photosynthesis"})
        assert r.status_code == 200
        body = r.json()
        assert body["topic"] == "Photosynthesis"
        assert "plants" in body["explanation"]
        assert body["engine"] == "gemini"


def test_explain_rejects_empty_topic():
    r = client.post("/explain", json={"topic": "  "})
    assert r.status_code == 400
    assert "topic" in r.json()["error"].lower()


def test_explain_rejects_missing_body():
    assert client.post("/explain", json={}).status_code == 400


# ---------------------------------------------------------------- /summarize
def test_summarize_ok(fake_gemini):
    calls = fake_gemini("Short summary.")
    r = client.post("/summarize/", json={"text": "A very long passage. " * 20})
    assert r.status_code == 200
    assert r.json() == {"summary": "Short summary."}
    assert "Passage:" in calls[0]["prompt"]


def test_summarize_rejects_empty_and_oversized():
    assert client.post("/summarize", json={"text": ""}).status_code == 400
    too_long = client.post("/summarize", json={"text": "x" * 9000})
    assert too_long.status_code == 400
    assert "at most" in too_long.json()["error"]


# ---------------------------------------------------------------- /quiz
def test_quiz_ok(fake_gemini):
    fake_gemini(json.dumps(GOOD_QUIZ))
    r = client.post("/quiz", json={"text": "Solar System"})
    assert r.status_code == 200
    quiz = r.json()["quiz"]
    assert len(quiz) == 3
    for q in quiz:
        assert len(q["options"]) == 4
        assert q["answer"] in q["options"]


def test_quiz_handles_markdown_fences(fake_gemini):
    fake_gemini("```json\n" + json.dumps(GOOD_QUIZ) + "\n```")
    assert client.post("/quiz", json={"text": "Topic"}).status_code == 200


def test_quiz_retries_once_on_bad_json(fake_gemini):
    replies = iter(["not json at all", json.dumps(GOOD_QUIZ)])
    calls = fake_gemini(lambda prompt: next(replies))
    r = client.post("/quiz", json={"text": "Topic"})
    assert r.status_code == 200
    assert len(calls) == 2


def test_quiz_error_after_two_bad_replies(fake_gemini):
    fake_gemini("still not json")
    r = client.post("/quiz", json={"text": "Topic"})
    assert r.status_code == 502
    assert "quiz" in r.json()["error"].lower()


def test_quiz_requires_text():
    assert client.post("/quiz", json={"text": ""}).status_code == 400


# ---------------------------------------------------------------- /learn/recommendations
def test_learning_path_ok(fake_gemini):
    fake_gemini("## Beginner\n- Basics")
    r = client.get("/learn/recommendations", params={"topic": "SQL"})
    assert r.status_code == 200
    body = r.json()
    assert body["topic"] == "SQL"
    assert "Beginner" in body["recommendation"]


def test_learning_path_requires_topic():
    assert client.get("/learn/recommendations").status_code == 400


# ---------------------------------------------------------------- error mapping
def test_missing_api_key_gives_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    r = client.get("/qa", params={"question": "hi"})
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["error"]


def test_ai_failure_gives_502(monkeypatch):
    def boom(*a, **k):
        raise AIServiceError("Gemini rate limit or quota reached.")

    monkeypatch.setattr(gemini_client, "generate_text", boom)
    r = client.get("/qa", params={"question": "hi"})
    assert r.status_code == 502
    assert "rate limit" in r.json()["error"]


def test_placeholder_key_counts_as_missing(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_api_key_here")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert gemini_client.is_configured() is False
    with pytest.raises(MissingAPIKeyError):
        gemini_client.generate_text("hello")


# ---------------------------------------------------------------- quiz unit tests
def test_clean_json_block_variants():
    assert quiz_module.clean_json_block('```json\n[{"a": 1}]\n```') == '[{"a": 1}]'
    assert quiz_module.clean_json_block('```\n[1]\n```') == "[1]"
    assert quiz_module.clean_json_block('Here you go: [1, 2] enjoy') == "[1, 2]"
    assert quiz_module.clean_json_block("[1]") == "[1]"


def test_validate_maps_letter_and_case_insensitive_answers():
    base = {"question": "Q?", "options": ["Red", "Green", "Blue", "Yellow"]}
    letter = [dict(base, answer="C")] * 3
    assert quiz_module._validate(letter)[0]["answer"] == "Blue"
    lower = [dict(base, answer="green")] * 3
    assert quiz_module._validate(lower)[0]["answer"] == "Green"


def test_validate_rejects_bad_shapes():
    base = {"question": "Q?", "options": ["a", "b", "c", "d"], "answer": "a"}
    with pytest.raises(quiz_module.QuizGenerationError):
        quiz_module._validate([base] * 2)  # too few questions
    with pytest.raises(quiz_module.QuizGenerationError):
        quiz_module._validate([dict(base, options=["a", "b", "c"])] * 3)  # too few options
    with pytest.raises(quiz_module.QuizGenerationError):
        quiz_module._validate([dict(base, answer="zzz")] * 3)  # answer not in options
