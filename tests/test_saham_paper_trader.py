import asyncio

import pytest

from core import saham_history as hist
from core import saham_paper_trader as pt
from core import saham_portfolio as port


class _FakeDecisionEngine:
    """Stand-in DecisionEngineTool — skor dikontrol lewat atribut instance."""

    def __init__(self, score: int = 78):
        self.score = score

    def _run(self, symbol: str) -> str:
        if self.score >= 70:
            verdict = "🟢 STRONG BUY"
        elif self.score <= 30:
            verdict = "🔴 STRONG SELL"
        else:
            verdict = "🟡 HOLD"
        return (
            f"=== KEPUTUSAN: {symbol} ===\n"
            f"Harga saat ini : 100.00\n"
            f"Skor           : {self.score}/100\n"
            f"Keputusan      : {verdict}\n"
        )


def _fake_snapshot_factory(ticker_map):
    def _snap(symbol):
        value = ticker_map[symbol]
        if isinstance(value, Exception):
            raise value
        return value
    return _snap


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


@pytest.fixture(autouse=True)
def isolate_storage(tmp_path, monkeypatch):
    """Redirect semua storage (cash, paper/real portfolio, history db) ke tmp_path."""
    monkeypatch.setattr(pt, "CASH_PATH", tmp_path / "saham_paper_cash.json")
    monkeypatch.setattr(port, "PAPER_PORTFOLIO_PATH", tmp_path / "saham_paper_portfolio.json")
    monkeypatch.setattr(port, "PORTFOLIO_PATH", tmp_path / "saham_portfolio.json")
    monkeypatch.setattr(hist, "DB_PATH", tmp_path / "saham_history.db")
    yield


def test_bucket_of_classifies_market():
    assert pt._bucket_of("BBCA.JK") == "idx"
    assert pt._bucket_of("BTC-USD") == "crypto"
    assert pt._bucket_of("AAPL") == "global"


def test_parse_decision_extracts_score_and_verdict():
    text = _FakeDecisionEngine(score=78)._run("BBCA.JK")
    score, verdict = pt._parse_decision(text)
    assert score == 78
    assert "STRONG BUY" in verdict


def test_parse_decision_returns_none_when_unparseable():
    score, verdict = pt._parse_decision("gagal ambil data")
    assert score is None
    assert verdict == ""


def test_extract_realized_pnl_parses_signed_amounts():
    assert pt._extract_realized_pnl("... realized P&L: +15,000.00") == 15000.0
    assert pt._extract_realized_pnl("... realized P&L: -8,000.00") == -8000.0
    assert pt._extract_realized_pnl("tidak ada info pnl") is None


def test_decide_and_trade_buys_on_strong_buy_signal(monkeypatch):
    monkeypatch.setattr(pt, "DecisionEngineTool", lambda: _FakeDecisionEngine(score=78))
    monkeypatch.setattr(pt, "fetch_snapshot", _fake_snapshot_factory({
        "BBCA": {"ticker": "BBCA.JK", "close": 5800.0},
    }))

    result = pt.decide_and_trade("BBCA", {})

    assert result is not None
    assert result.action == "BUY"
    assert result.ticker == "BBCA.JK"
    assert result.market == "idx"
    assert result.qty == pytest.approx(2_000_000.0 / 5800.0)
    assert result.cash_after == pytest.approx(8_000_000.0)
    assert result.equity_after == pytest.approx(10_000_000.0)
    assert "BBCA.JK" in port.list_positions(account="paper")


def test_decide_and_trade_holds_when_score_is_neutral(monkeypatch):
    monkeypatch.setattr(pt, "DecisionEngineTool", lambda: _FakeDecisionEngine(score=50))
    monkeypatch.setattr(pt, "fetch_snapshot", _fake_snapshot_factory({
        "BBCA": {"ticker": "BBCA.JK", "close": 5800.0},
    }))

    result = pt.decide_and_trade("BBCA", {})

    assert result is None
    assert port.list_positions(account="paper") == {}


