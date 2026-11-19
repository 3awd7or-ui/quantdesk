"""Flask web app exposing the QuantDesk dashboard API and UI."""

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .. import mt5bridge
from ..backtest import run_backtest
from ..data import DataFetchError, get_ohlcv
from ..screener import scan

STATIC_DIR = Path(__file__).parent / "static"


def create_app():
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"),
                static_folder=str(STATIC_DIR), static_url_path="/static")

    @app.errorhandler(mt5bridge.MT5Unavailable)
    @app.errorhandler(mt5bridge.LiveAccountError)
    def handle_mt5_error(exc):
        return jsonify({"error": str(exc)}), 503

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

    @app.get("/api/mt5/status")
    def api_mt5_status():
        status = {"connected": False, "mt5_package_installed": mt5bridge.MT5_AVAILABLE}
        if mt5bridge.MT5_AVAILABLE:
            try:
                status = {**mt5bridge.account_status(),
                          "mt5_package_installed": True}
            except Exception:
                pass
        return jsonify(status)

    @app.post("/api/mt5/connect")
    def api_mt5_connect():
        payload = request.get_json(silent=True) or {}
        result = mt5bridge.connect(
            login=payload.get("login") or None,
            password=payload.get("password") or None,
            server=payload.get("server") or None,
            path=payload.get("path") or None,
        )
        return jsonify(result)

    @app.get("/api/mt5/signal")
    def api_mt5_signal():
        symbol = request.args.get("symbol", "XAUUSD").upper()
        timeframe = request.args.get("timeframe", "M15")
        bars = mt5bridge.get_bars_mt5(symbol, timeframe, 500)
        sessions = [tuple(map(int, s.split("-")))
                    for s in request.args.get("sessions", "").split(",") if s]
        signal = mt5bridge.evaluate_signal(
            bars, symbol=symbol,
            min_adx=float(request.args.get("min_adx", 20)),
            ema_fast=int(request.args.get("ema_fast", 20)),
            ema_slow=int(request.args.get("ema_slow", 100)),
            sessions=sessions,
        )
        return jsonify(signal.__dict__)

    @app.get("/api/mt5/positions")
    def api_mt5_positions():
        return jsonify(mt5bridge.open_positions())

    @app.post("/api/mt5/execute")
    def api_mt5_execute():
        payload = request.get_json(silent=True) or {}
        lots = float(payload.get("lots", 0.01))
        result = mt5bridge.execute_signal(payload, lots=lots)
        return jsonify(result)

    @app.post("/api/mt5/close")
    def api_mt5_close():
        payload = request.get_json(silent=True) or {}
        return jsonify(mt5bridge.close_position(int(payload["ticket"])))

    @app.post("/api/mt5/breakeven")
    def api_mt5_breakeven():
        payload = request.get_json(silent=True) or {}
        return jsonify(mt5bridge.move_stop_to_breakeven(int(payload["ticket"])))

    @app.post("/api/mt5/trailing")
    def api_mt5_trailing():
        payload = request.get_json(silent=True) or {}
        mult = float(payload.get("atr_mult", 2.0))
        return jsonify(mt5bridge.trailing_stop_update(int(payload["ticket"]), atr_mult=mult))

    return app
