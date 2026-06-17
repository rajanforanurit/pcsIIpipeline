import asyncio
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.db.mongodb import MongoDB
from app.repositories.drive_repository import DriveRepository
from app.services.google_drive.watcher import get_start_page_token, list_existing_pdfs_in_unprocessed, poll_new_pdfs
from app.workers.drive_pipeline import run_drive_pipeline
logger = get_logger(__name__)
_semaphore: Optional[asyncio.Semaphore] = None
_watcher_task: Optional[asyncio.Task] = None
def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_WORKERS)
    return _semaphore
async def _process_file(drive_file_id: str, file_name: str) -> None:
    sem = _get_semaphore()
    async with sem:
        db = MongoDB.get_db()
        repo = DriveRepository(db)
        if settings.ENABLE_DUPLICATE_CHECK:
            if await repo.file_already_processed(drive_file_id):
                logger.info('drive_watcher.skip_duplicate', file_id=drive_file_id, file=file_name)
                return
        logger.info('drive_watcher.processing', file_id=drive_file_id, file=file_name)
        await run_drive_pipeline(drive_file_id, file_name, db)
async def _initial_scan() -> None:
    try:
        files = await list_existing_pdfs_in_unprocessed()
        if not files:
            return
        logger.info('drive_watcher.initial_scan', count=len(files))
        tasks = [asyncio.create_task(_process_file(f['id'], f['name'])) for f in files]
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:
        logger.error('drive_watcher.initial_scan_error', error=str(exc))
async def watch_loop() -> None:
    logger.info('drive_watcher.starting', interval=settings.CHECK_INTERVAL_SECONDS)
    db = MongoDB.get_db()
    repo = DriveRepository(db)
    state = await repo.get_watcher_state()
    if state:
        page_token = state['page_token']
        logger.info('drive_watcher.resumed', page_token=page_token)
    else:
        page_token = await get_start_page_token()
        await repo.save_watcher_state(page_token)
        logger.info('drive_watcher.initialized', page_token=page_token)
    await _initial_scan()
    while True:
        try:
            await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)
            new_files, page_token = await poll_new_pdfs(page_token)
            await repo.save_watcher_state(page_token)
            if new_files:
                logger.info('drive_watcher.new_files', count=len(new_files))
                tasks = [asyncio.create_task(_process_file(f['id'], f['name'])) for f in new_files]
                await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info('drive_watcher.stopped')
            break
        except Exception as exc:
            logger.error('drive_watcher.loop_error', error=str(exc))
            await asyncio.sleep(10)
async def start_watcher() -> None:
    global _watcher_task
    if not settings.google_drive_configured:
        logger.warning('drive_watcher.not_configured_skipping')
        return
    if settings.PIPELINE_MODE == 'manual':
        logger.info('drive_watcher.manual_mode_skipping')
        return
    _watcher_task = asyncio.create_task(watch_loop())
    logger.info('drive_watcher.task_created')
async def stop_watcher() -> None:
    global _watcher_task
    if _watcher_task and (not _watcher_task.done()):
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass
    _watcher_task = None
    logger.info('drive_watcher.task_stopped')
