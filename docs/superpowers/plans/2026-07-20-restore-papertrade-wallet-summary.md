# Restore Paper Trading Wallet Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengembalikan laporan `!saham papertrade` yang menampilkan total profit, total rugi, profit/rugi bersih, floating P&L, saldo, dan posisi tanpa menghilangkan state V1 yang sedang aktif.

**Architecture:** Pertahankan engine dan storage V1 (`outputs/saham_paper_cash.json`, `outputs/saham_paper_portfolio.json`, dan `memory/saham_history.db`) karena state V2 kosong. Tambahkan query agregat read-only pada history, bangun satu formatter laporan bersama di `core/saham_paper_trader.py`, lalu gunakan formatter yang sama untuk command manual dan recap harian. Jangan mengubah strategi trading, scheduler, dependency, schema, atau database.

**Tech Stack:** Python 3.12, SQLite stdlib, pytest, JSON storage yang sudah ada.

---

## File Map

- Modify: `core/saham_history.py` — query agregat realized P&L dan aktivitas terbaru.
- Modify: `core/saham_paper_trader.py` — hitung nilai pasar, floating P&L, equity, dan profit/rugi bersih per rekening.
- Modify: `core/saham_commands.py` — route `!saham papertrade` ke formatter bersama.
- Modify: `tests/test_saham_paper_trader.py` — regression test angka, format, dan quote yang tidak tersedia.
- Modify: `docs/WORKLOG.md` — catat root cause, keputusan mempertahankan V1, dan hasil verifikasi.
- Do not modify: `core/saham_scheduler.py` — file ini memiliki perubahan user aktif dan tidak diperlukan untuk perbaikan laporan.

### Task 1: Siapkan worktree dan buktikan baseline

**Files:**
- No source changes.

- [ ] **Step 1: Buat worktree terisolasi dari HEAD branch aktif**

```bash
git worktree add .worktrees/restore-papertrade-wallet -b codex/restore-papertrade-wallet agent-rules
```

Expected: worktree baru berada di `.worktrees/restore-papertrade-wallet`; working tree utama tetap tidak berubah.

- [ ] **Step 2: Pastikan file V1 dan database aktif tetap menjadi sumber data**

```bash
test -f /home/bima_lucian/BIMA_CORE/outputs/saham_paper_cash.json
test -f /home/bima_lucian/BIMA_CORE/outputs/saham_paper_portfolio.json
test -f /home/bima_lucian/BIMA_CORE/memory/saham_history.db
/home/bima_lucian/BIMA_CORE/bima_env/bin/python \
  -m pytest tests/test_saham_paper_trader.py -q
```

Expected: ketiga state file tersedia dan baseline test paper trader lulus. Jika baseline gagal, berhenti dan laporkan sebelum mengubah kode.

### Task 2: Tambahkan agregasi history yang dapat diaudit

**Files:**
- Modify: `core/saham_history.py`
- Test: `tests/test_saham_paper_trader.py`

- [ ] **Step 1: Tambahkan failing test untuk total profit, total rugi, realized bersih, dan aktivitas terbaru**

```python
def _trade_entry(
    *,
    ticker: str,
    market: str,
    action: str,
    realized_pnl: float | None,
) -> hist.TradeLogEntry:
    return hist.TradeLogEntry(
        ticker=ticker,
        market=market,
        action=action,
        qty=100.0,
        price=5_000.0,
        score=50,
        verdict="TEST",
        reasoning="test",
        realized_pnl=realized_pnl,
        cash_after=10_000_000.0,
        equity_after=10_000_000.0,
    )


def test_trade_summary_splits_profit_loss_and_limits_recent():
    hist.log_trade(
        _trade_entry(
            ticker="BBCA.JK", market="idx", action="SELL", realized_pnl=120_000.0
        )
    )
    hist.log_trade(
        _trade_entry(
            ticker="BBNI.JK", market="idx", action="SELL", realized_pnl=-40_000.0
        )
    )
    hist.log_trade(
        _trade_entry(
            ticker="BTC-USD", market="crypto", action="BUY", realized_pnl=None
        )
    )

    summary = hist.get_trade_summary("idx")
    recent = hist.get_recent_trades(limit=2)

    assert summary == {
        "total_profit": 120_000.0,
        "total_loss": -40_000.0,
        "realized_pnl": 80_000.0,
        "sell_count": 2,
    }
    assert [trade["ticker"] for trade in recent] == ["BTC-USD", "BBNI.JK"]
```

