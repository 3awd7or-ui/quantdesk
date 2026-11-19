"""Terminal UI: keyboard-driven watchlist with live-ish refresh (curses based)."""

import curses
import time

from .data import DataFetchError, get_ohlcv, get_snapshot
from .indicators import rsi, sma

DEFAULT_CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
DEFAULT_STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META"]


class WatchRow:
    def __init__(self, symbol):
        self.symbol = symbol
        self.price = None
        self.change_pct = None
        self.rsi_value = None
        self.sma_value = None
        self.signal = ""
        self.error = ""


def update_row(row, market):
    try:
        snap = get_snapshot(market, row.symbol)
        row.price = snap["price"]
        row.change_pct = snap["change_pct"]
        bars = get_ohlcv(market, row.symbol, days=180)
        closes = [b.close for b in bars]
        rsi_series = rsi(closes)
        row.rsi_value = next((v for v in reversed(rsi_series) if v is not None), None)
        sma_series = sma(closes, 50)
        row.sma_value = next((v for v in reversed(sma_series) if v is not None), None)
        if row.sma_value and closes[-1]:
            row.signal = "▲ فوق SMA50" if closes[-1] > row.sma_value else "▼ تحت SMA50"
        row.error = ""
    except DataFetchError as exc:
        row.error = str(exc)


def draw(stdscr, rows, market, status_line):
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)

    title = f" QuantDesk — {('عملات رقمية' if market == 'crypto' else 'أسهم')} "
    stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
    stdscr.addstr(0, 2, title[:width - 3])
    stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)

    header = f"{'الرمز':<10}{'السعر':>12}{'التغير٪':>10}{'RSI':>8}{'SMA50':>12}  الإشارة"
    stdscr.addstr(2, 2, header[:width - 3], curses.A_BOLD | curses.A_UNDERLINE)

    for idx, row in enumerate(rows[:height - 6]):
        line = f"{row.symbol:<10}"
        line += f"{row.price:,.2f}" if row.price is not None else "-".rjust(12)
        if row.change_pct is not None:
            color = 1 if row.change_pct >= 0 else 2
            line += f"{row.change_pct:>9.2f}%"
        else:
            color = 0
            line += " " * 10
        line += f"{row.rsi_value:>8.1f}" if row.rsi_value is not None else " " * 8
        line += f"{row.sma_value:>12,.2f}" if row.sma_value is not None else " " * 12
        line += f"  {row.signal}" + (f" [{row.error}]" if row.error else "")
        try:
            if color:
                stdscr.addstr(idx + 4, 2, line[:width - 3], curses.color_pair(color))
            else:
                stdscr.addstr(idx + 4, 2, line[:width - 3])
        except curses.error:
            pass

    stdscr.addstr(height - 2, 2, status_line[:width - 3], curses.color_pair(4))
    stdscr.addstr(height - 1, 2, "[c] عملات [s] أسهم [r] تحديث [q] خروج "[:width - 3], curses.A_DIM)
    stdscr.refresh()


def run(market="crypto", refresh_seconds=20):
    symbols = list(DEFAULT_CRYPTO if market == "crypto" else DEFAULT_STOCKS)
    curses.wrapper(_main, market, symbols, refresh_seconds)


def _main(stdscr, market, symbols, refresh_seconds):
    curses.use_default_colors()
    stdscr.keypad(True)
    rows = [WatchRow(s) for s in symbols]
    last_update = 0.0
    status = ""
    while True:
        now = time.time()
        if now - last_update >= refresh_seconds:
            status = f"آخر تحديث: {time.strftime('%H:%M:%S')} … (تحميل)"
            draw(stdscr, rows, market, status)
            for row in rows:
                update_row(row, market)
            last_update = time.time()
            status = f"آخر تحديث: {time.strftime('%H:%M:%S')}"
        draw(stdscr, rows, market, status)
        stdscr.timeout(1000)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (ord("c"), ord("C")) and market != "crypto":
            default = list(DEFAULT_CRYPTO)
            symbols[:] = default
            rows[:] = [WatchRow(s) for s in default]
            market = "crypto"
            last_update = 0.0
        elif key in (ord("s"), ord("S")) and market != "stocks":
            default = list(DEFAULT_STOCKS)
            symbols[:] = default
            rows[:] = [WatchRow(s) for s in default]
            market = "stocks"
            last_update = 0.0
        elif key in (ord("r"), ord("R")):
            last_update = 0.0
