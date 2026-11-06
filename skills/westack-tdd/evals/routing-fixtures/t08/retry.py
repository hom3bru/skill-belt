import time


def call_with_retry(func, attempts=3, delay=0.1):
    for attempt in range(attempts):
        try:
            return func()
        except ConnectionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
