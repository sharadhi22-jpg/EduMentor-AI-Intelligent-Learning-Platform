# EduMentor — Frontend

A static, dependency-free frontend for the EduMentor Phase 2 backend. Plain HTML/CSS/JS,
no build step, no npm install. Talks directly to the FastAPI backend's REST API.

> **This folder is now served automatically by the backend** (see the top-level
> `README.md` and `backend/app/main.py`) — just run the backend and open
> `http://localhost:8000`. Everything below about running it as a separate static server
> is only relevant if you deliberately want to split them across two processes/ports.

## What's here

```
frontend/
├── index.html          entry point
└── assets/
    ├── styles.css       design system (paper/notebook aesthetic)
    ├── api.js           API client — one function per backend endpoint
    └── app.js           router + all views (auth, dashboard, subjects,
                          documents, chat, flashcards, quizzes, progress)
```

## Running it

1. **Start the backend first** (see `backend/PHASE2_NOTES.md`):
   ```bash
   cd backend
   pip install -r requirements.txt
   cp .env.example .env   # fill in DATABASE_URL, JWT_SECRET_KEY, GEMINI_API_KEY
   python run.py
   ```
   It should be running at `http://localhost:8000`. CORS is already open (`allow_origins=["*"]`)
   in `app/main.py`, so no backend changes are needed to talk to this frontend.

2. **Serve the frontend** as static files (fetch calls need an http(s) origin, so don't
   just double-click `index.html` — use a tiny local server):
   ```bash
   cd frontend
   python -m http.server 5173
   ```
   Then open `http://localhost:5173`.

3. **API base URL**: the app defaults to `http://localhost:8000/api/v1`. If your backend
   runs elsewhere, edit the "API" field at the bottom of the sidebar (after logging in) —
   it's saved in `localStorage` immediately.

## Features implemented

- **Auth** — register / login / logout, JWT stored in `localStorage`, auto-attached to
  every request, redirected to login on 401.
- **Subjects** — create, list, filter by semester (backend supports it; UI lists all).
- **Documents** — drag-and-drop or click-to-upload (PDF/DOCX/PPTX/TXT), live status pill
  (pending → processing → completed/failed), delete.
- **Chat** — multiple sessions per subject, RAG-grounded replies with citation chips
  showing source filename + relevance score, typing indicator while waiting on Gemini.
- **Flashcards** — generate from a subject's documents (count + difficulty), flip-to-reveal
  cards, delete.
- **Quizzes** — generate MCQ quizzes, take them, grade client-side display of correct/
  incorrect after submission, retake.
- **Progress** — per-subject study hours, completed quizzes, weak/strong topics, manual
  study-time logging; plus an aggregate dashboard (`/analytics/dashboard`) as the home screen.

## Notes

- If `GEMINI_API_KEY` isn't set on the backend, chat/flashcard/quiz generation will
  return a 503 — the UI surfaces that error message as a toast rather than failing silently.
- No frontend framework or bundler is used on purpose, so this can be opened, edited, and
  understood without any tooling — swap in React/Vite later if the project grows.