def test_decide_and_trade_does_not_buy_past_max_concurrent_positions(monkeypatch):
    for i in range(pt.MAX_CONCURRENT_POSITIONS):
        # suffix .JK eksplisit — ticker ber-digit ("FAKE0") gak lolos heuristik
        # normalisasi_ticker (isalpha() gagal), jadi gak akan masuk bucket idx.
        port.add_position(f"FAKE{i}.JK", 10, 100.0, account="paper")
    pt._save_cash({"idx": 10_000_000.0, "global": 1_000.0, "crypto": 500.0})

    monkeypatch.setattr(pt, "DecisionEngineTool", lambda: _FakeDecisionEngine(score=78))
    monkeypatch.setattr(pt, "fetch_snapshot", _fake_snapshot_factory({
        "BBCA": {"ticker": "BBCA.JK", "close": 5800.0},
    }))

    result = pt.decide_and_trade("BBCA", {})

    assert result is None
    assert "BBCA.JK" not in port.list_positions(account="paper")


def test_decide_and_trade_sells_existing_position_on_strong_sell(monkeypatch):
    port.add_position("BBCA", 100, 5000.0, account="paper")
    pt._save_cash({"idx": 9_500_000.0, "global": 1_000.0, "crypto": 500.0})

    monkeypatch.setattr(pt, "DecisionEngineTool", lambda: _FakeDecisionEngine(score=20))
    monkeypatch.setattr(pt, "fetch_snapshot", _fake_snapshot_factory({
        "BBCA": {"ticker": "BBCA.JK", "close": 5800.0},
    }))

    result = pt.decide_and_trade("BBCA", {})

    assert result is not None
    assert result.action == "SELL"
    assert result.realized_pnl == pytest.approx((5800.0 - 5000.0) * 100)
    assert result.cash_after == pytest.approx(9_500_000.0 + 100 * 5800.0)
    assert port.list_positions(account="paper") == {}


def test_run_tick_skips_ticker_errors_and_collects_rest(monkeypatch):
    monkeypatch.setattr(pt, "DecisionEngineTool", lambda: _FakeDecisionEngine(score=78))
    monkeypatch.setattr(pt, "fetch_snapshot", _fake_snapshot_factory({
        "BROKEN": RuntimeError("yfinance down"),
        "GOOD": {"ticker": "GOOD.JK", "close": 1000.0},
    }))
    monkeypatch.setattr(pt, "MARKET_WATCHLIST", {**pt.MARKET_WATCHLIST, "idx": ["BROKEN", "GOOD"]})

    results = pt.run_tick("idx")

    assert len(results) == 1
    assert results[0].ticker == "GOOD.JK"


def test_history_log_and_query_roundtrip():
    entry = hist.TradeLogEntry(
        ticker="BBCA.JK", market="idx", action="BUY", qty=100.0, price=5800.0,
        score=78, verdict="🟢 STRONG BUY", reasoning="test", realized_pnl=None,
        cash_after=9_420_000.0, equity_after=10_000_000.0,
    )
    hist.log_trade(entry)

    trades = hist.get_today_trades(market="idx")

    assert len(trades) == 1
    assert trades[0]["ticker"] == "BBCA.JK"
    assert trades[0]["action"] == "BUY"
    assert trades[0]["realized_pnl"] is None


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
    assert "Simulasi ini belum menghitung fee broker dan settlement T+2." in report


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


def test_money_and_percent_formatters_do_not_show_negative_zero():
    assert pt._fmt_money(-0.001, "crypto", signed=True) == "$0,00"
    assert pt._fmt_percent(-0.001) == "+0,00%"


def test_daily_report_uses_detailed_account_summary(monkeypatch):
    monkeypatch.setattr(pt, "fetch_snapshot", _fake_snapshot_factory({}))

    report = pt.build_daily_report()

    assert "DOMPET ANISA — PAPER TRADING" in report
    assert "TRANSAKSI HARI INI" in report
    assert "Modal awal:" in report
    assert "HASIL BERSIH TOTAL:" in report


def test_command_report_uses_shared_account_builder(monkeypatch):
    from core import saham_commands as commands

    monkeypatch.setattr(pt, "build_account_report", lambda: "shared-report")

    report = asyncio.run(commands._build_paper_portfolio_report())

    assert report == "shared-report"


def test_portfolio_real_and_paper_accounts_are_isolated():
    port.add_position("TLKM", 200, 3000.0, account="real")
    port.add_position("TLKM", 50, 3200.0, account="paper")

    real_positions = port.list_positions(account="real")
    paper_positions = port.list_positions(account="paper")

    assert real_positions["TLKM.JK"][0]["qty"] == 200
    assert paper_positions["TLKM.JK"][0]["qty"] == 50
