# Threads Learning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuat posting otomatis Threads menjadi data evaluasi Anisa dengan snapshot insight 1 jam, 24 jam, dan 7 hari tanpa mengubah reaction gate yang sudah ada.

**Architecture:** Modul baru mengambil post insights melalui Threads Graph API, menyimpan snapshot ke SQLite, dan membuat konteks performa ringkas untuk draf berikutnya. Scheduler hanya mendaftarkan evaluasi setelah auto-post berhasil; kegagalan insight tidak boleh menggagalkan posting atau comment scanner.

**Tech Stack:** Python, httpx, SQLite, APScheduler, pytest, Meta Threads Graph API, AgentMemory optional.

---

## Explore Summary

- `auto_post_threads()` sudah menerima `post_id` dari `publish_post_to_threads()`.
- `start_threads_scheduler()` menjadwalkan tiga slot post acak dan scan komentar setiap lima menit.
- Reaction gate saat ini menunggu lima menit; timeout hanya auto-post jika `is_topic_safe_for_autopost()` mengembalikan aman.
- `fetch_user_posts()` hanya meminta `id,text,username,timestamp`; tidak ada views, likes, replies, reposts, quotes, atau shares.
- `ViralAnalysisTool` belajar dari tren luar dan menyimpan `[VIRAL_PATTERN]`, tetapi belum mengevaluasi performa posting Anisa sendiri.

## File Structure

- Create: `core/threads_insights.py` — API client, normalization, SQLite repository, dan performance context.
- Create: `tests/test_threads_insights.py` — parsing, persistence, dedup snapshot, dan ranking.
- Modify: `core/threads_scheduler.py` — daftar checkpoint setelah publish dan jalankan evaluasi terisolasi.
- Modify: `tests/test_threads_topic_dedup.py` atau create `tests/test_threads_insight_scheduler.py` — kontrak checkpoint scheduler.
- Modify: `core/threads_commands.py` — inject konteks performa lokal ke prompt draf tanpa mengubah reaction flow.
- Modify: `error_solutions.md` hanya jika implementasi menghasilkan error baru.

## Task 1: Define and Persist Insight Snapshots

**Files:**
- Create: `tests/test_threads_insights.py`
- Create: `core/threads_insights.py`

- [ ] **Step 1: Write failing model and persistence tests**

```python
from datetime import datetime, timezone

from core.threads_insights import (
    PostInsightSnapshot,
    ThreadsInsightRepository,
    normalize_insight_response,
)


def test_normalize_insight_response():
    payload = {
        "data": [
            {"name": "views", "values": [{"value": 1000}]},
            {"name": "likes", "values": [{"value": 50}]},
            {"name": "replies", "values": [{"value": 10}]},
            {"name": "reposts", "values": [{"value": 5}]},
            {"name": "quotes", "values": [{"value": 2}]},
            {"name": "shares", "values": [{"value": 3}]},
        ]
    }
    snapshot = normalize_insight_response(
        post_id="post-1",
        checkpoint="24h",
        post_text="meja gua lebih rapi dari hidup gua",
        payload=payload,
        captured_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    assert snapshot.views == 1000
    assert snapshot.interactions == 70
    assert snapshot.engagement_rate == 0.07


def test_repository_upserts_same_post_checkpoint(tmp_path):
    repo = ThreadsInsightRepository(tmp_path / "threads.db")
    first = PostInsightSnapshot(
        post_id="post-1", checkpoint="1h", post_text="abc",
        captured_at="2026-07-11T01:00:00+00:00", views=100,
        likes=5, replies=1, reposts=0, quotes=0, shares=0,
    )
    second = PostInsightSnapshot(
        post_id="post-1", checkpoint="1h", post_text="abc",
        captured_at="2026-07-11T01:05:00+00:00", views=120,
        likes=7, replies=1, reposts=1, quotes=0, shares=0,
    )
    repo.upsert(first)
    repo.upsert(second)
    rows = repo.list_snapshots(post_id="post-1")
    assert len(rows) == 1
    assert rows[0].views == 120
```

- [ ] **Step 2: Run tests and confirm missing module failure**

Run: `pytest tests/test_threads_insights.py -q`

Expected: `ModuleNotFoundError: core.threads_insights`.

