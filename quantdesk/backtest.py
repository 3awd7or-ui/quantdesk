"""Simple long/flat backtesting engine with daily OHLCV bars."""

from dataclasses import dataclass, field

from .indicators import rsi, sma


@dataclass
class Trade:
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0.0


@dataclass
class BacktestResult:
    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def sma_crossover_signals(closes, fast=20, slow=50):
    fast_line = sma(closes, fast)
    slow_line = sma(closes, slow)
    signals = [0] * len(closes)
    prev_pos = 0
    for i in range(len(closes)):
        f, s = fast_line[i], slow_line[i]
        if f is not None and s is not None:
            pos = 1 if f > s else 0
            signals[i] = pos - prev_pos if pos != prev_pos else 0
            prev_pos = pos
        else:
            signals[i] = 0
    return signals


def rsi_signals(closes, period=14, buy=30, sell=70):
    line = rsi(closes, period)
    signals = [0] * len(closes)
    in_pos = 0
    for i in range(len(closes)):
        v = line[i]
        if v is None:
            continue
        if v < buy and in_pos == 0:
            signals[i] = 1
            in_pos = 1
        elif v > sell and in_pos == 1:
            signals[i] = -1
            in_pos = 0
    return signals


STRATEGIES = {
    "sma": sma_crossover_signals,
    "rsi": rsi_signals,
}


def run_backtest(bars, strategy="sma", initial_capital=10_000.0, fee=0.001, **params):
    if not bars:
        raise ValueError("no bars to backtest")
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    closes = [b.close for b in bars]
    signals = STRATEGIES[strategy](closes, **params)

    cash = initial_capital
    position = 0.0
    equity_before = initial_capital
    equity_curve = []
    trades = []
    open_trade = None

    for i, bar in enumerate(bars):
        tid = signals[i]
        if tid == 1 and position == 0:
            price = bar.close * (1 + fee)
            position = cash / price
            cash = 0.0
            open_trade = Trade(bar.date, bar.close)
        elif tid == -1 and position > 0:
            price = bar.close * (1 - fee)
            cash = position * price
            position = 0.0
            if open_trade is not None:
                open_trade.exit_date = bar.date
                open_trade.exit_price = bar.close
                trades.append(open_trade)
                open_trade = None
        equity_before = cash + position * bar.close
        equity_curve.append({"date": bar.date, "equity": equity_before})

    final_equity = cash + position * closes[-1]
    metrics = compute_metrics(equity_curve, trades, final_equity, initial_capital)
    return BacktestResult(equity_curve, trades, metrics)


def compute_metrics(equity_curve, trades, final_equity, initial_capital):
    values = [point["equity"] for point in equity_curve]
    total_return = final_equity / initial_capital - 1.0

    returns = []
    for i in range(1, len(values)):
        if values[i - 1]:
            returns.append(values[i] / values[i - 1] - 1.0)

    if returns:
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std = var ** 0.5
        daily_sharpe = mean_r / std if std > 0 else 0.0
        sharpe = daily_sharpe * (252 ** 0.5)
        annualized = (1 + total_return) ** (252 / len(returns)) - 1
    else:
        sharpe = 0.0
        annualized = 0.0

    peak = values[0] if values else 0.0
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            max_dd = min(max_dd, v / peak - 1.0)

    wins = sum(1 for t in trades if t.exit_price > t.entry_price)
    buy_hold = values[-1] / values[0] - 1 if values and values[0] else 0.0

    return {
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(annualized * 100, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "trades": len(trades),
        "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else 0.0,
        "final_equity": round(final_equity, 2),
        "buy_hold_return_pct": round(buy_hold * 100, 2),
    }
