"""Market data fetchers for crypto and stocks, using free public APIs."""

import csv
import io
import time
from dataclasses import dataclass

import requests

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
COINGECKO_OHLC = "https://api.coingecko.com/api/v3/coins/{id}/ohlc"
COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
STOOQ_DAILY = "https://stooq.com/q/d/l/"

BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

USER_AGENT = {"User-Agent": "quantdesk/0.1 (+https://github.com/3awd7or-ui/quantdesk)"}


@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class DataFetchError(RuntimeError):
    pass


def _get(url, params=None, timeout=15):
    try:
        resp = requests.get(url, params=params, headers=USER_AGENT, timeout=timeout)
    except requests.RequestException as exc:
        raise DataFetchError(f"network error: {exc}") from exc
    if resp.status_code != 200:
        raise DataFetchError(f"HTTP {resp.status_code} from {url}")
    return resp


def fetch_crypto_ohlcv(pair="BTCUSDT", days=365):
    """Daily OHLCV for a crypto pair. Tries Binance first, falls back to CoinGecko."""
    pair = pair.upper()
    try:
        resp = _get(BINANCE_KLINES, {"symbol": pair, "interval": "1d", "limit": 1000})
        rows = resp.json()
        bars = []
        for r in rows:
            ts = time.strftime("%Y-%m-%d", time.gmtime(r[0] / 1000))
            bars.append(Bar(ts, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))
        return bars
    except DataFetchError:
        pass

    coin_id = coingecko_resolve_id(pair)
    resp = _get(COINGECKO_OHLC.format(id=coin_id), {"vs_currency": "usd", "days": days})
    rows = resp.json()
    if not rows:
        raise DataFetchError(f"no crypto data for {pair}")
    bars = []
    for r in rows:
        ts = time.strftime("%Y-%m-%d", time.gmtime(r[0] / 1000))
        bars.append(Bar(ts, r[1], r[2], r[3], r[4]))
    return bars


def coingecko_resolve_id(pair_or_id):
    names = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
             "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2"}
    code = pair_or_id.lower().replace("usdt", "").replace("usd", "")
    if code in names:
        return names[code]
    return code


def _yahoo_chart(symbol, days):
    range_map = [(100, "3mo"), (200, "6mo"), (400, "1y"), (800, "2y")]
    rng = "1y"
    for limit, name in range_map:
        if days <= limit:
            rng = name
            break
    else:
        rng = "5y"
    resp = _get(YAHOO_CHART.format(symbol=symbol), {"range": rng, "interval": "1d"})
    result = resp.json().get("chart", {}).get("result")
    if not result:
        raise DataFetchError(f"no stock data for {symbol}")
    data = result[0]
    ts = data.get("timestamp") or []
    quote = (data.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    bars = []
    for i, t in enumerate(ts):
        close = closes[i] if i < len(closes) else None
        if close is None:
            continue
        date = time.strftime("%Y-%m-%d", time.gmtime(t))
        open_ = opens[i] if i < len(opens) and opens[i] is not None else close
        high = highs[i] if i < len(highs) and highs[i] is not None else close
        low = lows[i] if i < len(lows) and lows[i] is not None else close
        volume = volumes[i] if i < len(volumes) and volumes[i] is not None else 0.0
        bars.append(Bar(date, open_, high, low, close, volume))
    if not bars:
        raise DataFetchError(f"no stock data for {symbol}")
    return bars


def _stooq_daily(symbol, days):
    sym = symbol.lower()
    if not sym.endswith(".us") and sym.isalpha():
        sym = sym + ".us"
    end = time.strftime("%Y%m%d")
    start = time.strftime("%Y%m%d", time.gmtime(time.time() - days * 86400))
    resp = _get(STOOQ_DAILY, {"s": sym, "d1": start, "d2": end, "i": "d"})
    text = resp.text.strip()
    if not text or text.lower().startswith("no data") or text.startswith("<"):
        raise DataFetchError(f"no stock data for {symbol}")
    bars = []
    for row in csv.DictReader(io.StringIO(text)):
        bars.append(Bar(
            row["Date"],
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            float(row.get("Volume") or 0),
        ))
    if not bars:
        raise DataFetchError(f"no stock data for {symbol}")
    return bars


def fetch_stock_ohlcv(symbol="AAPL", days=365):
    """Daily OHLCV for a stock/ETF: Yahoo Finance chart API with Stooq as fallback."""
    try:
        return _yahoo_chart(symbol, days)
    except DataFetchError:
        return _stooq_daily(symbol, days)


def get_ohlcv(market, symbol, days=365):
    if market == "crypto":
        return fetch_crypto_ohlcv(symbol, days)
    if market == "stocks":
        return fetch_stock_ohlcv(symbol, days)
    raise DataFetchError(f"unknown market: {market}")


def fetch_crypto_markets(per_page=50):
    resp = _get(COINGECKO_MARKETS, {
        "vs_currency": "usd", "order": "market_cap_desc",
        "per_page": per_page, "page": 1,
    })
    return resp.json()


def fetch_stock_snapshot(symbol):
    """Latest quote snapshot: Yahoo chart meta, falling back to Stooq daily.

    Returns dict: {symbol, price, change_pct, volume}.
    """
    try:
        resp = _get(YAHOO_CHART.format(symbol=symbol), {"range": "5d", "interval": "1d"})
        result = resp.json().get("chart", {}).get("result")[0]
        meta = result["meta"]
        return {
            "symbol": meta.get("symbol", symbol.upper()),
            "price": meta.get("regularMarketPrice"),
            "change_pct": meta.get("regularMarketChangePercent") or 0.0,
            "volume": meta.get("regularMarketVolume") or 0.0,
        }
    except (DataFetchError, KeyError, IndexError, ValueError):
        pass
    sym = symbol.lower()
    if not sym.endswith(".us") and sym.isalpha():
        sym = sym + ".us"
    resp = _get(STOOQ_DAILY, {"s": sym, "i": "d"})
    text = resp.text.strip()
    if not text or text.lower().startswith("no data") or text.startswith("<"):
        raise DataFetchError(f"no stock data for {symbol}")
    rows = list(csv.DictReader(io.StringIO(text)))
    last = rows[-1]
    prev = rows[-2] if len(rows) > 1 else last
    close = float(last["Close"])
    prev_close = float(prev["Close"])
    return {
        "symbol": symbol.upper(),
        "price": close,
        "change_pct": (close / prev_close - 1) * 100 if prev_close else 0.0,
        "volume": float(last.get("Volume") or 0),
    }


def get_snapshot(market, symbol):
    if market == "crypto":
        pair = symbol.upper() if "USD" in symbol.upper() else symbol.upper() + "USDT"
        try:
            bars = fetch_crypto_ohlcv(pair, days=30)
            last, prev = bars[-1], bars[-2] if len(bars) > 1 else bars[-1]
            return {
                "symbol": symbol.upper(),
                "price": last.close,
                "change_pct": (last.close / prev.close - 1) * 100 if prev.close else 0.0,
                "volume": last.volume,
            }
        except DataFetchError:
            markets = fetch_crypto_markets(per_page=250)
            sid = symbol.lower()
            for m in markets:
                if m["id"] == sid or m["symbol"] == sid:
                    return {
                        "symbol": m["symbol"].upper(),
                        "price": m["current_price"],
                        "change_pct": m.get("price_change_percentage_24h") or 0.0,
                        "volume": m.get("total_volume") or 0.0,
                    }
            raise DataFetchError(f"unknown crypto symbol: {symbol}")
    if market == "stocks":
        return fetch_stock_snapshot(symbol)
    raise DataFetchError(f"unknown market: {market}")
