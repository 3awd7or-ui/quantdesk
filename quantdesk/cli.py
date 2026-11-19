"""QuantDesk command line interface."""

import argparse
import sys

from .backtest import run_backtest
from .data import DataFetchError, get_ohlcv, get_snapshot
from .indicators import last_valid, rsi, sma
from .mt5bridge import LiveAccountError, MT5Unavailable
from .screener import scan


def cmd_price(args):
    snap = get_snapshot(args.market, args.symbol)
    print(f"{snap['symbol']:>10}  price={snap['price']:,.4f}  change={snap['change_pct']:+.2f}%")


def cmd_indicators(args):
    bars = get_ohlcv(args.market, args.symbol, days=args.days)
    closes = [b.close for b in bars]
    print(f"bars={len(bars)}  last={closes[-1]:,.4f}  {bars[-1].date}")
    for period in args.sma:
        line = sma(closes, period)
        value = last_valid(line)
        print(f"  SMA{period}: {value:,.4f}" if value is not None else f"  SMA{period}: n/a")
    rsi_series = rsi(closes, args.rsi_period)
    value = last_valid(rsi_series)
    print(f"  RSI{args.rsi_period}: {value:.1f}" if value is not None else "  RSI: n/a")


def cmd_backtest(args):
    bars = get_ohlcv(args.market, args.symbol, days=args.days)
    if args.strategy == "sma":
        params = {"fast": args.fast, "slow": args.slow}
    else:
        params = {"period": args.rsi_period, "buy": args.buy, "sell": args.sell}
    result = run_backtest(bars, args.strategy, initial_capital=args.capital, fee=args.fee, **params)
    m = result.metrics
    print(f"strategy={args.strategy}  market={args.market}  symbol={args.symbol.upper()}  bars={len(bars)}")
    for key in ("total_return_pct", "buy_hold_return_pct", "annualized_return_pct",
                "sharpe", "max_drawdown_pct", "trades", "win_rate_pct", "final_equity"):
        print(f"  {key}: {m[key]}")


def cmd_screen(args):
    result = scan(args.market, min_rsi=args.min_rsi, max_rsi=args.max_rsi,
                  above_sma=args.above_sma, min_change_pct=args.min_change)
    if not result["rows"]:
        print("لا نتائج مطابقة للفلاتر.")
        for err in result["errors"][:5]:
            print(f"  ! {err['symbol']}: {err['error']}")
        return
    header = f"{'الرمز':<10}{'السعر':>12}{'التغير٪':>10}{'RSI':>8}{'SMA':>12}"
    print(header)
    for row in result["rows"]:
        sma_txt = f"{row['sma']:,.2f}" if row["sma"] is not None else "-"
        print(f"{row['symbol']:<10}{row['price']:>12,.4f}{row['change_pct']:>9.2f}%{row['rsi']:>8.1f}{sma_txt:>12}")
    if result["errors"]:
        print(f"({len(result['errors'])} رمز فشل جلبه — راجع سجل الأخطاء)")


def cmd_tui(args):
    from .tui import run
    run(market=args.market, refresh_seconds=args.refresh)


def cmd_web(args):
    from .web.app import create_app
    app = create_app()
    app.run(host=args.host, port=args.port, debug=False)


def cmd_mt5(args):
    from . import mt5bridge
    if args.command == "mt5-connect":
        print(mt5bridge.connect(login=args.login, password=args.password, server=args.server))
    elif args.command == "mt5-signal":
        bars = mt5bridge.get_bars_mt5(args.symbol, args.timeframe, 500)
        signal = mt5bridge.evaluate_signal(bars, symbol=args.symbol.upper(),
                                           min_adx=args.min_adx,
                                           ema_fast=args.ema_fast, ema_slow=args.ema_slow)
        print(f"{signal.action.upper():<6} score={signal.score}/100  entry={signal.entry}  "
              f"SL={signal.sl}  TP1={signal.tp1}  TP2={signal.tp2}")
        for reason in signal.reasons:
            print(f"  • {reason}")
        if signal.blocked_reason:
            print(f"  ممنوع: {signal.blocked_reason}")
    elif args.command == "mt5-positions":
        positions = mt5bridge.open_positions()
        if not positions:
            print("لا عُقود مفتوحة.")
            return
        for p in positions:
            print(f"#{p['ticket']}  {p['symbol']:<8}{p['type']:<5}{p['volume']:>6.2f} لوت  "
                  f"دخول={p['price_open']}  الآن={p['price_current']}  "
                  f"SL={p['sl']}  TP={p['tp']}  ربح={p['profit']}")
    elif args.command == "mt5-trail":
        print(mt5bridge.trailing_stop_update(args.ticket, atr_mult=args.mult))
    elif args.command == "mt5-close":
        print(mt5bridge.close_position(args.ticket))


