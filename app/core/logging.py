import logging
import sys
from pathlib import Path
import structlog
from app.core.config import settings
def _ensure_log_dir() -> None:
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)
def setup_logging() -> None:
    _ensure_log_dir()
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(name)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    log_file = Path(settings.LOG_DIR) / 'app.log'
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    logging.getLogger('motor').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('paddleocr').setLevel(logging.WARNING)
    logging.getLogger('ppocr').setLevel(logging.WARNING)
    shared_processors: list = [structlog.contextvars.merge_contextvars, structlog.stdlib.add_log_level, structlog.stdlib.add_logger_name, structlog.processors.TimeStamper(fmt='iso'), structlog.processors.StackInfoRenderer(), structlog.processors.format_exc_info]
    structlog.configure(processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter], wrapper_class=structlog.stdlib.BoundLogger, context_class=dict, logger_factory=structlog.stdlib.LoggerFactory(), cache_logger_on_first_use=True)
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
