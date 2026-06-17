import asyncio
import functools
import random
from typing import Callable, Tuple, Type
from app.core.logging import get_logger
logger = get_logger(__name__)
def async_retry(max_attempts: int=3, base_delay: float=1.0, max_delay: float=30.0, exceptions: Tuple[Type[Exception], ...]=(Exception,)):
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            delay = base_delay
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error('retry.exhausted', func=func.__name__, attempts=attempt, error=str(exc))
                        raise
                    jitter = random.uniform(0, delay * 0.1)
                    sleep_time = min(delay + jitter, max_delay)
                    logger.warning('retry.retrying', func=func.__name__, attempt=attempt, sleep_s=round(sleep_time, 2), error=str(exc))
                    await asyncio.sleep(sleep_time)
                    delay = min(delay * 2, max_delay)
        return wrapper
    return decorator