- [ ] **Step 3: Implement the snapshot model and normalization**

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class PostInsightSnapshot:
    post_id: str
    checkpoint: str
    post_text: str
    captured_at: str
    views: int
    likes: int
    replies: int
    reposts: int
    quotes: int
    shares: int

    @property
    def interactions(self) -> int:
        return self.likes + self.replies + self.reposts + self.quotes + self.shares

    @property
    def engagement_rate(self) -> float:
        return self.interactions / self.views if self.views else 0.0


def normalize_insight_response(
    post_id: str,
    checkpoint: str,
    post_text: str,
    payload: dict,
    captured_at: datetime,
) -> PostInsightSnapshot:
    metrics: dict[str, int] = {}
    for item in payload.get("data", []):
        values = item.get("values") or []
        total = item.get("total_value", {}).get("value")
        value = total if total is not None else (values[-1].get("value", 0) if values else 0)
        metrics[item.get("name", "")] = int(value or 0)
    return PostInsightSnapshot(
        post_id=post_id,
        checkpoint=checkpoint,
        post_text=post_text,
        captured_at=captured_at.isoformat(),
        views=metrics.get("views", 0),
        likes=metrics.get("likes", 0),
        replies=metrics.get("replies", 0),
        reposts=metrics.get("reposts", 0),
        quotes=metrics.get("quotes", 0),
        shares=metrics.get("shares", 0),
    )
```

- [ ] **Step 4: Implement `ThreadsInsightRepository`**

```python
class ThreadsInsightRepository:
    def __init__(self, db_path: Path | str = Path("memory/threads_insights.db")):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS post_insight_snapshots (
                    post_id TEXT NOT NULL,
                    checkpoint TEXT NOT NULL,
                    post_text TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    views INTEGER NOT NULL,
                    likes INTEGER NOT NULL,
                    replies INTEGER NOT NULL,
                    reposts INTEGER NOT NULL,
                    quotes INTEGER NOT NULL,
                    shares INTEGER NOT NULL,
                    PRIMARY KEY (post_id, checkpoint)
                )
                """
            )

    def upsert(self, snapshot: PostInsightSnapshot) -> None:
        values = (
            snapshot.post_id, snapshot.checkpoint, snapshot.post_text,
            snapshot.captured_at, snapshot.views, snapshot.likes,
            snapshot.replies, snapshot.reposts, snapshot.quotes,
            snapshot.shares,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO post_insight_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id, checkpoint) DO UPDATE SET
                    post_text=excluded.post_text,
                    captured_at=excluded.captured_at,
                    views=excluded.views,
                    likes=excluded.likes,
                    replies=excluded.replies,
                    reposts=excluded.reposts,
                    quotes=excluded.quotes,
                    shares=excluded.shares
                """,
                values,
            )

    def list_snapshots(self, post_id: str | None = None) -> list[PostInsightSnapshot]:
        query = "SELECT * FROM post_insight_snapshots"
        params: tuple[str, ...] = ()
        if post_id is not None:
            query += " WHERE post_id = ?"
            params = (post_id,)
        query += " ORDER BY captured_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [PostInsightSnapshot(**dict(row)) for row in rows]
```

- [ ] **Step 5: Run persistence tests**

Run: `pytest tests/test_threads_insights.py -q`

Expected: normalization and persistence tests pass.

- [ ] **Step 6: Commit the local insight store**

```bash
git add core/threads_insights.py tests/test_threads_insights.py
git commit -m "feat: persist threads insight snapshots"
```

## Task 2: Fetch Official Post Insights

**Files:**
- Modify: `core/threads_insights.py`
- Modify: `tests/test_threads_insights.py`

- [ ] **Step 1: Add a failing HTTP contract test**

```python
import pytest


