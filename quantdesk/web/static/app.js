const $ = (id) => document.getElementById(id);

async function api(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(qs ? `${path}?${qs}` : path);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function fmt(n, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: digits });
}

function statCard(label, value, cls = "") {
  return `<div class="stat"><div class="label">${label}</div><div class="value ${cls}">${value}</div></div>`;
}

function drawCandles(canvas, bars) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = 380;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  if (!bars.length) return;

  const lows = bars.map(b => b.low), highs = bars.map(b => b.high);
  let min = Math.min(...lows), max = Math.max(...highs);
  const pad = (max - min) * 0.05 || 1;
  min -= pad; max += pad;

  const left = 10, right = 60, top = 10, bottom = 30;
  const plotW = w - left - right, plotH = h - top - bottom;
  const shown = Math.min(bars.length, Math.floor(plotW / 4) + 1);
  const start = bars.length - shown;
  const step = plotW / shown;
  const bw = Math.max(1, step * 0.6);
  const y = (p) => top + (max - p) / (max - min) * plotH;

  ctx.strokeStyle = "#30363d";
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px sans-serif";
  const ticks = 5;
  ctx.beginPath();
  for (let i = 0; i <= ticks; i++) {
    const v = min + (max - min) * i / ticks;
    const yy = y(v);
    ctx.moveTo(left, yy); ctx.lineTo(left + plotW, yy);
    ctx.fillText(fmt(v, max < 10 ? 4 : 0), left + plotW + 6, yy + 4);
  }
  ctx.stroke();

  for (let i = start; i < bars.length; i++) {
    const b = bars[i];
    const x = left + (i - start) * step + step / 2;
    const up = b.close >= b.open;
    ctx.strokeStyle = up ? "#3fb950" : "#f85149";
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath();
    ctx.moveTo(x, y(b.high)); ctx.lineTo(x, y(b.low));
    ctx.stroke();
    const yTop = y(Math.max(b.open, b.close));
    const bh = Math.max(1, Math.abs(y(b.open) - y(b.close)));
    ctx.fillRect(x - bw / 2, yTop, bw, bh);
  }

  ctx.fillStyle = "#8b949e";
  ctx.fillText(bars[start].date, left + 4, h - 8);
  ctx.fillText(bars[bars.length - 1].date, left + plotW - 70, h - 8);
}

function drawLine(canvas, points, color = "#58a6ff") {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = 320;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  if (!points.length) return;
  const vals = points.map(p => p.y);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (min === max) { min -= 1; max += 1; }
  const left = 10, right = 60, top = 10, bottom = 30;
  const plotW = w - left - right, plotH = h - top - bottom;
  const x = (i) => left + i / (vals.length - 1) * plotW;
  const y = (v) => top + (max - v) / (max - min) * plotH;

  ctx.strokeStyle = "#30363d";
  ctx.beginPath();
  for (let i = 0; i <= 5; i++) {
    const v = min + (max - min) * i / 5;
    const yy = y(v);
    ctx.moveTo(left, yy); ctx.lineTo(left + plotW, yy);
    ctx.fillStyle = "#8b949e";
    ctx.fillText(fmt(v), left + plotW + 6, yy + 4);
  }
  ctx.stroke();

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  points.forEach((p, i) => i ? ctx.lineTo(x(i), y(p.y)) : ctx.moveTo(x(i), y(p.y)));
  ctx.stroke();
  ctx.lineWidth = 1;
}

async function loadDashboard() {
  const market = $("market").value;
  const symbol = $("symbol").value.trim().toUpperCase();
  if (!symbol) return;
  if (market === "crypto" && !symbol.includes("USD")) $("symbol").value = symbol + "USDT";
  $("market-status").textContent = "جارٍ التحميل…";
  try {
    const bars = await api("/api/ohlcv", { market, symbol: $("symbol").value.trim().toUpperCase(), days: 365 });
    drawCandles($("candles"), bars);
    const last = bars[bars.length - 1], prev = bars[bars.length - 2] || last;
    const change = prev.close ? (last.close / prev.close - 1) * 100 : 0;
    const cls = change >= 0 ? "up" : "down";
    $("stats").innerHTML =
      statCard("مغلق", fmt(last.close, last.close < 10 ? 4 : 2), cls) +
      statCard("التغير اليومي", `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`, cls) +
      statCard("أعلى (يوم)", fmt(last.high, 2)) +
      statCard("أدنى (يوم)", fmt(last.low, 2));
    $("market-status").textContent = `آخر شمعة: ${last.date} · ${bars.length} شمعة`;
  } catch (err) {
    $("market-status").textContent = `خطأ: ${err.message}`;
  }
}

