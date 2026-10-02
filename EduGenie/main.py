"""EduGenie - Google Gemini powered learning assistant (FastAPI backend).

Run with:  uvicorn main:app --reload
Open:      http://127.0.0.1:8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

import explanation_module
import gemini_client
from explanation_module import explain
from gemini_client import AIServiceError, MissingAPIKeyError
from learning_path import get_learning_recommendations
from qna import answer_question_with_gemini
from quiz_module import generate_quiz
from summary_module import summarize_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="EduGenie",
    description="AI-powered learning assistant: Q&A, explanations, quizzes, summaries and learning paths.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

MAX_TOPIC_CHARS = 500
MAX_QUESTION_CHARS = 1000
MAX_TEXT_CHARS = 8000


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------
class TopicRequest(BaseModel):
    topic: str

    @field_validator("topic")
    @classmethod
    def _check_topic(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please provide a topic.")
        if len(v) > MAX_TOPIC_CHARS:
            raise ValueError(f"Topic must be at most {MAX_TOPIC_CHARS} characters.")
        return v


class TextRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _check_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please provide some text.")
        if len(v) > MAX_TEXT_CHARS:
            raise ValueError(f"Text must be at most {MAX_TEXT_CHARS} characters.")
        return v


# --------------------------------------------------------------------------
# Error handling - every error is returned as {"error": "..."}
# --------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    message = str(first.get("msg", "Invalid request.")).removeprefix("Value error, ")
    if first.get("type") == "missing":
        message = "Please provide the required input."
    return JSONResponse(status_code=400, content={"error": message})


@app.exception_handler(MissingAPIKeyError)
async def missing_key_handler(request: Request, exc: MissingAPIKeyError):
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.exception_handler(AIServiceError)
async def ai_error_handler(request: Request, exc: AIServiceError):
    return JSONResponse(status_code=502, content={"error": str(exc)})


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health():
    """Lightweight status check used by the UI and for debugging setup."""
    return {
        "status": "ok",
        "gemini_configured": gemini_client.is_configured(),
        "gemini_model": gemini_client.get_model_name(),
        "local_model_installed": explanation_module.local_model_available(),
    }


# --------------------------------------------------------------------------
# API routes (plain `def` handlers run in FastAPI's thread pool, so slow
# model calls never block the event loop)
# --------------------------------------------------------------------------
# Q&A - GET API using Gemini
@app.get("/qa")
def answer_question(
    question: str = Query(..., min_length=1, max_length=MAX_QUESTION_CHARS, description="Your question")
):
    question = question.strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "Please provide a question."})
    return {"question": question, "answer": answer_question_with_gemini(question)}


# Explanation - POST API (local LaMini-Flan-T5, Gemini fallback)
@app.post("/explain")
@app.post("/explain/", include_in_schema=False)
def explain_api(body: TopicRequest):
    explanation, engine = explain(body.topic)
    return {"topic": body.topic, "explanation": explanation, "engine": engine}


# Summarization - POST API
@app.post("/summarize")
@app.post("/summarize/", include_in_schema=False)
def summarize_api(body: TextRequest):
    return {"summary": summarize_text(body.text)}


# Quiz generation - POST API
@app.post("/quiz")
@app.post("/quiz/", include_in_schema=False)
def quiz_api(body: TextRequest):
    return {"quiz": generate_quiz(body.text)}


# Learning recommendations - GET API
@app.get("/learn/recommendations")
def learning_recommendation_api(
    topic: str = Query(..., min_length=1, max_length=MAX_TOPIC_CHARS, description="Topic to learn")
):
    topic = topic.strip()
    if not topic:
        return JSONResponse(status_code=400, content={"error": "Please provide a topic."})
    return {"topic": topic, "recommendation": get_learning_recommendations(topic)}
