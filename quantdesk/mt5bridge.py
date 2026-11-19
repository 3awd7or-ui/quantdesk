"""MetaTrader 5 bridge: connection, signal engine, order execution and management.

Requires the MetaTrader5 package and a running MT5 terminal (Windows only).
Everything here degrades gracefully when MT5 is absent: signal math and data
conversion stay testable everywhere, execution functions raise MT5Unavailable.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .data import Bar
from .indicators import adx, atr, ema, last_valid

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False


class MT5Unavailable(RuntimeError):
    pass


class LiveAccountError(RuntimeError):
    """Refused: target account is not a demo account."""


DEMO_TRADING_ENABLED = {"live_ack": False}
ALLOWED_TIMEFRAMES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}


@dataclass
class Signal:
    action: str
    symbol: str
    score: int
    entry: float
    sl: float
    tp1: float
    tp2: float
    reasons: list = field(default_factory=list)
    blocked_reason: str = ""


def require_mt5():
    if not MT5_AVAILABLE:
        raise MT5Unavailable(
            "MetaTrader5 غير مثبتة — ثبّتها على ويندوز عبر: pip install MetaTrader5 "
            "وتأكد أن منصة MT5 تعمل (أو استخدم وضع الإشارات فقط signal-only)"
        )
    return mt5


def connect(login=None, password=None, server=None, path=None):
    """Initialize MT5 terminal and optionally log into an account."""
    lib = require_mt5()
    kwargs = {}
    if path:
        kwargs["path"] = path
    if not lib.initialize(**kwargs):
        raise MT5Unavailable(f"فشل الاتصال بالمنصة: {lib.last_error()}")
    if login:
        if not lib.login(int(login), password=password, server=server):
            raise MT5Unavailable(f"فشل تسجيل الدخول: {lib.last_error()}")
    info = account_info()
    return {
        "connected": True,
        "login": info["login"],
        "name": info["name"],
        "server": info["server"],
        "balance": info["balance"],
        "equity": info["equity"],
        "is_demo": is_demo_account(),
    }


def disconnect():
    if MT5_AVAILABLE:
        mt5.shutdown()


def account_info():
    lib = require_mt5()
    info = lib.account_info()
    if info is None:
        raise MT5Unavailable("لا يوجد حساب متصل")
    return {
        "login": info.login,
        "name": info.name,
        "server": info.server,
        "balance": info.balance,
        "equity": info.equity,
        "margin_free": info.margin_free,
        "currency": info.currency,
        "trade_mode": info.trade_mode,
    }


def is_demo_account():
    info = account_info()
    return info["trade_mode"] == 0


def get_bars_mt5(symbol, timeframe="M15", count=500):
    """Copy bars from MT5 as plain Bar list."""
    lib = require_mt5()
    tf = getattr(lib, f"TIMEFRAME_{timeframe}", None)
    if tf is None:
        raise ValueError(f"إطار زمني غير مدعوم: {timeframe}")
    rates = lib.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        raise MT5Unavailable(f"لا بيانات للرمز {symbol}: {lib.last_error()}")
    return [Bar(
        datetime.fromtimestamp(int(r["time"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        float(r["open"]), float(r["high"]), float(r["low"]),
        float(r["close"]), float(r["tick_volume"]),
    ) for r in rates]


def _in_session(now_hour_utc, sessions):
    for start, end in sessions:
        if start <= end:
            if start <= now_hour_utc < end:
                return True
        elif now_hour_utc >= start or now_hour_utc < end:
            return True
    return not sessions


def evaluate_signal(bars, symbol="XAUUSD", min_adx=20.0, ema_fast=20, ema_slow=100,
                    adx_period=14, atr_sl_mult=1.5, atr_tp1_mult=1.5, atr_tp2_mult=3.0,
                    sessions=None, cooldown_open_ge=None, max_spread_points=None):
    """Score a setup on a Bar list: returns Signal dict (never executes)."""
    if len(bars) < ema_slow + adx_period * 2:
        return Signal("none", symbol, 0, 0.0, 0.0, 0.0, 0.0,
                      [], blocked_reason="بيانات غير كافية")
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    closes = [b.close for b in bars]

    ema_f = last_valid(ema(closes, ema_fast))
    ema_s = last_valid(ema(closes, ema_slow))
    adx_v = last_valid(adx(highs, lows, closes, adx_period)[0])
    atr_v = last_valid(atr(highs, lows, closes, adx_period)) or 0.0
    price = closes[-1]

    score, reasons, action = 0, [], "none"
    if ema_f is not None and ema_s is not None:
        trend_up = ema_f > ema_s * 1.0005
        trend_down = ema_f < ema_s * 0.9995
        if trend_up:
            score += 35
            action = "buy"
            reasons.append("EMA20 > EMA100 (اتجاه صاعد)")
        elif trend_down:
            score += 35
            action = "sell"
            reasons.append("EMA20 < EMA100 (اتجاه هابط)")
    if adx_v is not None and adx_v >= min_adx:
        score += 30
        reasons.append(f"ADX={adx_v:.1f} (اتجاه قوي ≥ {min_adx})")
    # momentum of the last completed candle
    body = abs(closes[-1] - closes[-2])
    if atr_v > 0 and body >= atr_v * 0.5:
        score += 15
        reasons.append("شمعة دافعة ≥ 0.5×ATR")

    now_hour = datetime.now(tz=timezone.utc).hour
    session_ok = _in_session(now_hour, sessions or []
                             )
    if sessions:
        if session_ok:
            score += 20
            reasons.append("داخل جلسة التداول المسموحة")
        else:
            return Signal("none", symbol, score, price, 0, 0, 0, reasons,
                          blocked_reason="خارج جلسة التداول")
    if adx_v is None or adx_v < min_adx:
        return Signal("none", symbol, score, price, 0, 0, 0, reasons,
                      blocked_reason=f"ADX ضعيف ({(adx_v or 0):.1f} < {min_adx}) — BLOCKED")

    if cooldown_open_ge is not None and cooldown_open_ge > 0:
        return Signal(action if score >= 50 else "none", symbol, score, price,
                      0, 0, 0, reasons, blocked_reason="فترة كولداون نشطة")

    signal = Signal(action if score >= 50 else "none", symbol, min(score, 100),
                    price, 0, 0, 0, reasons)
    if atr_v > 0 and signal.action != "none":
        sign = -1 if action == "sell" else 1
        signal.sl = round(price - sign * atr_sl_mult * atr_v, 3)
        signal.tp1 = round(price + sign * atr_tp1_mult * atr_v, 3)
        signal.tp2 = round(price + sign * atr_tp2_mult * atr_v, 3)
    elif signal.action != "none":
        signal.blocked_reason = "ATR غير متاح — لا يمكن تحديد SL/TP"
        signal.action = "none"
    return signal


def open_positions(symbol=None):
    lib = require_mt5()
    positions = lib.positions_get(symbol=symbol) if symbol else lib.positions_get()
    return [{
        "ticket": p.ticket, "symbol": p.symbol, "type": "buy" if p.type == 0 else "sell",
        "volume": p.volume, "price_open": p.price_open,
        "price_current": p.price_current, "sl": p.sl, "tp": p.tp,
        "profit": round(p.profit, 2), "time":
        datetime.fromtimestamp(p.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
    } for p in (positions or [])]


def execute_signal(signal, lots=0.01, comment="quantdesk"):
    """Send a market order with sl/tp = tp1 mid-managed; tp2 via trailing later.

    Hardcoded safety: refuses non-demo accounts unless explicitly unlocked.
    """
    lib = require_mt5()
    if not is_demo_account() and not DEMO_TRADING_ENABLED["live_ack"]:
        raise LiveAccountError("الحساب حقيقي — التنفيذ معطّل تلقائياً. فعّله صراحة عندك على مسؤوليتك.")
    if signal["action"] not in ("buy", "sell"):
        raise ValueError("الإشارة ليست صالحة للتنفيذ")
    symbol = signal["symbol"]
    tick = lib.symbol_info_tick(symbol)
    if tick is None:
        raise MT5Unavailable(f"الرمز {symbol} غير متاح في حسابك — افتح Market Watch أولاً")
    price = tick.ask if signal["action"] == "buy" else tick.bid
    order_type = lib.ORDER_TYPE_BUY if signal["action"] == "buy" else lib.ORDER_TYPE_SELL
    request = {
        "action": lib.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lots),
        "type": order_type,
        "price": price,
        "sl": signal["sl"],
        "tp": signal["tp2"],
        "deviation": 20,
        "magic": 777001,
        "comment": comment,
        "type_time": lib.ORDER_TIME_GTC,
        "type_filling": lib.ORDER_FILLING_IOC,
    }
    result = lib.order_send(request)
    if result is None or result.retcode != lib.TRADE_RETCODE_DONE:
        code = getattr(result, "retcode", None)
        raise MT5Unavailable(f"فشل إرسال الأمر: retcode={code} · {lib.last_error()}")
    return {
        "ticket": result.order, "price": result.price, "volume": result.volume,
        "sl": signal["sl"], "tp1": signal["tp1"], "tp2": signal["tp2"],
    }


def close_position(ticket):
    lib = require_mt5()
    positions = lib.positions_get(ticket=ticket)
    if not positions:
        raise MT5Unavailable(f"لا توجد صفقة برقم {ticket}")
    p = positions[0]
    tick = lib.symbol_info_tick(p.symbol)
    is_buy = p.type == 0
    request = {
        "action": lib.TRADE_ACTION_DEAL,
        "symbol": p.symbol,
        "volume": p.volume,
        "type": lib.ORDER_TYPE_SELL if is_buy else lib.ORDER_TYPE_BUY,
        "position": ticket,
        "price": tick.bid if is_buy else tick.ask,
        "deviation": 20,
        "magic": 777001,
        "comment": "quantdesk-close",
        "type_filling": lib.ORDER_FILLING_IOC,
    }
    result = lib.order_send(request)
    if result is None or result.retcode != lib.TRADE_RETCODE_DONE:
        raise MT5Unavailable(f"فشل الإغلاق: retcode={getattr(result, 'retcode', None)}")
    return {"closed": ticket, "price": result.price}


def move_stop_to_breakeven(ticket):
    lib = require_mt5()
    positions = lib.positions_get(ticket=ticket)
    if not positions:
        raise MT5Unavailable(f"لا توجد صفقة برقم {ticket}")
    p = positions[0]
    is_buy = p.type == 0
    tick = lib.symbol_info_tick(p.symbol)
    new_sl = p.price_open if is_buy else p.price_open
    request = {
        "action": lib.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": p.symbol,
        "sl": new_sl,
        "tp": p.tp,
    }
    result = lib.order_send(request)
    if result is None or result.retcode != lib.TRADE_RETCODE_DONE:
        raise MT5Unavailable(f"فشل نقل SL: retcode={getattr(result, 'retcode', None)}")
    return {"ticket": ticket, "sl": new_sl}


def trailing_stop_update(ticket, atr_mult=2.0, step=0.5):
    """Slide SL behind price by ATR multiple once profit > 1 ATR."""
    lib = require_mt5()
    positions = lib.positions_get(ticket=ticket)
    if not positions:
        raise MT5Unavailable(f"لا توجد صفقة برقم {ticket}")
    p = positions[0]
    is_buy = p.type == 0
    bars = get_bars_mt5(p.symbol, "M15", 100)
    atr_v = last_valid(atr([b.high for b in bars], [b.low for b in bars],
                           [b.close for b in bars], 14)) or 0.0
    if atr_v <= 0:
        return {"ticket": ticket, "trailing": False, "reason": "ATR غير متاح"}
    tick = lib.symbol_info_tick(p.symbol)
    price = tick.ask if is_buy else tick.bid
    current = price - p.price_open if is_buy else p.price_open - price
    if current < atr_v:
        return {"ticket": ticket, "trailing": False, "reason": "الربح أقل من 1 ATR"}
    new_sl = (price - atr_mult * atr_v) if is_buy else (price + atr_mult * atr_v)
    new_sl = round(new_sl, 3)
    if (is_buy and p.sl >= new_sl) or (not is_buy and p.sl and p.sl <= new_sl):
        return {"ticket": ticket, "trailing": False, "reason": "SL محدّث بالفعل"}
    request = {"action": lib.TRADE_ACTION_SLTP, "position": ticket,
               "symbol": p.symbol, "sl": new_sl, "tp": p.tp}
    result = lib.order_send(request)
    if result is None or result.retcode != lib.TRADE_RETCODE_DONE:
        raise MT5Unavailable(f"فشل التحديث: retcode={getattr(result, 'retcode', None)}")
    return {"ticket": ticket, "trailing": True, "sl": new_sl}


def account_status():
    if not MT5_AVAILABLE or mt5.account_info() is None:
        return {"connected": False}
    info = account_info()
    return {
        "connected": True,
        "login": info["login"],
        "server": info["server"],
        "balance": info["balance"],
        "equity": info["equity"],
        "currency": info["currency"],
        "is_demo": is_demo_account(),
        "auto_trading_allowed": bool(mt5.terminal_info().trade_allowed),
    }
