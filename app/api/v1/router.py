from fastapi import APIRouter
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.english_ingest import router as english_router
from app.api.v1.routes.hindi_ingest import router as hindi_router
from app.api.v1.routes.book_ingest import router as book_router
from app.api.v1.routes.english_questions import router as english_questions_router
from app.api.v1.routes.hindi_questions import router as hindi_questions_router
from app.api.v1.routes.book_questions import router as book_questions_router
from app.api.v1.routes.pending_review import router as pending_review_router
from app.api.v1.routes.drive_pipeline import router as drive_pipeline_router

api_router = APIRouter(prefix="/api/v1")

# Existing routes (preserved)
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(jobs_router)
api_router.include_router(english_router)
api_router.include_router(hindi_router)
api_router.include_router(book_router)
api_router.include_router(english_questions_router)
api_router.include_router(hindi_questions_router)
api_router.include_router(book_questions_router)

# New Drive ETL pipeline routes
api_router.include_router(pending_review_router)
api_router.include_router(drive_pipeline_router)
