import threading
import time
from collections import deque
from collections.abc import Callable

_MAX_KEYS = 10_000


class FailureLimiter:
    """In-memory sliding-window limiter keyed by e.g. client IP.

    Used for failed logins (`retry_after` / `record_failure`) and for per-IP request
    rates (`hit`).

    Per-process only: fine for the single-instance deployment, not shared across workers.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()  # handlers run in a thread pool

    def _prune(self, key: str, window: float) -> deque[float]:
        events = self._failures.get(key)
        if events is None:
            return deque()
        cutoff = self._clock() - window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._failures[key]
        return events

    def _retry_after(self, key: str, max_events: int, window: float) -> int:
        events = self._prune(key, window)
        if len(events) < max_events:
            return 0
        return max(1, int(events[0] + window - self._clock()) + 1)

    def _record(self, key: str, window: float) -> None:
        self._prune(key, window)
        if key not in self._failures and len(self._failures) >= _MAX_KEYS:
            self._failures.pop(next(iter(self._failures)))  # drop the oldest key
        self._failures.setdefault(key, deque()).append(self._clock())

    def retry_after(self, key: str, max_failures: int, window: float) -> int:
        """Seconds to wait before the next attempt (0 = allowed)."""
        with self._lock:
            return self._retry_after(key, max_failures, window)

    def record_failure(self, key: str, window: float) -> None:
        with self._lock:
            self._record(key, window)

    def hit(self, key: str, max_events: int, window: float) -> int:
        """Count one request atomically. Returns 0 if allowed, else seconds to wait
        (a rejected request is not counted, so waiting out the window always works)."""
        with self._lock:
            wait = self._retry_after(key, max_events, window)
            if wait == 0:
                self._record(key, window)
            return wait

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)