def build_parser():
    parser = argparse.ArgumentParser(prog="quantdesk", description="QuantDesk — أدوات تداول كمّي")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("price", help="سعر لحظي")
    p.add_argument("market", choices=["crypto", "stocks"])
    p.add_argument("symbol")
    p.set_defaults(func=cmd_price)

    p = sub.add_parser("indicators", help="مؤشرات فنية لرمز")
    p.add_argument("market", choices=["crypto", "stocks"])
    p.add_argument("symbol")
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--sma", type=int, nargs="*", default=[20, 50])
    p.add_argument("--rsi-period", type=int, default=14)
    p.set_defaults(func=cmd_indicators)

    p = sub.add_parser("backtest", help="اختبار تاريخي لاستراتيجية")
    p.add_argument("market", choices=["crypto", "stocks"])
    p.add_argument("symbol")
    p.add_argument("--strategy", choices=["sma", "rsi"], default="sma")
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--capital", type=float, default=10_000.0)
    p.add_argument("--fee", type=float, default=0.001)
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--rsi-period", type=int, default=14)
    p.add_argument("--buy", type=float, default=30)
    p.add_argument("--sell", type=float, default=70)
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("screen", help="فحص الرموز بفلاتر فنية")
    p.add_argument("market", choices=["crypto", "stocks"])
    p.add_argument("--min-rsi", type=float, default=0.0)
    p.add_argument("--max-rsi", type=float, default=100.0)
    p.add_argument("--above-sma", type=int, default=0)
    p.add_argument("--min-change", type=float, default=None)
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("tui", help="شاشة طرفية تفاعلية")
    p.add_argument("--market", choices=["crypto", "stocks"], default="crypto")
    p.add_argument("--refresh", type=int, default=20)
    p.set_defaults(func=cmd_tui)

    p = sub.add_parser("mt5-connect", help="اتصال بحساب MT5")
    p.add_argument("--login", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--server", default=None)
    p.set_defaults(func=cmd_mt5, command="mt5-connect")

    p = sub.add_parser("mt5-signal", help="إشارة تداول من شارت MT5")
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--timeframe", default="M15")
    p.add_argument("--min-adx", type=float, default=20.0)
    p.add_argument("--ema-fast", type=int, default=20)
    p.add_argument("--ema-slow", type=int, default=100)
    p.set_defaults(func=cmd_mt5, command="mt5-signal")

    p = sub.add_parser("mt5-positions", help="العقود المفتوحة")
    p.set_defaults(func=cmd_mt5, command="mt5-positions")

    p = sub.add_parser("mt5-trail", help="وقف متحرك على صفقة")
    p.add_argument("ticket", type=int)
    p.add_argument("--mult", type=float, default=2.0)
    p.set_defaults(func=cmd_mt5, command="mt5-trail")

    p = sub.add_parser("mt5-close", help="إغلاق صفقة")
    p.add_argument("ticket", type=int)
    p.set_defaults(func=cmd_mt5, command="mt5-close")

    p = sub.add_parser("web", help="تشغيل لوحة الويب")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.set_defaults(func=cmd_web)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except DataFetchError as exc:
        print(f"خطأ في جلب البيانات: {exc}", file=sys.stderr)
        sys.exit(2)
    except (MT5Unavailable, LiveAccountError) as exc:
        print(f"MT5: {exc}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
