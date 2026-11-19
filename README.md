# QuantDesk

حزمة أدوات تداول كمّي (Quant) مفتوحة المصدر — للعملات الرقمية والأسهم و MetaTrader 5 — تضم:

1. **لوحة أسعار ويب (Dashboard)** — شموع يابانية، إحصاءات لحظية، تبويبات تفاعلية.
2. **مُختبر استراتيجيات (Backtester)** — استراتيجيات SMA Crossover و RSI، مع منحنى رأس المال ومقاييس Sharpe وأقصى تراجع ونسبة الصفقات الرابحة.
3. **مُصفّي فني (Screener)** — فحص رموز متعددة بفلاتر RSI / SMA / نسبة التغير.
4. **شاشة طرفية (TUI)** — قائمة متابعة تفاعلية داخل الترمنال (curses من المكتبة القياسية، بلا تبعيات إضافية).
5. **جسر MetaTrader 5** — إشارات دخول/خروج (EMA 20/100 + ADX + جلسات + ATR) مع بطاقة تقييم /100، تنفيذ صفقات على حساب Demo، إدارة عقود: نقل SL للتعادل، وقف متحرك ATR، إغلاق، وتنبيهات صوتية.

> ⚠️ التنفيذ التلقائي مقصور على حسابات Demo — الحسابات الحقيقية محجوبة بشكل افتراضي.

## المصادر
- العملات الرقمية: Binance (أساسي) مع ارجاع تلقائي إلى CoinGecko.
- **MetaTrader 5**: شارت مباشر من منصتك (رموز XAUUSD/EURUSD وأي ما تدعمه وسيطك) — يتطلب ويندوز وحزمة `pip install MetaTrader5` مع تشغيل منصة MT5 وتفعيل Algo Trading.
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
python -m quantdesk.cli mt5-signal --symbol XAUUSD --timeframe M15 --min-adx 20
python -m quantdesk.cli mt5-positions
python -m quantdesk.cli mt5-trail 123456 --mult 2.0
python -m quantdesk.cli mt5-close 123456
```

### ربط MT5 من لوحة الويب
شغّل `python -m quantdesk.cli web` ثم تبويب **ميتاتريدر 5**:
1. كلّل `pip install MetaTrader5` (ويندوز فقط) وشغّل منصة MT5 مع تفعيل **Algo Trading**
2. أدخل Login/كلمة المرور/الخادم واضغط اتصال — أو استخدم session المحطة المفتوحة مباشرة
3. زر **فحص الإشارة**: يظهر SELL/BUY بتقييم /100 ومستويات SL/TP1/TP2 بنسبة ATR (مثل 1.5×1.5×3.0)
4. زر **شراء/بيع الآن** ينفذ على حساب Demo فقط بسعة اللوت المحددة
5. جدول العقود المفتوحة يُحدّث تلقائياً مع أزرار: نقل SL للتعادل، وقف متحرك ATR، إغلاق
6. تنبيه صوتي عند ظهور إشارة جديدة بقوة ≥ 50

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
