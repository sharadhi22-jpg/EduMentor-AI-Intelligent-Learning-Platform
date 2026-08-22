"""
Gemini API client wrapper and system prompt definitions.

Centralizes every call out to Google's Gemini API so the rest of the app
(chat, flashcards, quizzes, embeddings) never talks to the SDK directly.
Handles lazy client init, missing-API-key detection, and JSON response
parsing in one place.
"""
import json
import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiNotConfiguredError(RuntimeError):
    """Raised when a Gemini call is attempted without an API key set."""


class GeminiError(RuntimeError):
    """Raised when the Gemini API call itself fails."""


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    if not is_configured():
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY is not set. Add it to your .env file to enable "
            "AI chat, flashcard/quiz generation, and semantic search."
        )
    return genai.Client(api_key=settings.GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

CHAT_SYSTEM_PROMPT = """You are EduMentor, an AI study assistant helping a student understand \
material from their own uploaded course documents.

Rules:
- Answer ONLY using the provided context excerpts. If the context does not contain \
the answer, say so honestly and suggest the student upload more material or rephrase.
- Be clear, concise, and pedagogical. Prefer short paragraphs, bullet points, and \
worked examples over dense prose.
- Do not invent facts, page numbers, or sources that are not in the context.
- Where useful, connect ideas to help the student build intuition rather than just \
restating the text."""

FLASHCARD_SYSTEM_PROMPT = """You are an expert study-content creator. Given source text, \
generate high-quality flashcards (front/back) that test understanding of key concepts, \
definitions, and relationships \u2014 not trivial recall. Keep fronts short (a question or \
term) and backs concise but complete (1-3 sentences)."""

QUIZ_SYSTEM_PROMPT = """You are an expert exam-question writer. Given source text, generate \
multiple-choice quiz questions that test real understanding at the requested difficulty. \
Each question must have exactly 4 options, exactly one correct answer, and no ambiguous \
or trick wording."""


# ---------------------------------------------------------------------------
# Text / JSON generation
# ---------------------------------------------------------------------------

def generate_text(prompt: str, system_instruction: str | None = None, temperature: float = 0.4) -> str:
    """Generate a plain-text response from Gemini."""
    client = get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )
        return (response.text or "").strip()
    except GeminiNotConfiguredError:
        raise
    except Exception as e:
        logger.error("Gemini generate_text failed: %s", e)
        raise GeminiError(f"Gemini generation failed: {e}") from e


def generate_json(prompt: str, system_instruction: str | None = None, temperature: float = 0.5):
    """Generate a response from Gemini constrained to valid JSON, and parse it."""
    client = get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        raw = (response.text or "").strip()
        return json.loads(raw)
    except GeminiNotConfiguredError:
        raise
    except json.JSONDecodeError as e:
        logger.error("Gemini returned invalid JSON: %s", e)
        raise GeminiError("Gemini returned a response that could not be parsed as JSON.") from e
    except Exception as e:
        logger.error("Gemini generate_json failed: %s", e)
        raise GeminiError(f"Gemini generation failed: {e}") from e


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a batch of texts. task_type is RETRIEVAL_DOCUMENT for stored content
    or RETRIEVAL_QUERY for a user's search/question."""
    if not texts:
        return []
    client = get_client()
    try:
        response = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.EMBEDDING_DIMENSIONS,
            ),
        )
        return [e.values for e in response.embeddings]
    except GeminiNotConfiguredError:
        raise
    except Exception as e:
        logger.error("Gemini embed_texts failed: %s", e)
        raise GeminiError(f"Gemini embedding failed: {e}") from e


def embed_query(text: str) -> list[float]:
    result = embed_texts([text], task_type="RETRIEVAL_QUERY")
    return result[0] if result else []
