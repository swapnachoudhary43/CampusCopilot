"""Transparent priority suggestions.

These rules are not a machine-learning model. The project does not have a
separately labelled priority dataset, so it does not pretend to predict
priority with a classifier.
"""

from app.constants import PRIORITY_DISCLAIMER

HIGH_KEYWORDS = (
    "fire",
    "smoke",
    "electric shock",
    "spark",
    "injury",
    "injured",
    "harassment",
    "assault",
    "unsafe",
    "gas leak",
    "flood",
    "short circuit",
    "exposed wire",
    "exposed pin",
    "accident",
    "medical emergency",
    "no water",
)

MEDIUM_KEYWORDS = (
    "not working",
    "does not",
    "doesn't",
    "broken",
    "leak",
    "delay",
    "delayed",
    "unavailable",
    "out of service",
    "out of order",
    "cannot",
    "can't",
    "failed",
    "stuck",
    "no internet",
    "not connecting",
)


def suggest_priority(text: str) -> dict:
    lowered = text.lower()
    for keyword in HIGH_KEYWORDS:
        if keyword in lowered:
            return _result("high", keyword)
    for keyword in MEDIUM_KEYWORDS:
        if keyword in lowered:
            return _result("medium", keyword)
    return _result("low", None)


def _result(level: str, keyword: str | None) -> dict:
    if keyword:
        reason = f"Matched keyword '{keyword}'."
    else:
        reason = "No urgent or disruption keyword was found."
    return {
        "suggested_priority": level,
        "priority_method": "rule_based",
        "priority_reason": reason,
        "priority_disclaimer": PRIORITY_DISCLAIMER,
    }
