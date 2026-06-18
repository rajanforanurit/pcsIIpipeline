import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import PlatformException
from app.core.logging import get_logger, setup_logging
from app.db.indexes import create_indexes
from app.db.mongodb import MongoDB
from app.workers.drive_watcher_worker import start_watcher, stop_watcher

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info('app.startup', env='production')
    await MongoDB.connect()
    db = MongoDB.get_db()
    await create_indexes(db)
    await start_watcher()
    logger.info('app.ready')
    yield
    logger.info('app.shutdown')
    await stop_watcher()
    await MongoDB.disconnect()


app = FastAPI(
    title='PCS Question Ingestion Platform',
    description='Production backend for UPSC/PSC bilingual question ingestion via Azure Blob Storage ETL pipeline, OCR, AI extraction (DeepSeek V3.2), admin review, and MongoDB storage.',
    version='2.2.0',
    docs_url='/docs',
    redoc_url='/redoc',
    openapi_url='/openapi.json',
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info('http.request', method=request.method, path=request.url.path, status=response.status_code, duration_ms=duration_ms)
    return response


@app.exception_handler(PlatformException)
async def platform_exception_handler(request: Request, exc: PlatformException) -> JSONResponse:
    logger.error('platform.exception', message=exc.message, status_code=exc.status_code, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={'success': False, 'message': exc.message, 'details': exc.details, 'status_code': exc.status_code},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error('unhandled.exception', error=str(exc), path=request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={'success': False, 'message': 'Internal server error', 'details': {}, 'status_code': 500},
    )


app.include_router(api_router)


@app.get('/health', tags=['Health'])
async def health_check():
    return {'status': 'healthy', 'version': '2.0.0'}


@app.get('/readiness', tags=['Health'])
async def readiness_check():
    try:
        db = MongoDB.get_db()
        await db.command('ping')
        return {'status': 'ready', 'mongodb': 'connected'}
    except Exception as exc:
        return JSONResponse(status_code=503, content={'status': 'not ready', 'mongodb': str(exc)})


@app.get('/', tags=['Root'])
async def root():
    return {
        'message': 'PCS-II Question Ingestion Platform',
        'version': '2.0.0',
        'docs': '/docs',
        'features': [
            'Azure Blob Storage ETL Pipeline',
            'Admin Pending Review Panel',
            'PCS2 V3.2 Model for Bilingual AI Extraction',
            'OCR (PaddleOCR)',
            'MongoDB Storage (pcsquestions, bookquestions, pending_reviews)',
        ],
    }


application = app
