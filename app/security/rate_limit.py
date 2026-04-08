"""Rate limiting en memoria (por proceso). Para varios workers, usar Redis o el proxy."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request


class LoginAttemptLimiter:
    """
    Ventana deslizante de intentos fallidos de login por clave (p. ej. IP).
    Solo debe llamarse tras un login fallido (evita bloquear al usuario que acierta).
    """

    def __init__(self, max_failures: int, window_seconds: int):
        self.max_failures = max_failures
        self.window = float(window_seconds)
        self._lock = Lock()
        self._events: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window
        self._events[key] = [t for t in self._events[key] if t > cutoff]

    def is_blocked(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            return len(self._events[key]) >= self.max_failures

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._events[key].append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


def client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


_default_limiter: LoginAttemptLimiter | None = None


def get_login_limiter() -> LoginAttemptLimiter | None:
    return _default_limiter


def configure_login_limiter(max_failures: int, window_seconds: int) -> LoginAttemptLimiter | None:
    global _default_limiter
    if max_failures <= 0 or window_seconds <= 0:
        _default_limiter = None
        return None
    _default_limiter = LoginAttemptLimiter(max_failures, window_seconds)
    return _default_limiter
