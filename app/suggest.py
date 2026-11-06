"""suggest.py — 「今日值得出報告」推介（唔用 AI、唔收費）：用當日行情對照每隻股上一張 V2.0 行動卡嘅價位，加 J Law／MYT 量價訊號計分。
用戶 2026-11-06 要求：唔係每日做晒所有股票，要揀重點。分數只係排次序，唔係買賣建議。
資料：jlaw.stock_list（截圖齊唔齊）、jlaw-report /api/signals（每隻股最新 V2.0 卡：順勢觸發 buy、減倉 trim、離場 stop、分數、出卡日）、
/api/ohlcv（Yahoo 日線）、Longbridge 財經日曆（未來 5 個交易日業績，選填）。"""
import datetime as dt, threading, time
from concurrent.futures import ThreadPoolExecutor
import jlaw, longbridge as lb

_cache, _lock = {}, threading.Lock()
TTL = 600


def _norm(t):
    t = str(t).strip().upper()
    return str(int(t)) if t.isdigit() else t


def _metrics(rows, date):
    r = [x for x in rows if x['d'] <= date]
    if len(r) < 60 or r[-1]['d'] != date: return None
    C, H, L, V = [x['c'] for x in r], [x['h'] for x in r], [x['l'] for x in r], [x['v'] for x in r]
    sma = lambda n, k=0: sum(C[len(C) - n - k:len(C) - k]) / n if len(C) >= n + k else None
    tr = [max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1])) for i in range(len(C) - 14, len(C))]
    v50 = sum(V[-51:-1]) / 50
    return dict(c=C[-1], prev=C[-2], chg=(C[-1] / C[-2] - 1) * 100, h=H[-1], v=V[-1], vr=V[-1] / v50 if v50 else 0,
                atrp=sum(tr) / 14 / C[-1] * 100, s50=sma(50), s50p=sma(50, 5), s200=sma(200), s200p=sma(200, 5),
                hi52=max(H[-253:-1]), rng10=(max(H[-10:]) - min(L[-10:])) / C[-1] * 100,
                down=C[-1] < C[-2], ddv=V[-1] > V[-2] and V[-1] > v50)


def _score(t, m, card, er, date):
    pts, why, kinds = 0, [], set()
    def add(p, s, k=''):
        nonlocal pts; pts += p; why.append(s)
        if k: kinds.add(k)
    c, prev = m['c'], m['prev']
    if card:
        lv = card.get('levels') or {}
        buy, trim, stop = ((lv.get(k) or {}).get('price') for k in ('buy', 'trim', 'stop'))
        if buy:
            if c > buy and prev <= buy: add(5, f'收市升穿順勢觸發 {buy:g}（要核實量）', 'opp')
            elif c <= buy and buy / c - 1 <= 0.03: add(3, f'距順勢觸發 {buy:g} 只差 {(buy / c - 1) * 100:.1f}%', 'opp')
        if stop:
            if c < stop and prev >= stop: add(5, f'收市跌穿離場線 {stop:g}（持倉要處理）', 'risk')
            elif c >= stop and c / stop - 1 <= 0.02: add(2, f'貼近離場線 {stop:g}（{(c / stop - 1) * 100:.1f}%）', 'risk')
        if trim and (not stop or c >= stop):
            if c < trim and prev >= trim: add(4, f'收市跌穿減倉線 {trim:g}', 'risk')
            elif c >= trim and c / trim - 1 <= 0.02: add(2, f'貼近減倉線 {trim:g}（{(c / trim - 1) * 100:.1f}%）', 'risk')
        age = (dt.date.fromisoformat(date) - dt.date.fromisoformat(card['date'])).days
        if age >= 7: add(1, f'{age} 日冇出新卡（上一張 {card["date"]}）')
        if (card.get('score') or 0) >= 70: add(1, f'上一張評等 {card.get("rating")} {card.get("score")} 分')
    else:
        add(2, '未有 V2.0 行動卡')
    if m['vr'] >= 1.5 and abs(m['chg']) >= max(1.5 * m['atrp'], 3):
        add(3, f'放量{"大升" if m["chg"] > 0 else "大跌"} {m["chg"]:+.1f}%（量 {m["vr"]:.1f}× 50 日均量）', 'opp' if m['chg'] > 0 else 'risk')
    elif m['vr'] >= 2: add(2, f'異常大量（{m["vr"]:.1f}× 50 日均量）')
    if m['c'] > m['hi52']: add(2, f'收市創 52 週新高（舊高 {m["hi52"]:g}）', 'opp')
    elif m['h'] > m['hi52']: add(1, f'日內創 52 週新高（舊高 {m["hi52"]:g}），收市回落')
    if m['s50'] and m['s200'] and c > m['s50'] > m['s200'] and m['s50'] > (m['s50p'] or 0) and m['s200'] > (m['s200p'] or 0):
        add(1, 'High-alpha 模板（股價＞50 天線＞200 天線，兩線向上）')
        if m['rng10'] <= 6: add(2, f'近 10 日波幅收窄至 {m["rng10"]:.1f}%（可能係 VCP 緊縮區）', 'opp')
    if m['down'] and m['ddv'] and card and (card.get('cls') or {}).get('held', {}).get('key') == 'hold': add(1, '續抱中遇派發日（下跌＋量大過前日同 50 日均量）', 'risk')
    if er: add(2, f'業績日 {er[0]}（{er[1]}，Longbridge）')
    return pts, why, sorted(kinds)


def suggest(date):
    with _lock:
        hit = _cache.get(date)
        if hit and time.time() - hit[0] < TTL: return hit[1]
    rows, _ = jlaw.stock_list(date)
    ok = [r['ticker'] for r in rows if r.get('status') == 'ok']
    try: cards = {_norm(r['ticker']): r for r in jlaw.get_json('/api/signals').get('rows', [])}
    except Exception: cards = {}
    ers, er_note = {}, ''
    if lb.enabled():
        try:
            for mk in ('US', 'HK'): ers.update(lb.earnings_calendar(mk, date, 5))
        except Exception as e: er_note = f'Longbridge 業績日查唔到（{e}）'
    else: er_note = '未設定 Longbridge，冇業績日'

    def one(t):
        try:
            m = _metrics(jlaw.get_json(f'/api/ohlcv?t={t}&range=2y').get('rows', []), date)
        except Exception as e: return dict(ticker=t, points=0, why=[], err=f'行情：{e}')
        if not m: return dict(ticker=t, points=0, why=[], err='行情未有當日收市')
        card = cards.get(_norm(t))
        if card and card.get('date', '') >= date: return dict(ticker=t, points=0, why=[f'已有 {card["date"]} 行動卡'], done=True, close=m['c'], chg=round(m['chg'], 2))
        sym = lb.symbol(t)
        pts, why, kinds = _score(t, m, card, ers.get(sym) if sym else None, date)
        return dict(ticker=t, points=pts, why=why, kinds=kinds, close=round(m['c'], 4), chg=round(m['chg'], 2), card=card.get('date') if card else None)
    with ThreadPoolExecutor(8) as ex: res = list(ex.map(one, ok))
    res.sort(key=lambda x: (-x['points'], x['ticker']))
    out = dict(date=date, n=len(ok), rows=res, note=er_note, at=dt.datetime.now(dt.timezone.utc).isoformat())
    with _lock: _cache[date] = (time.time(), out)
    return out
