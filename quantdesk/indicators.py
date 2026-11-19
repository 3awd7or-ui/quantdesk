"""Technical indicators computed on plain lists of floats (no pandas needed)."""

from math import sqrt


def sma(values, period):
    out = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    run = 0.0
    for i, v in enumerate(values):
        run += v
        if i >= period:
            run -= values[i - period]
        if i >= period - 1:
            out[i] = run / period
    return out


def ema(values, period):
    out = [None] * len(values)
    if period <= 0 or not values:
        return out
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / min(period, len(values))
    prev = seed
    start = period - 1
    if start >= len(values):
        return out
    out[start] = prev
    for i in range(start + 1, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values, period=14):
    out = [None] * len(values)
    if len(values) <= period:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain, avg_loss):
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(values, fast=12, slow=26, signal=9):
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    line = [None if (f is None or s is None) else f - s for f, s in zip(ema_fast, ema_slow)]
    clean = [v for v in line if v is not None]
    sig_clean = ema(clean, signal)
    sig = [None] * len(values)
    offset = len(values) - len(sig_clean)
    for i, v in enumerate(sig_clean):
        sig[offset + i] = v
    hist = [None if (l is None or s is None) else l - s for l, s in zip(line, sig)]
    return line, sig, hist


def atr(highs, lows, closes, period=14):
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    prev = sum(trs[1:period + 1]) / period
    out[period] = prev
    for i in range(period + 1, len(closes)):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


def bollinger(values, period=20, num_std=2.0):
    mid = sma(values, period)
    upper = [None] * len(values)
    lower = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        mean = mid[i]
        var = sum((v - mean) ** 2 for v in window) / period
        sd = sqrt(var)
        upper[i] = mean + num_std * sd
        lower[i] = mean - num_std * sd
    return mid, upper, lower


def last_valid(series):
    for v in reversed(series):
        if v is not None:
            return v
    return None
