"""longbridge.py — Longbridge OpenAPI 直連（longport SDK），邏輯同 Jlaw-report tools/stockreport/lbcheck.py 直連模式一樣。
金鑰只由環境變數讀：LONGBRIDGE_APP_KEY、LONGBRIDGE_APP_SECRET、LONGBRIDGE_ACCESS_TOKEN（Railway Variables）。
只支援美股（字母代號 → XXX.US）同港股（5 位數字 → 去前導零 .HK）；日韓未驗證，回傳 None 照舊用 Yahoo。
任何失敗（缺金鑰、網絡、權限、token 過期）都唔會令報告失敗：呼叫者收到 LBError，報告寫「今次冇 Longbridge 核實」。"""
import os, threading, time
from datetime import date, datetime, timedelta, timezone

KEYS = ('LONGBRIDGE_APP_KEY', 'LONGBRIDGE_APP_SECRET', 'LONGBRIDGE_ACCESS_TOKEN')
_lock = threading.Lock()
_call_lock = threading.Lock()   # 兩條 worker thread 共用同一個連線，逐個 call
_ctx = {}


class LBError(Exception):
    pass


def enabled():
    return all(os.environ.get(k) for k in KEYS)


def symbol(t):
    """本地代號 → Longbridge 代號；唔支援嘅市場回 None。"""
    t = t.strip().upper()
    if '.' in t: return t
    if t.isalpha(): return f'{t}.US'
    if t.isdigit() and len(t) == 5: return f'{int(t)}.HK'
    return None


def _config():
    if not enabled(): raise LBError('未設定 Longbridge 金鑰（' + '、'.join(k for k in KEYS if not os.environ.get(k)) + '）')
    from longport.openapi import Config
    return Config.from_apikey(*(os.environ[k] for k in KEYS), enable_print_quote_packages=False)


def _get(kind):
    """QuoteContext／CalendarContext 開一次重用（每次開都要連 websocket）；出錯就清走，下次重開。"""
    with _lock:
        if kind not in _ctx:
            from longport.openapi import CalendarContext, QuoteContext
            _ctx[kind] = (QuoteContext if kind == 'quote' else CalendarContext)(_config())
        return _ctx[kind]


def _call(kind, fn):
    try:
        with _call_lock: return fn(_get(kind))
    except LBError:
        raise
    except Exception as e:
        with _lock: _ctx.pop(kind, None)
        raise LBError(f'{type(e).__name__}: {e}') from None


def check(sym='NVDA.US'):
    """連線自檢：攞一個報價。成功回傳一句；失敗 raise LBError。"""
    q = _call('quote', lambda c: c.quote([sym]))
    if not q: raise LBError(f'{sym} 冇報價（代號或權限）')
    return f'{q[0].symbol} 最新價 {q[0].last_done}（{q[0].timestamp}）'


def daily_bars(t, count=5):
    """最近 count 根日線（不復權、正常時段）→ {日期: {d,o,h,l,c,v}}，v 單位股。
    Longbridge 日線 timestamp 係當地午夜（UTC 表示）：加 12 小時再取日期，美股、港股都啱（lbcheck.py 實測）。"""
    sym = symbol(t)
    if not sym: return None
    from longport.openapi import AdjustType, Period, TradeSessions
    cs = _call('quote', lambda c: c.candlesticks(sym, Period.Day, count, AdjustType.NoAdjust, TradeSessions.Intraday))
    if not cs: raise LBError(f'{sym} 冇回傳日線（代號或權限）')
    out = {}
    for c in cs:
        ts = c.timestamp if c.timestamp.tzinfo else c.timestamp.replace(tzinfo=timezone.utc)
        d = (ts.astimezone(timezone.utc) + timedelta(hours=12)).date().isoformat()
        out[d] = dict(d=d, o=float(c.open), h=float(c.high), l=float(c.low), c=float(c.close), v=float(c.volume))
    return out


def next_earnings(t, d, days=45):
    """由 d 起 days 日內下次業績日 → (日期, 類型) 或 None。SDK 用日期範圍只返第一日，所以逐個平日查。"""
    sym = symbol(t)
    if not sym: return None
    from longport.openapi import CalendarCategory
    mkt, day = sym.rsplit('.', 1)[-1], date.fromisoformat(d)
    for _ in range(days + 1):
        if day.weekday() < 5:
            groups = _call('cal', lambda c: c.finance_calendar(CalendarCategory.Report, day.isoformat(), day.isoformat(), mkt).list)
            for g in groups:
                for i in g.infos:
                    if i.symbol == sym: return str(g.date), str(i.date_type)
            time.sleep(0.2)
        day += timedelta(days=1)
    return None


def compare(lb, mine):
    """Longbridge bar 同本地（Yahoo）bar 比對：收市差 ≤0.02 或 ≤0.05% 當一致。回傳 (一致?, 文字)。"""
    ok, parts = True, []
    for k, name in (('o', '開'), ('h', '高'), ('l', '低'), ('c', '收')):
        diff = abs(lb[k] - mine[k]); good = diff <= 0.02 or diff <= 0.0005 * lb[k]; ok &= good
        parts.append(f'{name} Longbridge {lb[k]:g}／Yahoo {mine[k]:g}{"" if good else "（差 " + format(diff, ".4f") + "）"}')
    vr = lb['v'] / mine['v'] if mine.get('v') else float('nan')
    parts.append(f'量 Longbridge {lb["v"]:,.0f}／Yahoo {mine["v"]:,.0f}（比 {vr:.2f}，口徑可能唔同，並列唔平均）')
    return ok, '；'.join(parts)


def earnings_calendar(market, start, days=7):
    """market（US／HK）由 start 起 days 個平日嘅業績日 → {Longbridge 代號: (日期, 類型)}。一日一次查詢，俾推介用。"""
    from longport.openapi import CalendarCategory
    out, day, n = {}, date.fromisoformat(start), 0
    while n < days:
        if day.weekday() < 5:
            n += 1
            for g in _call('cal', lambda c: c.finance_calendar(CalendarCategory.Report, day.isoformat(), day.isoformat(), market).list):
                for i in g.infos: out.setdefault(i.symbol, (str(g.date), str(i.date_type)))
            time.sleep(0.2)
        day += timedelta(days=1)
    return out
