import asyncio
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.db.mongodb import MongoDB
from app.repositories.pending_review_repository import PendingReviewRepository
from app.services.azure_blob.watcher import list_unprocessed_pdfs
from app.workers.drive_pipeline import run_blob_pipeline

logger = get_logger(__name__)

_semaphore: Optional[asyncio.Semaphore] = None
_watcher_task: Optional[asyncio.Task] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_WORKERS)
    return _semaphore


async def _process_file(blob_name: str, file_name: str) -> None:
    sem = _get_semaphore()
    async with sem:
        db = MongoDB.get_db()
        if settings.ENABLE_DUPLICATE_CHECK:
            review_repo = PendingReviewRepository(db)
            # Check if already processed (any status other than pending means done)
            docs = await review_repo._col.find_one({'blob_name': blob_name})
            if docs:
                logger.info('blob_watcher.skip_duplicate', blob=blob_name, file=file_name)
                return
        logger.info('blob_watcher.processing', blob=blob_name, file=file_name)
        await run_blob_pipeline(blob_name, file_name, db)


async def _initial_scan() -> None:
    try:
        files = await list_unprocessed_pdfs()
        if not files:
            return
        logger.info('blob_watcher.initial_scan', count=len(files))
        tasks = [asyncio.create_task(_process_file(f['blob_name'], f['file_name'])) for f in files]
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:
        logger.error('blob_watcher.initial_scan_error', error=str(exc))


async def watch_loop() -> None:
    logger.info('blob_watcher.starting', interval=settings.CHECK_INTERVAL_SECONDS)
    await _initial_scan()
    while True:
        try:
            await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)
            files = await list_unprocessed_pdfs()
            if files:
                logger.info('blob_watcher.new_files', count=len(files))
                tasks = [asyncio.create_task(_process_file(f['blob_name'], f['file_name'])) for f in files]
                await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info('blob_watcher.stopped')
            break
        except Exception as exc:
            logger.error('blob_watcher.loop_error', error=str(exc))
            await asyncio.sleep(10)


async def start_watcher() -> None:
    global _watcher_task
    if not settings.blob_configured:
        logger.warning('blob_watcher.not_configured_skipping')
        return
    if settings.PIPELINE_MODE == 'manual':
        logger.info('blob_watcher.manual_mode_skipping')
        return
    _watcher_task = asyncio.create_task(watch_loop())
    logger.info('blob_watcher.task_created')


async def stop_watcher() -> None:
    global _watcher_task
    if _watcher_task and not _watcher_task.done():
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass
    _watcher_task = None
    logger.info('blob_watcher.task_stopped')
