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

/* ============ MT5 tab ============ */
async function postJson(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "HTTP " + res.status);
  return data;
}

function beep() {
  if (!$("mt5-sound").checked) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.frequency.value = 880; gain.gain.value = 0.15;
    osc.start();
    setTimeout(() => { osc.stop(); ctx.close(); }, 400);
  } catch (e) {}
}

async function mt5RefreshStatus() {
  try {
    const st = await api("/api/mt5/status");
    if (!st.mt5_package_installed) {
      $("mt5-status").textContent = "حزمة MetaTrader5 غير مثبتة — شغّل: pip install MetaTrader5 (ويندوز فقط)";
      $("mt5-connect-box").classList.add("hidden");
      return;
    }
    if (st.connected) {
      $("mt5-status").innerHTML =
        "متصل: " + st.login + " @ " + st.server + " — الرصيد: " + fmt(st.balance) + " " + st.currency + " · " +
        (st.is_demo ? '<span class="up">حساب تجريبي (Demo) — التنفيذ مفعّل</span>'
                    : '<span class="down">حساب حقيقي — التنفيذ محجوب تلقائياً</span>');
      $("mt5-connect-box").classList.add("hidden");
    } else {
      $("mt5-status").textContent = "غير متصل بمنصة MT5";
      $("mt5-connect-box").classList.remove("hidden");
    }
  } catch (e) {
    $("mt5-status").textContent = "خطأ فحص الاتصال: " + e.message;
  }
}

async function mt5Connect() {
  try {
    const r = await postJson("/api/mt5/connect", {
      login: $("mt5-login").value, password: $("mt5-password").value,
      server: $("mt5-server").value,
    });
    beep();
    $("mt5-status").innerHTML = "متصل: " + r.login + " @ " + r.server + " — الرصيد: " + fmt(r.balance) + " · " + (r.is_demo ? "Demo" : "حقيقي");
    $("mt5-connect-box").classList.add("hidden");
  } catch (e) {
    $("mt5-status").innerHTML = '<span class="down">فشل الاتصال: ' + e.message + "</span>";
  }
}

async function mt5Scan() {
  const box = $("mt5-signal-box");
  const params = {
    symbol: $("mt5-symbol").value.trim().toUpperCase(),
    timeframe: $("mt5-timeframe").value,
    min_adx: $("mt5-min-adx").value,
    ema_fast: $("mt5-ema-fast").value,
    ema_slow: $("mt5-ema-slow").value,
    sessions: $("mt5-sessions").value.trim(),
  };
  box.innerHTML = '<p class="muted">جارٍ التحليل…</p>';
  try {
    const prev = window._mt5LastAction;
    const s = await api("/api/mt5/signal", params);
    window._mt5LastAction = s.action;
    if (s.action !== "none" && s.score >= 50 && prev !== s.action) beep();
    const cls = s.action === "buy" ? "signal-buy" : (s.action === "sell" ? "signal-sell" : "signal-none");
    const label = s.action === "buy" ? "BUY — الدخول شراء" : (s.action === "sell" ? "SELL — الدخول بيع" : "NO TRADE — لا إشارة");
    const blocked = s.blocked_reason ? '<div class="down">' + s.blocked_reason + "</div>" : "";
    const levels = s.action !== "none" ? `
        <div class="stat"><div class="label">دخول</div><div class="value">${fmt(s.entry, 3)}</div></div>
        <div class="stat"><div class="label">SL</div><div class="value down">${fmt(s.sl, 3)}</div></div>
        <div class="stat"><div class="label">TP1</div><div class="value up">${fmt(s.tp1, 3)}</div></div>
        <div class="stat"><div class="label">TP2</div><div class="value up">${fmt(s.tp2, 3)}</div></div>` : "";
    box.innerHTML = `
      <div class="signal-box ${cls}">
        <div><div class="signal-action ${s.action === 'buy' ? 'up' : (s.action === 'sell' ? 'down' : '')}">${label}</div>
        <div class="score">${s.score}<span class="muted">/100</span></div></div>
        ${levels}
        ${s.action !== "none" ? `<button id="mt5-exec-btn">${s.action === 'buy' ? 'شراء الآن' : 'بيع الآن'} (Demo)</button>` : ""}
        <div class="reasons">${s.reasons.join("<br>") || "—"}${blocked}</div>
      </div>`;
    const execBtn = $("mt5-exec-btn");
    if (execBtn) execBtn.addEventListener("click", () => mt5Execute(s));
  } catch (e) {
    box.innerHTML = '<div class="down">خطأ: ' + e.message + "</div>";
  }
}

async function mt5Execute(signalData) {
  signalData.lots = $("mt5-lots").value;
  try {
    const r = await postJson("/api/mt5/execute", signalData);
    beep();
    $("mt5-signal-box").innerHTML =
      '<div class="signal-box signal-buy"><div><div class="signal-action up">تم التنفيذ ✓</div>' +
      '<div class="reasons">العقد: ' + r.ticket + " · السعر: " + fmt(r.price, 3) + " · SL: " + fmt(r.sl, 3) + " · TP2: " + fmt(r.tp2, 3) + "</div></div></div>";
    mt5Positions();
  } catch (e) {
    $("mt5-signal-box").innerHTML += '<div class="down">فشل التنفيذ: ' + e.message + "</div>";
  }
}

async function mt5Positions() {
  try {
    const list = await api("/api/mt5/positions");
    if (!list.length) {
      $("mt5-positions").innerHTML = '<p class="muted">لا عُقود مفتوحة حالياً.</p>';
      return;
    }
    const rows = list.map(p => `
      <tr><td>${p.ticket}</td><td>${p.symbol}</td><td class="${p.type === 'buy' ? 'up' : 'down'}">${p.type === 'buy' ? 'شراء' : 'بيع'}</td>
      <td>${fmt(p.volume, 2)}</td><td>${fmt(p.price_open, 3)}</td><td>${fmt(p.price_current, 3)}</td>
      <td>${fmt(p.sl, 3)}</td><td>${fmt(p.tp, 3)}</td>
      <td class="${p.profit >= 0 ? 'up' : 'down'}">${fmt(p.profit)}</td>
      <td><button data-a="be" data-t="${p.ticket}">نقل SL للتعادل</button>
      <button data-a="tr" data-t="${p.ticket}">وقف متحرك ATR</button>
      <button data-a="cl" data-t="${p.ticket}">إغلاق</button></td></tr>`).join("");
    $("mt5-positions").innerHTML =
      "<table><tr><th>رقم</th><th>الرمز</th><th>النوع</th><th>حجم</th><th>دخول</th><th>الآن</th><th>SL</th><th>TP</th><th>ربح/خسارة</th><th>إدارة</th></tr>" + rows + "</table>";
    $("mt5-positions").querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", async () => {
        const path = { be: "/api/mt5/breakeven", tr: "/api/mt5/trailing", cl: "/api/mt5/close" }[btn.dataset.a];
        try {
          await postJson(path, { ticket: btn.dataset.t, atr_mult: 2.0 });
          mt5Positions();
        } catch (e) { alert("خطأ: " + e.message); }
      });
    });
  } catch (e) {
    $("mt5-positions").innerHTML = '<div class="down">خطأ: ' + e.message + "</div>";
  }
}

$("mt5-connect-btn").addEventListener("click", mt5Connect);
$("mt5-scan-btn").addEventListener("click", mt5Scan);
mt5RefreshStatus();

setInterval(() => {
  if (!document.getElementById("tab-mt5").classList.contains("hidden")) {
    mt5RefreshStatus();
    mt5Positions();
  }
}, 5000);
