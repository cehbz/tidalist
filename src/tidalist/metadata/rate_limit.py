"""Min-interval rate limiter for Discogs (which has no built-in throttle)."""

import time


class MinInterval:
    def __init__(self, per_minute: int = 60, *, now=time.monotonic, sleep=time.sleep):
        if per_minute <= 0:
            raise ValueError("per_minute must be positive")
        self._interval = 60.0 / per_minute
        self._now = now
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            remaining = self._interval - (self._now() - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._now()
