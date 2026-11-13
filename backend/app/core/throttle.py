"""Small in-process limit for repeated login failures.

This is enough for the local demo. A production deployment should put the
same counters in a shared store so they survive more than one process.
"""

import time

_WINDOW_SECONDS = 300
_MAX_FAILURES = 8
_failures: dict[str, list[float]] = {}


def _recent(email: str) -> list[float]:
    now = time.time()
    kept = [stamp for stamp in _failures.get(email.lower(), []) if now - stamp < _WINDOW_SECONDS]
    _failures[email.lower()] = kept
    return kept


def login_allowed(email: str) -> bool:
    return len(_recent(email)) < _MAX_FAILURES


def record_login_failure(email: str) -> None:
    _recent(email).append(time.time())


def record_login_success(email: str) -> None:
    _failures.pop(email.lower(), None)
