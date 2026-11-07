import functools
import time


def retry(times=3, delay=0.5, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise
                    time.sleep(delay * attempt)

        return wrapper

    return decorator


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]
