"""Centralized retry wrapper for external API calls.

Uses stamina (already in requirements.txt; proven di embedder.py:125 + furniture_qc.py:236).

Pakai call_with_retry() buat wrap one-shot call:
    resp = call_with_retry(lambda: yf.Ticker(t).info, label="yfinance_info")

Pattern on=Exception (broad) konsisten sama existing usage di BIMA —
predicate 429-only butuh exception wrapping yg awkward, skip per minimal-diff.
"""
from __future__ import annotations

import logging
from typing import Callable, TypeVar

import stamina

logger = logging.getLogger("bima_core")
T = TypeVar("T")

retry_external_api = stamina.retry(
    on=Exception,
    attempts=3,
    wait_initial=1.0,
    wait_max=30.0,
    wait_jitter=0.5,
)


def call_with_retry(fn: Callable[[], T], label: str = "external_api") -> T:
    """One-shot retry wrapper. Logs warning kalau exhausted, re-raise ke caller."""

    @retry_external_api
    def _wrapped() -> T:
        return fn()

    try:
        return _wrapped()
    except Exception as e:
        logger.warning(f"[API_RETRY] {label} gagal setelah 3x retry: {type(e).__name__}: {e}")
        raise
