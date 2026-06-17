from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.dependencies import get_current_admin
from app.db.mongodb import get_db
from app.models.job import DashboardStats
from app.repositories.job_repository import JobRepository
from app.repositories.question_repository import BilingualQuestionRepository, BookQuestionRepository, EnglishQuestionRepository, HindiQuestionRepository
router = APIRouter(prefix='/dashboard', tags=['Dashboard'])
@router.get('/stats', response_model=DashboardStats)
async def get_dashboard_stats(current_admin: str=Depends(get_current_admin), db: AsyncIOMotorDatabase=Depends(get_db)) -> DashboardStats:
    job_repo = JobRepository(db)
    en_repo = EnglishQuestionRepository(db)
    hi_repo = HindiQuestionRepository(db)
    bi_repo = BilingualQuestionRepository(db)
    book_repo = BookQuestionRepository(db)
    job_status_counts = await job_repo.count_by_status()
    en_status_counts = await en_repo.count_by_status()
    hi_status_counts = await hi_repo.count_by_status()
    bi_status_counts = await bi_repo.count_by_status()
    book_status_counts = await book_repo.count_by_status()
    total_pcs = sum(en_status_counts.values()) + sum(hi_status_counts.values()) + sum(bi_status_counts.values())
    total_jobs = sum(job_status_counts.values())
    total_book = sum(book_status_counts.values())
    return DashboardStats(total_jobs=total_jobs, pending_jobs=job_status_counts.get('Pending', 0), running_jobs=job_status_counts.get('Running', 0), failed_jobs=job_status_counts.get('Failed', 0), draft_ready_jobs=job_status_counts.get('Draft Ready', 0), total_pcs_questions=total_pcs, total_book_questions=total_book, draft_pcs_questions=en_status_counts.get('draft', 0) + hi_status_counts.get('draft', 0) + bi_status_counts.get('draft', 0), draft_book_questions=book_status_counts.get('draft', 0), approved_pcs_questions=en_status_counts.get('approved', 0) + hi_status_counts.get('approved', 0) + bi_status_counts.get('approved', 0), approved_book_questions=book_status_counts.get('approved', 0))
