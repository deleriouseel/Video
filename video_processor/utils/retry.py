import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Optional
import random
from .logging import get_logger

logger = get_logger()

T = TypeVar("T")

class RetryConfig:
    def __init__ (
            self,
            max_attempts: int = 5,
            base_delay: float = 1.0,
            max_delay: float = 60.0,
            exponential_base: float = 2.0,
            jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

def exponential_backoff(
        retry_exceptions: tuple = (Exception),
        retry_config: Optional[RetryConfig] = None
):
    """"
    Decorator that implements retry logic with exponential backoff
    
    Args:
        retry_exceptions: Tuple of exceptions to catch and retry
        retry_config: Configuration for retry behavior
    
    """
    config =  retry_config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                
                except retry_exceptions as e:
                    last_exception = e
                    if attempt == config.max_attempts:
                        logger.error(f"Final attempt {attempt} failed for {func.__name__}: {str(e)}")
                        raise

                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt -1)), config.max_delay)
                    
                    if config.jitter:
                        delay = (0.5 + random.random())
                    
                    logger.warning(f"Attempt {attempt} failed for {func.__name__}: {str(e)}."
                                   f"Retrying in {delay:.2f} seconds...")
                    
                    time.sleep(delay)

            raise last_exception
        return wrapper
    return decorator

                    
                