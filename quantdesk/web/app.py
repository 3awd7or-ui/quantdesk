"""Flask web app exposing the QuantDesk dashboard API and UI."""

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from ..backtest import run_backtest
from ..data import DataFetchError, get_ohlcv
from ..screener import scan

STATIC_DIR = Path(__file__).parent / "static"


def create_app():
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"),
                static_folder=str(STATIC_DIR), static_url_path="/static")

    @app.errorhandler(DataFetchError)
    def handle_fetch_error(exc):
        return jsonify({"error": str(exc)}), 502

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/ohlcv")
    def api_ohlcv():
        market = request.args.get("market", "crypto")
        symbol = request.args.get("symbol", "BTCUSDT")
        days = min(int(request.args.get("days", 365)), 1000)
        bars = get_ohlcv(market, symbol, days=days)
        return jsonify([{"date": b.date, "open": b.open, "high": b.high,
                         "low": b.low, "close": b.close, "volume": b.volume}
                        for b in bars])

    @app.get("/api/backtest")
    def api_backtest():
        market = request.args.get("market", "crypto")
        symbol = request.args.get("symbol", "BTCUSDT")
        if symbol.lower() in ("btc", "bitcoin"):
            symbol = "BTCUSDT" if market == "crypto" else symbol
        days = min(int(request.args.get("days", 365)), 1000)
        strategy = request.args.get("strategy", "sma")
        capital = float(request.args.get("capital", 10000))
        fee = float(request.args.get("fee", 0.001))
        params = {}
        if strategy == "sma":
            params = {"fast": int(request.args.get("fast", 20)),
                      "slow": int(request.args.get("slow", 50))}
        elif strategy == "rsi":
            params = {"period": int(request.args.get("rsi_period", 14)),
                      "buy": float(request.args.get("buy", 30)),
                      "sell": float(request.args.get("sell", 70))}
        bars = get_ohlcv(market, symbol, days=days)
        result = run_backtest(bars, strategy, initial_capital=capital, fee=fee, **params)
        return jsonify({
            "metrics": result.metrics,
            "equity_curve": result.equity_curve,
            "trades": [{"entry_date": t.entry_date, "entry_price": t.entry_price,
                        "exit_date": t.exit_date, "exit_price": t.exit_price}
                       for t in result.trades],
        })

    @app.get("/api/screen")
    def api_screen():
        market = request.args.get("market", "crypto")
        min_rsi = float(request.args.get("min_rsi", 0))
        max_rsi = float(request.args.get("max_rsi", 100))
        above_sma = int(request.args.get("above_sma", 0))
        min_change = request.args.get("min_change")
        min_change = float(min_change) if min_change not in (None, "") else None
        result = scan(market, min_rsi=min_rsi, max_rsi=max_rsi,
                      above_sma=above_sma, min_change_pct=min_change)
        return jsonify(result)

    return app
