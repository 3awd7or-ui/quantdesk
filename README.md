# QuantDesk

حزمة أدوات تداول كمّي (Quant) مفتوحة المصدر — للعملات الرقمية والأسهم — تضم أربع ميزات:

1. **لوحة أسعار ويب (Dashboard)** — شموع يابانية، إحصاءات لحظية، تبويبات تفاعلية.
2. **مُختبر استراتيجيات (Backtester)** — استراتيجيات SMA Crossover و RSI، مع منحنى رأس المال ومقاييس Sharpe وأقصى تراجع ونسبة الصفقات الرابحة.
3. **مُصفّي فني (Screener)** — فحص رموز متعددة بفلاتر RSI / SMA / نسبة التغير.
4. **شاشة طرفية (TUI)** — قائمة متابعة تفاعلية داخل الترمنال (curses من المكتبة القياسية، بلا تبعيات إضافية).

## المصادر
- العملات الرقمية: Binance (أساسي) مع ارجاع تلقائي إلى CoinGecko.
- الأسهم/ETF: Yahoo Finance (أساسي) مع بديل Stooq.
- كل المصادر مجانية وبدون مفاتيح API.

## التثبيت
```bash
pip install -r requirements.txt
```

## الاستخدام (سطر الأوامر)
```bash
python -m quantdesk.cli price crypto BTCUSDT
python -m quantdesk.cli indicators stocks AAPL --days 200 --sma 20 50 --rsi-period 14
python -m quantdesk.cli backtest crypto BTCUSDT --strategy sma --fast 20 --slow 50
python -m quantdesk.cli backtest stocks AAPL --strategy rsi --buy 30 --sell 70
python -m quantdesk.cli screen crypto --min-rsi 30 --max-rsi 70 --above-sma 50
python -m quantdesk.cli tui --market crypto --refresh 20
```

## الاستخدام (الويب)
```bash
python -m quantdesk.cli web            # ثم افتح http://127.0.0.1:5000
```
- تبويب **لوحة الأسعار**: شموع + إحصاءات لأي رمز.
- تبويب **مُختبر الاستراتيجيات**: اختر السوق والرمز والاستراتيجية وشغّل — يظهر منحنى رأس المال وجدول الصفقات.
- تبويب **المُصفّي**: فلاتر RSI وSMA مع جدول مرتب.

## الاختبارات
```bash
python -m unittest discover -s tests -v
```

## البنية
```
quantdesk/
├── data.py         # جلب البيانات (Binance/CoinGecko/Yahoo/Stooq)
├── indicators.py   # SMA, EMA, RSI, MACD, ATR, Bollinger
├── backtest.py     # محرك الاختبار التاريخي
├── screener.py     # فحص الرموز بفلاتر فنية
├── tui.py          # الشاشة الطرفية (curses)
├── cli.py          # واجهة الأوامر
└── web/            # تطبيق Flask (API + واجهة)
tests/              # اختبارات الوحدة
```

> ⚠️ لأغراض تعليمية وبحثية فقط — لا تمثل نصيحة استثمارية.
