# EduMentor AI

A RAG-based study assistant: upload course documents, chat with them (with citations),
generate flashcards and quizzes from them, and track study progress — all scoped per subject.

This is the **complete, integrated project**: FastAPI backend + static frontend, served
together from a single process on a single port. No separate frontend server, no CORS
setup required for normal use.

```
edumentor/
├── backend/
│   ├── app/
│   │   ├── main.py          <- mounts frontend/ as static files (see below)
│   │   ├── api/v1/          <- auth, subjects, documents, chat, study_tools, analytics
│   │   ├── core/            <- config, security, gemini.py, embeddings.py
│   │   ├── services/        <- parser, chunker, vector_store
│   │   ├── models/, schemas/, db/
│   │   └── uploads/         <- uploaded documents land here
│   ├── tests/
│   ├── requirements.txt
│   ├── run.py
│   ├── .env.example
│   └── PHASE2_NOTES.md      <- backend build notes
└── frontend/
    ├── index.html
    ├── assets/
    │   ├── styles.css
    │   ├── api.js            <- one function per backend endpoint
    │   └── app.js             <- router + every view
    └── README.md              <- frontend-specific notes
```

## How the integration works

`backend/app/main.py` does two things after registering the API routes:

1. Keeps `app.include_router(api_router, prefix="/api/v1")` registered **first**, so those
   routes always take priority.
2. Mounts the sibling `frontend/` folder as static files at `/`:
   ```python
   app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
   ```
   `html=True` means `GET /` serves `frontend/index.html`, and `frontend/assets/*` is
   served as-is. Because this mount is registered *after* the API router, it only catches
   requests that don't match an API route — `/api/v1/...` always goes to FastAPI, `/`,
   `/assets/app.js`, etc. go to the static files.

Because the browser now loads the page from `http://localhost:8000` and calls the API on
that same origin, `frontend/assets/api.js` defaults its API base URL to
`${location.origin}/api/v1` — so it just works with zero configuration. (If you ever want
to run the frontend on a different port/host than the backend, e.g. for split local dev,
the "API" field at the bottom of the sidebar overrides this and is saved to `localStorage`;
CORS is left open in `main.py` to support that case too.)

If the `frontend/` folder isn't present next to `backend/` (e.g. you deploy the API by
itself), the mount is skipped automatically rather than crashing on startup.

## Running it

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# edit .env: set DATABASE_URL (MySQL) and JWT_SECRET_KEY at minimum
# optional but needed for chat/flashcards/quizzes/embeddings:
#   set GEMINI_API_KEY (free key: https://aistudio.google.com/apikey)
python run.py
```

Then open **http://localhost:8000** — that's the whole app, frontend and API together.
API docs are still available at **http://localhost:8000/docs**.

## What each half does

- **Backend** (`backend/PHASE2_NOTES.md`): FastAPI + SQLAlchemy + MySQL, JWT auth,
  document upload → text extraction → chunking → Gemini embeddings, brute-force cosine
  top-k retrieval for RAG chat, Gemini-generated flashcards/MCQ quizzes, and progress
  analytics.
- **Frontend** (`frontend/README.md`): vanilla HTML/CSS/JS SPA (hash-based routing, no
  build step) covering auth, subjects, document upload with live status, RAG chat with
  citation chips, flip-to-reveal flashcards, quiz taking/grading, and a dashboard.
