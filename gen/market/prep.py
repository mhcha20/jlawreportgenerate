#!/usr/bin/env python3
"""market/prep.py DATE [--extra '<JSON {"SPY":[{"d","o","h","l","c","v"}]}>'] — 大盤報告行情準備
經網站 /api/ohlcv（Yahoo 日線，不復權，同回測同源）攞 SPY／QQQ／IWM／11 個 SPDR 板塊／SMH，只取 ≤ DATE 嘅完整交易日，
存 market/data/<T>.json 同 market/data/_meta.json。
- Yahoo 唔識嘅代號（VIX、SOX、DXY、GC1!、US10Y）直接標「缺項」＝只可讀截圖，報告寫「圖表讀數」，唔好估。
- 最後一根 K 線要＝DATE（否則 DATE 唔係交易日或 Yahoo 未更新）；DATE 當日 bar 若喺美東收市後 15 分鐘前攞到就當盤中，拒絕。
- Yahoo 缺 DATE 嘅 bar 時：用 Longbridge history_candlesticks_by_offset（period=day, forward_adjust=false）攞，經 --extra 補入，並喺報告第二節註明。
輸出最後一行 JSON：{date, prev, have, missing, last}。"""
import datetime as dt, json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mlib import *
SITE = os.environ.get('JLAW_SITE', 'https://jlaw-report-a74806.up.railway.app')

def fetch(t):
    last = None
    for _ in range(2):                                    # /api/ohlcv 曾回 502，重試一次
        try:
            with urllib.request.urlopen(f'{SITE}/api/ohlcv?t={t}&range=2y', timeout=90) as r: return json.load(r)
        except Exception as e: last = e
    raise last

def main():
    a = sys.argv[1:]
    if not a or a[0].startswith('-'): sys.exit(__doc__)
    date = a[0]; dt.date.fromisoformat(date)
    extra = json.loads(a[a.index('--extra') + 1]) if '--extra' in a else {}
    if dt.date.fromisoformat(date).weekday() >= 5: sys.exit(f'{date} 係週末，唔係美股交易日')
    os.makedirs(DATA, exist_ok=True)
    have, missing, last, warn = [], [], {}, []
    close_utc = dt.datetime.fromisoformat(date + 'T16:15:00').replace(tzinfo=NY).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    for t in YAHOO_OK:
        try:
            j = fetch(t); rows = [x for x in j['rows'] if x['d'] <= date]
        except Exception as e:
            missing.append({'t': t, 'err': str(e)[:120]}); continue
        if t in extra:
            em = {x['d']: x for x in extra[t]}
            rows = sorted([x for x in rows if x['d'] not in em] + [x for x in em.values() if x['d'] <= date], key=lambda x: x['d'])
            warn.append(f'{t} 已用 --extra 補入 {sorted(em)}：報告第二節要註明來源')
        if not rows or rows[-1]['d'] != date:
            missing.append({'t': t, 'err': f'最後一根 {rows[-1]["d"] if rows else None} ≠ {date}'}); continue
        if t not in extra and rows[-1].get('fa', '9') < close_utc:
            sys.exit(f'{t} {date} 嘅 bar 係盤中攞（fa={rows[-1].get("fa")} < 收市後 {close_utc}），唔可以用；收市後再跑')
        if len(rows) < 210: warn.append(f'{t} 只有 {len(rows)} 根日線，MA200 唔可靠')
        rows = rows[-400:]
        json.dump({'symbol': j.get('symbol', t), 'rows': [{k: x[k] for k in ('d', 'o', 'h', 'l', 'c', 'v')} for x in rows]}, open(f'{DATA}/{t}.json', 'w'))
        have.append(t); last[t] = [rows[-1]['d'], rows[-1]['c'], rows[-1]['v']]
    core = INDEXES + [s for s, _ in SECTORS]
    gone = [t for t in core if t not in have]
    meta = {'date': date, 'have': have, 'missing': missing, 'chart_only': CHART_ONLY, 'warn': warn, 'last': last}
    if have and 'SPY' in have:
        sp = json.load(open(f'{DATA}/SPY.json'))['rows']; meta['prev'] = sp[-2]['d']
    json.dump(meta, open(f'{DATA}/_meta.json', 'w'), ensure_ascii=False)
    for w in warn: print('⚠', w, file=sys.stderr)
    for m_ in missing: print('✗ 缺項', m_['t'], m_['err'], file=sys.stderr)
    print('✗ 圖表讀數項（Yahoo 無）：', '、'.join(CHART_ONLY), file=sys.stderr)
    print(json.dumps({'date': date, 'prev': meta.get('prev'), 'have': len(have), 'core_missing': gone, 'chart_only': CHART_ONLY,
                      'spy': last.get('SPY')}, ensure_ascii=False))
    if gone: sys.exit(f'核心標的缺 {gone}：build 會失敗，補 --extra 或等 Yahoo 更新')

if __name__ == '__main__': main()