async function runBacktest() {
  const params = {
    market: $("bt-market").value,
    symbol: $("bt-symbol").value.trim().toUpperCase(),
    strategy: $("bt-strategy").value,
    fast: $("bt-fast").value, slow: $("bt-slow").value,
    capital: $("bt-capital").value,
  };
  let symbol = params.symbol;
  if (params.market === "crypto") {
    if (symbol.toLowerCase() === "btc" || symbol.toLowerCase() === "bitcoin") symbol = "BTCUSDT";
    else if (!symbol.includes("USD")) symbol += "USDT";
  } else if (symbol.toLowerCase() === "btcusdt") {
    symbol = "BTC";
  }
  params.symbol = symbol;
  try {
    const data = await api("/api/backtest", params);
    const m = data.metrics;
    $("bt-metrics").innerHTML =
      statCard("العائد الكلي", `${m.total_return_pct}%`, m.total_return_pct >= 0 ? "up" : "down") +
      statCard("شراء واحتفاظ", `${m.buy_hold_return_pct}%`) +
      statCard("Sharpe", m.sharpe) +
      statCard("أقصى تراجع", `${m.max_drawdown_pct}%`, "down") +
      statCard("صفقات", m.trades) +
      statCard("نسبة رابحة", `${m.win_rate_pct}%`) +
      statCard("قيمة نهائية", fmt(m.final_equity));
    drawLine($("equity"), data.equity_curve.map(p => ({ x: p.date, y: p.equity })));
    const rows = data.trades.slice(-10).reverse().map(t =>
      `<tr><td>${t.entry_date}</td><td>${fmt(t.entry_price)}</td><td>${t.exit_date}</td><td>${fmt(t.exit_price)}</td><td class="${t.exit_price >= t.entry_price ? "up" : "down"}">${fmt((t.exit_price / t.entry_price - 1) * 100, 1)}%</td></tr>`).join("");
    $("bt-trades").innerHTML = rows ? `<table><tr><th>شراء</th><th>سعر الدخول</th><th>بيع</th><th>سعر الخروج</th><th>ربح/خسارة %</th></tr>${rows}</table>` : "";
  } catch (err) {
    $("bt-metrics").innerHTML = `<div class="down">خطأ: ${err.message}</div>`;
  }
}

async function runScreener() {
  try {
    const data = await api("/api/screen", {
      market: $("sc-market").value,
      min_rsi: $("sc-min-rsi").value,
      max_rsi: $("sc-max-rsi").value,
      above_sma: $("sc-above-sma").value,
    });
    const rows = data.rows.map(r =>
      `<tr><td>${r.symbol}</td><td>${fmt(r.price, r.price < 10 ? 4 : 2)}</td><td class="${r.change_pct >= 0 ? "up" : "down"}">${fmt(r.change_pct)}%</td><td>${fmt(r.rsi, 1)}</td><td>${fmt(r.sma, r.sma < 10 ? 4 : 2)}</td></tr>`).join("");
    const errs = data.errors.map(e => `<div class="muted">${e.symbol}: ${e.error}</div>`).join("");
    $("sc-results").innerHTML =
      `<div class="muted">${data.rows.length} نتيجة</div>` +
      (rows ? `<table><tr><th>الرمز</th><th>السعر</th><th>التغير٪</th><th>RSI</th><th>SMA</th></tr>${rows}</table>` : "<div class='muted'>لا نتائج مطابقة</div>") + errs;
  } catch (err) {
    $("sc-results").innerHTML = `<div class="down">خطأ: ${err.message}</div>`;
  }
}

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.add("hidden"));
    tab.classList.add("active");
    $("tab-" + tab.dataset.tab).classList.remove("hidden");
  });
});
$("load-btn").addEventListener("click", loadDashboard);
$("symbol").addEventListener("keydown", e => { if (e.key === "Enter") loadDashboard(); });
$("market").addEventListener("change", () => {
  $("symbol").value = $("market").value === "crypto" ? "BTCUSDT" : "AAPL";
  loadDashboard();
});
$("bt-run").addEventListener("click", runBacktest);
$("sc-run").addEventListener("click", runScreener);

loadDashboard();