- [ ] **Step 2: Jalankan test dan pastikan gagal karena API belum ada**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python \
  -m pytest \
  tests/test_saham_paper_trader.py::test_trade_summary_splits_profit_loss_and_limits_recent \
  -q
```

Expected: FAIL dengan `AttributeError` untuk `get_trade_summary` atau `get_recent_trades`.

- [ ] **Step 3: Implementasikan query agregat dan recent trades**

```python
def get_trade_summary(market: str | None = None) -> dict[str, float | int]:
    """Ringkasan realized P&L SELL; BUY tidak dihitung sebagai hasil jual."""
    conn = _get_conn()
    try:
        where = "WHERE market = ?" if market else ""
        params = (market,) if market else ()
        row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(
                    CASE WHEN action = 'SELL' AND realized_pnl > 0
                    THEN realized_pnl ELSE 0 END
                ), 0) AS total_profit,
                COALESCE(SUM(
                    CASE WHEN action = 'SELL' AND realized_pnl < 0
                    THEN realized_pnl ELSE 0 END
                ), 0) AS total_loss,
                COALESCE(SUM(
                    CASE WHEN action = 'SELL'
                    THEN realized_pnl ELSE 0 END
                ), 0) AS realized_pnl,
                COALESCE(SUM(
                    CASE WHEN action = 'SELL' THEN 1 ELSE 0 END
                ), 0) AS sell_count
            FROM paper_trades
            {where}
            """,
            params,
        ).fetchone()
        return {
            "total_profit": float(row[0]),
            "total_loss": float(row[1]),
            "realized_pnl": float(row[2]),
            "sell_count": int(row[3]),
        }
    finally:
        conn.close()


def get_recent_trades(
    limit: int = 5,
    market: str | None = None,
) -> list[dict]:
    """Trade terbaru, dibatasi agar laporan Discord tetap ringkas."""
    safe_limit = max(0, int(limit))
    conn = _get_conn()
    try:
        if market:
            cur = conn.execute(
                """
                SELECT * FROM paper_trades
                WHERE market = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (market, safe_limit),
            )
        else:
            cur = conn.execute(
                """
                SELECT * FROM paper_trades
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
        columns = [item[0] for item in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()
```

- [ ] **Step 4: Jalankan focused test**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python \
  -m pytest \
  tests/test_saham_paper_trader.py::test_trade_summary_splits_profit_loss_and_limits_recent \
  -q
```

Expected: PASS.

### Task 3: Bangun laporan dompet lengkap dari state V1

**Files:**
- Modify: `core/saham_paper_trader.py`
- Test: `tests/test_saham_paper_trader.py`

- [ ] **Step 1: Tambahkan failing test untuk ringkasan per mata uang**

```python
def test_account_report_shows_net_realized_and_floating_pnl(monkeypatch):
    port.add_position("BBCA", 100, 5_000.0, account="paper")
    pt._save_cash({"idx": 9_500_000.0, "global": 1_000.0, "crypto": 500.0})
    hist.log_trade(
        _trade_entry(
            ticker="BBNI.JK", market="idx", action="SELL", realized_pnl=80_000.0
        )
    )
    monkeypatch.setattr(
        pt,
        "fetch_snapshot",
        _fake_snapshot_factory(
            {"BBCA.JK": {"ticker": "BBCA.JK", "close": 5_500.0}}
        ),
    )

    report = pt.build_account_report()

    assert "PROFIT BERSIH TOTAL: **+Rp50.000 (+0,50%)**" in report
    assert "Total profit jual: **+Rp80.000**" in report
    assert "Total rugi jual: **Rp0**" in report
    assert "Profit bersih terealisasi: **+Rp80.000**" in report
    assert "Untung/rugi berjalan: **+Rp50.000**" in report
    assert "Kekayaan sekarang: **Rp10.050.000**" in report
    assert "**5 AKTIVITAS TERAKHIR**" in report
    assert "Jual `BBNI.JK`" in report
```

- [ ] **Step 2: Tambahkan failing test agar harga gagal tidak menghasilkan profit tebakan**

```python
def test_account_report_does_not_guess_total_when_quote_missing(monkeypatch):
    port.add_position("BBCA", 100, 5_000.0, account="paper")
    pt._save_cash({"idx": 9_500_000.0, "global": 1_000.0, "crypto": 500.0})
    monkeypatch.setattr(
        pt,
        "fetch_snapshot",
        _fake_snapshot_factory({"BBCA.JK": RuntimeError("provider down")}),
    )

    report = pt.build_account_report()

    assert "IDX — harga pasar belum lengkap" in report
    assert "Profit/rugi bersih total belum bisa dihitung." in report
    assert "PROFIT BERSIH TOTAL" not in report
```

- [ ] **Step 3: Jalankan kedua test dan pastikan gagal**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest \
  tests/test_saham_paper_trader.py::test_account_report_shows_net_realized_and_floating_pnl \
  tests/test_saham_paper_trader.py::test_account_report_does_not_guess_total_when_quote_missing \
  -q
```

Expected: FAIL karena `build_account_report()` belum ada.

- [ ] **Step 4: Implementasikan formatter uang dan kalkulasi bucket**

```python
def _fmt_number(value: float, decimals: int = 0) -> str:
    rendered = f"{abs(value):,.{decimals}f}"
    return rendered.replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_money(value: float, market: str, *, signed: bool = False) -> str:
    prefix = "Rp" if market == "idx" else "$"
    decimals = 0 if market == "idx" else 2
    if signed and value:
        sign = "+" if value > 0 else "-"
    else:
        sign = "-" if value < 0 else ""
    return f"{sign}{prefix}{_fmt_number(value, decimals)}"


def _fmt_percent(value: float) -> str:
    return f"{value:+.2f}%".replace(".", ",")


def _bucket_snapshot(
    market: str,
    cash: dict[str, float],
    positions: dict[str, dict],
) -> dict:
    bucket_positions = {
        ticker: info
        for ticker, info in positions.items()
        if _bucket_of(ticker) == market
    }
    marked_positions: list[dict] = []
    complete = True
    market_value = 0.0
    cost_basis = 0.0
    for ticker, info in bucket_positions.items():
        try:
            snapshot = fetch_snapshot(ticker)
        except Exception:
            snapshot = None
        if not snapshot or snapshot.get("close") is None:
            complete = False
            continue
        current = float(snapshot["close"])
        value = current * float(info["qty"])
        cost = float(info["total_cost"])
        market_value += value
        cost_basis += cost
        marked_positions.append(
            {
                "ticker": ticker,
                "qty": float(info["qty"]),
                "avg_price": float(info["avg_price"]),
                "current": current,
                "value": value,
                "pnl": value - cost,
                "pnl_pct": ((value - cost) / cost * 100) if cost else 0.0,
            }
        )
    bucket_cash = float(cash.get(market, STARTING_CASH[market]))
    equity = bucket_cash + market_value if complete else None
    floating_pnl = market_value - cost_basis if complete else None
    return {
        "market": market,
        "cash": bucket_cash,
        "starting_cash": float(STARTING_CASH[market]),
        "equity": equity,
        "floating_pnl": floating_pnl,
        "positions": marked_positions,
        "complete": complete,
    }
```

- [ ] **Step 5: Tambahkan import query history ke paper trader**

```python
from core.saham_history import (
    TradeLogEntry,
    get_recent_trades,
    get_today_trades,
    get_trade_summary,
    log_trade,
)
```

- [ ] **Step 6: Implementasikan laporan bersama**

```python
def build_account_report(*, include_today_trades: bool = False) -> str:
    cash = _load_cash()
    positions = aggregate(list_positions(account="paper"))
    lines = ["🤖 **DOMPET ANISA — PAPER TRADING**"]

    if include_today_trades:
        trades = get_today_trades()
        lines.extend(["", "**TRANSAKSI HARI INI**"])
        if not trades:
            lines.append("Tidak ada transaksi hari ini.")
        else:
            for trade in trades:
                action = "Beli" if trade["action"] == "BUY" else "Jual"
                lines.append(
                    f"{action} `{trade['ticker']}` {trade['qty']:.4f} "
                    f"@ {_fmt_money(trade['price'], trade['market'])}"
                )

    for market in ("idx", "global", "crypto"):
        bucket = _bucket_snapshot(market, cash, positions)
        summary = get_trade_summary(market)
        lines.extend(
            [
                "",
                f"**{market.upper()}**",
                f"Modal awal: **{_fmt_money(bucket['starting_cash'], market)}**",
                f"Kas tersedia: **{_fmt_money(bucket['cash'], market)}**",
            ]
        )
        if bucket["complete"]:
            equity = float(bucket["equity"])
            net_pnl = equity - float(bucket["starting_cash"])
            net_pct = (
                net_pnl / float(bucket["starting_cash"]) * 100
                if bucket["starting_cash"]
                else 0.0
            )
            total_label = (
                "PROFIT BERSIH TOTAL"
                if net_pnl > 0
                else "RUGI BERSIH TOTAL"
                if net_pnl < 0
                else "HASIL BERSIH TOTAL"
            )
            lines.extend(
                [
                    f"Kekayaan sekarang: **{_fmt_money(equity, market)}**",
                    f"{total_label}: **{_fmt_money(net_pnl, market, signed=True)} "
                    f"({_fmt_percent(net_pct)})**",
                    f"Total profit jual: **"
                    f"{_fmt_money(float(summary['total_profit']), market, signed=True)}**",
                    f"Total rugi jual: **"
                    f"{_fmt_money(float(summary['total_loss']), market, signed=True)}**",
                    f"Profit bersih terealisasi: **"
                    f"{_fmt_money(float(summary['realized_pnl']), market, signed=True)}**",
                    f"Untung/rugi berjalan: **"
                    f"{_fmt_money(float(bucket['floating_pnl']), market, signed=True)}**",
                ]
            )
        else:
            lines.extend(
                [
                    f"{market.upper()} — harga pasar belum lengkap.",
                    "Profit/rugi bersih total belum bisa dihitung.",
                ]
            )

        if not bucket["positions"] and bucket["complete"]:
            lines.append("Posisi terbuka: tidak ada.")
        else:
            for position in bucket["positions"]:
                lines.append(
                    f"`{position['ticker']}` {position['qty']:.4f} @ "
                    f"{_fmt_money(position['avg_price'], market)} → "
                    f"{_fmt_money(position['current'], market)} | "
                    f"{_fmt_money(position['pnl'], market, signed=True)} "
                    f"({_fmt_percent(position['pnl_pct'])})"
                )

    lines.extend(["", "**5 AKTIVITAS TERAKHIR**"])
    recent_trades = get_recent_trades(limit=5)
    if not recent_trades:
        lines.append("Anisa belum melakukan transaksi.")
    else:
        for trade in recent_trades:
            action = "Beli" if trade["action"] == "BUY" else "Jual"
            result = ""
            if trade["action"] == "SELL":
                result = (
                    " | hasil "
                    f"{_fmt_money(float(trade['realized_pnl'] or 0), trade['market'], signed=True)}"
                )
            lines.append(
                f"{action} `{trade['ticker']}` {trade['qty']:.4f} @ "
                f"{_fmt_money(float(trade['price']), trade['market'])}{result}"
            )

    lines.extend(
        [
            "",
            "Catatan: engine V1 belum memodelkan fee broker dan settlement T+2; "
            "angka tersebut tidak dibuat-buat.",
        ]
    )
    return "\n".join(lines)
```

- [ ] **Step 7: Jalankan focused report tests**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest \
  tests/test_saham_paper_trader.py::test_account_report_shows_net_realized_and_floating_pnl \
  tests/test_saham_paper_trader.py::test_account_report_does_not_guess_total_when_quote_missing \
  -q
```

Expected: PASS.

### Task 4: Pakai formatter yang sama untuk command dan recap harian

**Files:**
- Modify: `core/saham_commands.py`
- Modify: `core/saham_paper_trader.py`
- Test: `tests/test_saham_paper_trader.py`

- [ ] **Step 1: Route command ke formatter bersama**

```python
async def _build_paper_portfolio_report() -> str:
    """Laporan lengkap rekening paper-trading Anisa yang sedang aktif."""
    from core.saham_paper_trader import build_account_report

    return await asyncio.to_thread(build_account_report)
```

- [ ] **Step 2: Jadikan recap harian memakai perhitungan yang sama**

```python
def build_daily_report() -> str:
    """Recap harian dan ringkasan dompet dari satu sumber perhitungan."""
    return build_account_report(include_today_trades=True)
```

- [ ] **Step 3: Tambahkan test parity recap**

```python
def test_daily_report_uses_detailed_account_summary(monkeypatch):
    monkeypatch.setattr(
        pt,
        "fetch_snapshot",
        _fake_snapshot_factory({}),
    )

    report = pt.build_daily_report()

    assert "DOMPET ANISA — PAPER TRADING" in report
    assert "TRANSAKSI HARI INI" in report
    assert "Modal awal:" in report
    assert "HASIL BERSIH TOTAL:" in report
```

- [ ] **Step 4: Jalankan seluruh test paper trader**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python \
  -m pytest tests/test_saham_paper_trader.py -q
```

Expected: seluruh test lulus.

### Task 5: Verifikasi regresi dan catat hasil

**Files:**
- Modify: `docs/WORKLOG.md`

- [ ] **Step 1: Jalankan compile dan focused tests**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m py_compile \
  core/saham_history.py \
  core/saham_paper_trader.py \
  core/saham_commands.py \
  tests/test_saham_paper_trader.py
/home/bima_lucian/BIMA_CORE/bima_env/bin/python -m pytest \
  tests/test_saham_paper_trader.py \
  tests/test_saham_scheduler.py \
  -q
```

Expected: compile sukses dan seluruh focused test lulus.

- [ ] **Step 2: Jalankan suite repo dengan worktree diabaikan**

```bash
/home/bima_lucian/BIMA_CORE/bima_env/bin/python \
  -m pytest -q --no-header --ignore=.worktrees
```

Expected: tidak ada kegagalan baru. Kegagalan baseline yang tidak terkait harus dilaporkan apa adanya dan tidak boleh disembunyikan.

- [ ] **Step 3: Smoke report memakai salinan state aktif**

```bash
tmpdir="$(mktemp -d)"
cp /home/bima_lucian/BIMA_CORE/outputs/saham_paper_cash.json "$tmpdir/cash.json"
cp /home/bima_lucian/BIMA_CORE/outputs/saham_paper_portfolio.json "$tmpdir/portfolio.json"
cp /home/bima_lucian/BIMA_CORE/memory/saham_history.db "$tmpdir/history.db"
TMPDIR="$tmpdir" /home/bima_lucian/BIMA_CORE/bima_env/bin/python - <<'PY'
import os
from pathlib import Path

from core import saham_history as history
from core import saham_paper_trader as trader
from core import saham_portfolio as portfolio

state = Path(os.environ["TMPDIR"])
trader.CASH_PATH = state / "cash.json"
portfolio.PAPER_PORTFOLIO_PATH = state / "portfolio.json"
history.DB_PATH = state / "history.db"
print(trader.build_account_report())
PY
```

Expected: output memiliki blok IDX, GLOBAL, CRYPTO, `PROFIT/RUGI BERSIH TOTAL`, realized, floating, serta posisi terbuka. State produksi tidak ditulis.

- [ ] **Step 4: Perbarui WORKLOG**

Catat:

```markdown
## 2026-07-20 — Restore papertrade wallet summary

- Root cause: runtime branch aktif masih memakai formatter V1 lama; implementasi laporan lengkap tertinggal di branch `audit-saham-anisa`.
- Keputusan: pertahankan engine/state V1 karena database V2 kosong dan V1 memiliki posisi aktif terbaru.
- Perubahan: command dan recap harian memakai satu formatter yang menampilkan profit/rugi bersih, realized, floating, saldo, dan posisi per mata uang.
- Verifikasi: isi dengan hasil compile, focused tests, full suite, dan smoke report yang benar-benar dijalankan.
```

## Acceptance Criteria

- [ ] Posisi IDX, global, dan crypto V1 yang aktif tidak dihapus atau dimigrasikan.
- [ ] Ringkasan awal tiap rekening menampilkan modal, kekayaan sekarang, dan profit/rugi bersih total.
- [ ] Total profit jual, total rugi jual, realized bersih, dan floating P&L ditampilkan terpisah.
- [ ] Lima aktivitas terbaru ditampilkan tanpa mengubah history.
- [ ] Mata uang tidak pernah digabung menjadi satu total lintas Rp dan USD.
- [ ] Harga yang gagal diambil tidak diganti harga beli dan tidak menghasilkan profit tebakan.
- [ ] Command manual dan recap harian memakai sumber perhitungan yang sama.
- [ ] Tidak ada perubahan pada strategi, scheduler, dependency, schema, CI, atau state produksi.
- [ ] Focused tests lulus dan full-suite result dilaporkan apa adanya.
