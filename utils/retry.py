"""
utils/retry.py — Retry and resilience decorators
"""

import time
import functools
from utils.exceptions import ExternalServiceError
from utils.logger import get_logger

logger = get_logger("retry")

def retry_with_backoff(max_attempts: int = 3, backoff_base: float = 1.0, retryable_exceptions: tuple = (ExternalServiceError,)):
    """
    Retry a function with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts. Last error: {str(e)}")
                        raise e
                    
                    sleep_time = backoff_base * (2 ** (attempts - 1))
                    logger.warning(f"Attempt {attempts} for {func.__name__} failed: {str(e)}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
            return func(*args, **kwargs) # Fallback, should not reach here due to raise e
        return wrapper
    return decorator
