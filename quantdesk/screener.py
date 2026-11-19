"""Screener that scans symbols by technical filters."""

from .data import DataFetchError, get_ohlcv
from .indicators import rsi, sma

DEFAULT_CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                  "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
                  "MATICUSDT", "LTCUSDT"]
DEFAULT_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                  "JPM", "V", "XOM", "KO", "DIS"]


def scan(market, symbols=None, days=365, min_rsi=0.0, max_rsi=100.0,
         above_sma=0, min_change_pct=None, max_rows=100):
    """Scan symbols; above_sma>0 keeps rows with last close above that SMA period."""
    if symbols is None:
        symbols = DEFAULT_CRYPTO if market == "crypto" else DEFAULT_STOCKS
    rows = []
    errors = []
    for symbol in symbols:
        try:
            bars = get_ohlcv(market, symbol, days=days)
        except DataFetchError as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
            continue
        if len(bars) < 15:
            errors.append({"symbol": symbol, "error": "insufficient history"})
            continue
        closes = [b.close for b in bars]
        last = closes[-1]
        prev = closes[-2]
        rsi_series = rsi(closes)
        rsi_value = next((v for v in reversed(rsi_series) if v is not None), 50.0)
        sma_series = sma(closes, above_sma) if above_sma > 0 else None
        sma_value = None
        if sma_series is not None:
            sma_value = next((v for v in reversed(sma_series) if v is not None), None)
        volume = bars[-1].volume

        change_pct = (last / prev - 1) * 100 if prev else 0.0
        if min_rsi <= rsi_value <= max_rsi:
            if sma_value is None or last >= sma_value:
                if min_change_pct is None or change_pct >= min_change_pct:
                    rows.append({
                        "symbol": symbol,
                        "price": round(last, 4),
                        "change_pct": round(change_pct, 2),
                        "rsi": round(rsi_value, 1),
                        "sma": round(sma_value, 4) if sma_value is not None else None,
                        "volume": round(volume, 0),
                    })
        if len(rows) >= max_rows:
            break
    rows.sort(key=lambda r: r["rsi"], reverse=True)
    return {"rows": rows, "errors": errors}
