"""QuantDesk command line interface."""

import argparse
import sys

from .backtest import run_backtest
from .data import DataFetchError, get_ohlcv, get_snapshot
from .indicators import last_valid, rsi, sma
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


if __name__ == "__main__":
    main()
