from fastapi import APIRouter

from app.api.v1 import analytics, auth, chat, documents, study_tools, subjects

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(subjects.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
api_router.include_router(study_tools.router)
api_router.include_router(analytics.router)

