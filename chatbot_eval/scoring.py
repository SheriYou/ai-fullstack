"""Shared scoring helpers for eval runs and report regeneration."""

from __future__ import annotations

import re


AFTER_HOURS_HANDOFF_REASON = "after_hours_handoff_fallback"


def is_after_hours_handoff_fallback(reply: str | None) -> bool:
    """Return True for the approved after-hours customer-care fallback."""

    text = re.sub(r"\s+", " ", str(reply or "").strip().lower())
    return all(
        part in text
        for part in (
            "sorry, customer care is closed for today",
            "monday to friday",
            "9 am",
            "3 pm",
            "no wahala",
        )
    )


def score_handoff(expected: bool, actual: bool, reply: str | None) -> tuple[bool, str | None]:
    """Score handoff, accepting the after-hours fallback as a reasonable outcome."""

    if actual == expected:
        return True, None
    if expected and not actual and is_after_hours_handoff_fallback(reply):
        return True, AFTER_HOURS_HANDOFF_REASON
    return False, None
