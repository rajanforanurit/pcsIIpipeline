from fastapi import APIRouter
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.bilingual_ingest import router as bilingual_router
from app.api.v1.routes.book_ingest import router as book_router
from app.api.v1.routes.bilingual_questions import router as pcs_questions_router
from app.api.v1.routes.book_questions import router as book_questions_router
from app.api.v1.routes.pending_review import router as pending_review_router
from app.api.v1.routes.drive_pipeline import router as blob_pipeline_router

api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(jobs_router)
api_router.include_router(bilingual_router)
api_router.include_router(book_router)
api_router.include_router(pcs_questions_router)
api_router.include_router(book_questions_router)
api_router.include_router(pending_review_router)
api_router.include_router(blob_pipeline_router)
