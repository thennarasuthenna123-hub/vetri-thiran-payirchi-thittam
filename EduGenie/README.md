# EduGenie - Google Gemini Powered Learning Assistant

A lightweight AI study assistant built with **FastAPI** + plain **HTML/CSS/JS**.

| Tool | Endpoint | Engine |
|---|---|---|
| Ask a question | `GET /qa?question=...` | Gemini |
| Explain a concept | `POST /explain` `{"topic": "..."}` | Local LaMini-Flan-T5-783M (falls back to Gemini) |
| Summarize text | `POST /summarize` `{"text": "..."}` | Gemini |
| Generate a quiz (3 MCQs x 4 options) | `POST /quiz` `{"text": "..."}` | Gemini |
| Learning path | `GET /learn/recommendations?topic=...` | Gemini |
| Health check | `GET /health` | - |

Interactive API docs: http://127.0.0.1:8000/docs

## Project structure

```
EduGenie/
├── main.py                 # FastAPI app + routes + error handling
├── gemini_client.py        # Shared Gemini client (API key, model, errors)
├── qna.py                  # Question answering
├── explanation_module.py   # Concept explanation (local T5, Gemini fallback)
├── quiz_module.py          # Quiz generation + JSON cleaning/validation
├── summary_module.py       # Summarization
├── learning_path.py        # Learning recommendations
├── templates/index.html    # Frontend page
├── static/style.css        # Styling
├── static/script.js        # Frontend logic (fetch, rendering, interactive quiz)
├── tests/test_api.py       # Automated tests (Gemini mocked)
├── requirements.txt        # Core dependencies
├── requirements-local.txt  # OPTIONAL: local LaMini-Flan-T5 (torch/transformers)
├── requirements-dev.txt    # Test dependencies
├── .env.example            # Copy to .env and add your key
└── .vscode/                # Debug + test settings
```

## Setup (VS Code)

1. Install **Python 3.10+** (tick "Add Python to PATH" on Windows) and **VS Code** with the *Python* extension.
2. **File > Open Folder...** and choose the `EduGenie` folder. Open a terminal: **Terminal > New Terminal**.
3. Create and activate a virtual environment:
   - macOS / Linux: `python3 -m venv .venv && source .venv/bin/activate`
   - Windows (PowerShell): `python -m venv .venv` then `.venv\Scripts\Activate.ps1`
     (if blocked: `Set-ExecutionPolicy -Scope Process Bypass`)
4. In VS Code press **Ctrl/Cmd+Shift+P > Python: Select Interpreter** and pick the one inside `.venv`.
5. Install dependencies: `pip install -r requirements.txt`
6. Get a free Gemini API key at https://aistudio.google.com/apikey, then:
   - macOS / Linux: `cp .env.example .env`
   - Windows: `copy .env.example .env`
   
   Open `.env` and set `GEMINI_API_KEY=` to your key.

## Run

```
uvicorn main:app --reload
```

Open http://127.0.0.1:8000. Or press **F5** in VS Code and choose *EduGenie: run (uvicorn)* to debug.
Stop the server with **Ctrl+C**.

## Optional: local explanation model

By default concept explanations use Gemini, so nothing large is downloaded. To use the local
LaMini-Flan-T5-783M model from the project design (works on CPU and on Apple Silicon Macs):

```
pip install -r requirements-local.txt
```

Restart the server. The first "Explain" request downloads the model (~3 GB) and is slow; later ones are fast.
Force an engine with `EXPLAINER_BACKEND=local` or `gemini` in `.env` (default `auto`).

## Test

Automated (no API key or internet needed):

```
pip install -r requirements-dev.txt
pytest
```

Manual checklist (with the server running and a real key in `.env`):

1. **Ask a question**: "Which is the largest ocean?" -> answer mentions the Pacific.
2. **Explain a concept**: "Photosynthesis" -> short beginner explanation.
3. **Summarize text**: paste a long paragraph -> short summary with bullet points.
4. **Take a quiz**: "The Pythagorean theorem" -> 3 questions, 4 options each; wrong picks show the correct answer; a score appears at the end.
5. **Plan my learning**: "SQL" -> beginner / intermediate / advanced sections with timelines and resources.

Quick API checks from a terminal:

```
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/qa?question=Which+is+the+largest+ocean%3F"
curl -X POST http://127.0.0.1:8000/quiz -H "Content-Type: application/json" -d '{"text":"Solar System"}'
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Yellow "Gemini API key missing" banner | Create `.env` from `.env.example`, set `GEMINI_API_KEY`, restart the server |
| "Gemini model '...' was not found" | Google renamed/retired the model. Set `GEMINI_MODEL` in `.env` to a current one: https://ai.google.dev/gemini-api/docs/models |
| "rate limit or quota reached" | Wait a minute, or check your quota in Google AI Studio |
| `uvicorn` not found | Activate the virtual environment, or run `python -m uvicorn main:app --reload` |
| Port 8000 busy | `uvicorn main:app --reload --port 8001` |
| First local explanation is very slow | It is downloading the 3 GB model once; or set `EXPLAINER_BACKEND=gemini` |
