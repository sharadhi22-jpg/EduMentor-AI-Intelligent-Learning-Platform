# EduMentor AI — Phase 2 Build Notes

## Bug fix (blocking, found before Phase 2 work)
`app/api/v1/deps.py` passed the raw `HTTPAuthorizationCredentials` object into
`decode_access_token()` instead of `.credentials` (the actual JWT string).
This silently broke **every authenticated endpoint** except login/register —
subjects, documents, everything. Also normalized the "no token supplied" case
to return `401` instead of FastAPI's non-standard default of `403`.
Fixed in `deps.py`. All previously-failing tests now pass.

## What was built (previously empty stub files)

| File | What it does |
|---|---|
| `app/core/gemini.py` | Gemini API client wrapper: `generate_text`, `generate_json`, `embed_texts`, `embed_query`. Centralizes all LLM calls + system prompts. |
| `app/core/embeddings.py` | Batches chunk text into Gemini embedding calls; degrades gracefully (empty vectors + warning log) if no API key is set, so uploads never hard-fail. |
| `app/services/vector_store.py` | Cosine similarity + brute-force top-k retrieval over a subject's chunks. |
| `app/api/v1/chat.py` | RAG chat: create/list/delete sessions, list messages, send message (retrieves relevant chunks → prompts Gemini → stores reply with citations). |
| `app/api/v1/study_tools.py` | Flashcard generation from documents, quiz generation (MCQ), quiz submission/grading, quiz attempt history — all backed by Gemini `generate_json`. |
| `app/api/v1/analytics.py` | Per-subject progress (study hours, weak/strong topics, completed quizzes) + an aggregate dashboard endpoint. |
| `app/api/v1/router.py` | Registered the three new routers (they existed as files but were never wired in). |
| `app/api/v1/documents.py` | Upload now actually computes and stores chunk embeddings (was hardcoded to `[]`). |

## Frontend

A static frontend (`../frontend`) is now integrated: `app/main.py` mounts it directly
via `StaticFiles`, so running the backend serves the whole app — UI and API — from one
process on one port. No separate dev server, no CORS config to manage. See
`../frontend/README.md` for details on the UI itself.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` → `.env`, fill in `DATABASE_URL`, `JWT_SECRET_KEY`
3. Get a free Gemini key at https://aistudio.google.com/apikey and set `GEMINI_API_KEY`
   (the app still runs without it — chat/flashcards/quizzes just return `503` until it's set)
4. `python run.py`
5. Open `http://localhost:8000` for the app, or `http://localhost:8000/docs` for the API docs.

## Tests

`pytest tests/ -q` — 13 tests, all passing. Includes a fully mocked end-to-end
RAG cycle (upload → embed → retrieve → generate → citations) so the pipeline
is verified without needing a live API key.

## Known gaps / good next steps
- `require_admin` dependency exists but no admin-only routes use it yet.
- Study-hours logging is manual (`POST /analytics/progress/study-time`) rather
  than auto-tracked from real session time — worth revisiting once there's a
  frontend that can track active study sessions.
- Progress's weak/strong topic detection is a simple per-quiz threshold
  (< 60% → weak). Could be made smarter by tagging questions to sub-topics.