@pytest.mark.asyncio
async def test_fetch_post_insights_requests_expected_metrics(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": []}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params, timeout):
            captured.update(url=url, params=params, timeout=timeout)
            return FakeResponse()

    monkeypatch.setattr("core.threads_insights.httpx.AsyncClient", FakeClient)
    payload = await fetch_post_insights("post-9", "token-1")
    assert captured["url"].endswith("/post-9/insights")
    assert captured["params"]["metric"] == "views,likes,replies,reposts,quotes,shares"
    assert captured["params"]["access_token"] == "token-1"
    assert payload == {"data": []}
```

- [ ] **Step 2: Run the focused test and confirm missing function failure**

Run: `pytest tests/test_threads_insights.py::test_fetch_post_insights_requests_expected_metrics -q`

Expected: FAIL because `fetch_post_insights` is undefined.

- [ ] **Step 3: Implement the API call**

```python
import httpx


async def fetch_post_insights(post_id: str, access_token: str) -> dict:
    url = f"https://graph.threads.net/v1.0/{post_id}/insights"
    params = {
        "metric": "views,likes,replies,reposts,quotes,shares",
        "access_token": access_token,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run the full insight test module**

Run: `pytest tests/test_threads_insights.py -q`

Expected: all tests pass without real network calls.

- [ ] **Step 5: Commit the API client**

```bash
git add core/threads_insights.py tests/test_threads_insights.py
git commit -m "feat: fetch official threads post insights"
```

## Task 3: Schedule 1h, 24h, and 7d Checkpoints

**Files:**
- Modify: `core/threads_scheduler.py`
- Create: `tests/test_threads_insight_scheduler.py`

- [ ] **Step 1: Write a failing scheduler contract test**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from core.threads_scheduler import schedule_post_insight_checkpoints


class FakeScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, **kwargs):
        self.jobs.append((func, kwargs))


def test_schedule_post_insight_checkpoints_registers_three_jobs():
    scheduler = FakeScheduler()
    published_at = datetime(2026, 7, 11, 10, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    schedule_post_insight_checkpoints(
        scheduler=scheduler,
        post_id="post-1",
        post_text="draf",
        published_at=published_at,
    )
    assert [job[1]["id"] for job in scheduler.jobs] == [
        "threads_insight_post-1_1h",
        "threads_insight_post-1_24h",
        "threads_insight_post-1_7d",
    ]
```

- [ ] **Step 2: Run the scheduler test and confirm missing function failure**

Run: `pytest tests/test_threads_insight_scheduler.py -q`

Expected: import failure for `schedule_post_insight_checkpoints`.

- [ ] **Step 3: Implement the isolated collection job**

Add these imports and function to `core/threads_scheduler.py`:

```python
from datetime import datetime, timedelta, timezone

from core.threads_insights import (
    ThreadsInsightRepository,
    fetch_post_insights,
    normalize_insight_response,
)


async def collect_post_insight(
    post_id: str,
    post_text: str,
    checkpoint: str,
) -> None:
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not token:
        logger.warning("[THREADS_INSIGHTS] token tidak tersedia")
        return
    try:
        payload = await fetch_post_insights(post_id, token)
        snapshot = normalize_insight_response(
            post_id=post_id,
            checkpoint=checkpoint,
            post_text=post_text,
            payload=payload,
            captured_at=datetime.now(timezone.utc),
        )
        await asyncio.to_thread(ThreadsInsightRepository().upsert, snapshot)
        logger.info(
            "[THREADS_INSIGHTS] saved post=%s checkpoint=%s views=%s interactions=%s",
            post_id,
            checkpoint,
            snapshot.views,
            snapshot.interactions,
        )
    except Exception as exc:
        logger.error(
            "[THREADS_INSIGHTS] collection failed post=%s checkpoint=%s: %s",
            post_id,
            checkpoint,
            exc,
        )
```

- [ ] **Step 4: Implement the three date-trigger registrations**

```python
def schedule_post_insight_checkpoints(
    scheduler,
    post_id: str,
    post_text: str,
    published_at: datetime,
) -> None:
    checkpoints = (("1h", 3600), ("24h", 86400), ("7d", 604800))
    for label, delay_seconds in checkpoints:
        scheduler.add_job(
            collect_post_insight,
            trigger="date",
            run_date=published_at + timedelta(seconds=delay_seconds),
            args=[post_id, post_text, label],
            id=f"threads_insight_{post_id}_{label}",
            replace_existing=True,
        )
```

- [ ] **Step 5: Pass the scheduler into auto-post jobs and register checkpoints only after successful publish**

Change `auto_post_threads(client)` to `auto_post_threads(client, scheduler=None)`. In `schedule_random_posts_for_today()`, use `args=[client, scheduler]`. Immediately after a valid `post_id` is returned, call `schedule_post_insight_checkpoints(scheduler, post_id, final_text, datetime.now(WIB))` when scheduler is not `None`.

Do not alter `request_permission`, `PermissionTimeoutError`, `is_topic_safe_for_autopost`, or the approve/reject/timeout branches.

- [ ] **Step 6: Run scheduler and existing Threads tests**

Run:

```bash
pytest tests/test_threads_insight_scheduler.py tests/test_threads_topic_dedup.py tests/test_threads_dedup.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit checkpoint scheduling**

```bash
git add core/threads_scheduler.py tests/test_threads_insight_scheduler.py
git commit -m "feat: schedule threads insight checkpoints"
```

## Task 4: Feed Proven Performance Back Into Drafts

**Files:**
- Modify: `core/threads_insights.py`
- Modify: `core/threads_commands.py`
- Modify: `core/threads_scheduler.py`
- Modify: `tests/test_threads_insights.py`

- [ ] **Step 1: Add a failing performance-context test**

```python
def _snapshot(
    post_id: str,
    checkpoint: str,
    views: int,
    likes: int = 0,
    replies: int = 0,
    reposts: int = 0,
    quotes: int = 0,
    shares: int = 0,
) -> PostInsightSnapshot:
    return PostInsightSnapshot(
        post_id=post_id,
        checkpoint=checkpoint,
        post_text=post_id,
        captured_at="2026-07-11T00:00:00+00:00",
        views=views,
        likes=likes,
        replies=replies,
        reposts=reposts,
        quotes=quotes,
        shares=shares,
    )


def test_build_performance_context_ranks_24h_or_7d_snapshots(tmp_path):
    repo = ThreadsInsightRepository(tmp_path / "threads.db")
    repo.upsert(_snapshot("low", "24h", views=1000, likes=5))
    repo.upsert(_snapshot("high", "24h", views=1000, likes=100, replies=20))
    context = repo.build_performance_context(limit=3)
    assert "high" in context
    assert context.index("high") < context.index("low")
    assert "engagement_rate" in context
```

- [ ] **Step 2: Implement bounded local performance context**

Add this method to `ThreadsInsightRepository`:

```python
    def build_performance_context(self, limit: int = 3) -> str:
        eligible = [
            row for row in self.list_snapshots()
            if row.checkpoint in {"24h", "7d"}
        ]
        newest_by_post: dict[str, PostInsightSnapshot] = {}
        for row in eligible:
            newest_by_post.setdefault(row.post_id, row)
        ranked = sorted(
            newest_by_post.values(),
            key=lambda row: (row.engagement_rate, row.interactions, row.views),
            reverse=True,
        )[:limit]
        return "\n".join(
            (
                f"post_id={row.post_id} checkpoint={row.checkpoint} "
                f"engagement_rate={row.engagement_rate:.4f} "
                f"views={row.views} interactions={row.interactions} "
                f"text={row.post_text[:180]}"
            )
            for row in ranked
        )
```

- [ ] **Step 3: Inject the context beside existing viral memory**

In manual and automatic draft flows, read:

```python
performance_context = ThreadsInsightRepository().build_performance_context(limit=3)
```

Append it under a separate heading:

```text
=== PERFORMA POSTING ANISA SENDIRI ===
{performance_context}
Gunakan sebagai evaluasi, bukan formula yang harus disalin mentah.
```

Do not replace `[VIRAL_PATTERN]`; external trend learning and own-post evaluation remain separate inputs.

- [ ] **Step 4: Run prompt, insight, and anti-slop regressions**

Run:

```bash
pytest tests/test_threads_insights.py tests/test_threads_reply_prompt.py tests/test_threads_no_ai_leak.py tests/test_threads_revision.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the feedback loop**

```bash
git add core/threads_insights.py core/threads_commands.py core/threads_scheduler.py tests/test_threads_insights.py
git commit -m "feat: feed threads performance into future drafts"
```

## Final Verification

- [ ] Run `pytest tests/test_threads*.py -q`.
- [ ] Run `python scripts/healthcheck.py`.
- [ ] With a test token, mock or sandbox the insight endpoint before any production post.
- [ ] Confirm approve, reject, revision, timeout-safe auto-post, timeout-unsafe cancel, comment auto-reply, and comment manual approval behave exactly as before.
- [ ] Confirm an insight API timeout produces a log entry but does not stop APScheduler.
- [ ] Record every implementation error and verified solution in `error_solutions.md`.
