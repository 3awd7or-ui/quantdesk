import unittest

from quantdesk.indicators import atr, bollinger, ema, last_valid, macd, rsi, sma
from quantdesk.backtest import BacktestResult, run_backtest
from quantdesk.data import Bar
from quantdesk.screener import scan


def series(n=100, start=100.0, drift=0.2):
    return [start + drift * i for i in range(n)]


def oscillating(n=180, base=100.0, amp=15.0, rise=0.3):
    """Rising trend with waves, forces SMA crossover exits."""
    from math import sin
    return [base + rise * i + amp * sin(i / 9.0) for i in range(n)]


class TestIndicators(unittest.TestCase):
    def test_sma_constant(self):
        self.assertEqual(sma([5.0] * 10, 5)[9], 5.0)
        self.assertIsNone(sma([5.0] * 10, 5)[3])

    def test_sma_known_values(self):
        self.assertIsNone(sma([1, 2, 3], 4)[2])
        self.assertAlmostEqual(sma([1, 2, 3, 4], 2)[3], 3.5)

    def test_ema_converges(self):
        line = ema(series(200, 100, 0), 10)
        self.assertAlmostEqual(line[-1], 100.0, delta=0.1)

    def test_rsi_bounds(self):
        values = series(60)
        out = rsi(values, 14)
        self.assertTrue(all(0 <= v <= 100 for v in out if v is not None))
        self.assertAlmostEqual(out[-1], 100.0)

    def test_rsi_none_when_short(self):
        self.assertTrue(all(v is None for v in rsi([1, 2, 3], 14)))

    def test_macd_alignment(self):
        values = series(80)
        line, sig, hist = macd(values)
        self.assertEqual(len(line), len(values))
        self.assertEqual(len(sig), len(values))
        self.assertEqual(len(hist), len(values))
        self.assertIsNotNone(line[-1])
        self.assertAlmostEqual(hist[-1], line[-1] - sig[-1])

    def test_atr(self):
        bars_h = series(30, 105, 0.2)
        bars_l = series(30, 95, 0.2)
        closes = series(30)
        out = atr(bars_h, bars_l, closes, 14)
        self.assertIsNotNone(out[-1])
        self.assertIsInstance(out[-1], float)

    def test_bollinger(self):
        values = series(40)
        _, upper, lower = bollinger(values, 20, 2.0)
        self.assertGreater(upper[-1], lower[-1])
        self.assertIsNone(upper[10])

    def test_last_valid(self):
        self.assertEqual(last_valid([None, 2.0, None, 7.5]), 7.5)


def bars_from(closes, base_date="2024-01-01"):
    from datetime import date, timedelta
    day = date(2024, 1, 1)
    bars = []
    for i, c in enumerate(closes):
        bars.append(Bar((day + timedelta(days=i)).isoformat(), c, c * 1.01, c * 0.99, c))
    return bars


class TestBacktest(unittest.TestCase):
    def test_oscillating_uptrend_produces_profitable_trades(self):
        closes = oscillating(180)
        result = run_backtest(bars_from(closes), "sma", fast=5, slow=20)
        self.assertGreater(result.metrics["total_return_pct"], 0)
        self.assertGreater(result.metrics["trades"], 0)
        self.assertEqual(len(result.equity_curve), len(closes))

    def test_rsi_never_fires_on_monotonic_rise(self):
        closes = series(60, 100, 1.0)
        result = run_backtest(bars_from(closes), "rsi")
        self.assertEqual(result.metrics["trades"], 0)
        self.assertAlmostEqual(result.metrics["final_equity"], 10_000.0)

    def test_metrics_fields(self):
        result = run_backtest(bars_from(series(80)), "sma", fast=5, slow=10)
        for key in ("total_return_pct", "sharpe", "max_drawdown_pct", "trades",
                    "win_rate_pct", "final_equity", "buy_hold_return_pct"):
            self.assertIn(key, result.metrics)
        self.assertIsInstance(result, BacktestResult)

    def test_unknown_strategy(self):
        with self.assertRaises(ValueError):
            run_backtest(bars_from(series(30)), "nope")

    def test_no_bars(self):
        with self.assertRaises(ValueError):
            run_backtest([], "sma")


class TestScreener(unittest.TestCase):
    def test_scan_filters_with_error_handling(self):
        result = scan("crypto", symbols=["BTCUSDT", "BAD??PAIR"], days=120)
        self.assertTrue(any(r["symbol"] == "BTCUSDT" for r in result["rows"]))
        self.assertTrue(any(e["symbol"] == "BAD??PAIR" for e in result["errors"]))
        for row in result["rows"]:
            self.assertLessEqual(row["rsi"], 100)

    def test_rows_sorted_by_rsi(self):
        result = scan("crypto", symbols=["BTCUSDT", "ETHUSDT"], days=150)
        rsi_values = [r["rsi"] for r in result["rows"]]
        self.assertEqual(rsi_values, sorted(rsi_values, reverse=True))


if __name__ == "__main__":
    unittest.main()
