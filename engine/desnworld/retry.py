"""
API call retry helpers with exponential backoff.

Adapted from MiroFish (https://github.com/666ghj/MiroFish),
backend/app/utils/retry.py — Copyright (c) MiroFish authors and contributors,
AGPL-3.0. Modified for DESNWORLD (module path, logging, documentation; async
variant omitted).
"""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger("desnworld.retry")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Retry decorator with exponential backoff.

    Args:
        max_retries: maximum number of retries after the first attempt
        initial_delay: initial delay in seconds
        max_delay: cap on the delay in seconds
        backoff_factor: multiplier applied to the delay after each retry
        jitter: add random jitter to the delay
        exceptions: exception types that trigger a retry
        on_retry: callback invoked as on_retry(exception, retry_count)

    Usage:
        @retry_with_backoff(max_retries=3)
        def call_llm_api():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception: Optional[Exception] = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            "Function %s failed after %d retries: %s",
                            func.__name__,
                            max_retries,
                            e,
                        )
                        raise

                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())

                    logger.warning(
                        "Function %s attempt %d failed: %s; retrying in %.1fs",
                        func.__name__,
                        attempt + 1,
                        e,
                        current_delay,
                    )

                    if on_retry:
                        on_retry(e, attempt + 1)

                    time.sleep(current_delay)
                    delay *= backoff_factor

            if last_exception is not None:  # pragma: no cover - defensive
                raise last_exception
            raise RuntimeError("retry_with_backoff loop exited unexpectedly")

        return wrapper

    return decorator
