import logging

import pytest

from core import saham_scheduler as scheduler_module


def test_scheduler_keeps_late_jobs_for_two_minutes(monkeypatch):
    captured: dict[str, object] = {}

    class FakeScheduler:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            return None

    monkeypatch.setenv("SAHAM_CHANNEL_ID", "123")
    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", FakeScheduler)
    monkeypatch.setattr(scheduler_module, "_scheduler_started", False)

    scheduler_module.start_saham_scheduler(object())

    assert captured["job_defaults"] == {
        "misfire_grace_time": 120,
        "coalesce": True,
        "max_instances": 1,
    }


@pytest.mark.asyncio
async def test_paper_tick_logs_completion_without_trade(monkeypatch, caplog):
    async def fake_to_thread(func, *args):
        return []

    monkeypatch.setattr(scheduler_module.asyncio, "to_thread", fake_to_thread)
    caplog.set_level(logging.INFO, logger="bima_core")

    await scheduler_module._paper_trading_tick("idx")

    assert "[PAPER TRADER] idx: tick completed, no trade" in caplog.text
