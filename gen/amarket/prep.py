#!/usr/bin/env python3
"""amarket/prep.py DATE [--extra '<JSON {"02800":[{"d","o","h","l","c","v"}]}>'] — 香港／日本／韓國大盤報告行情準備（AMARKET=hk|jp|kr）
- core ETF＋板塊／權重股：經 jlaw-report /api/ohlcv（Yahoo 日線，不復權，同回測同源），只取 ≤ DATE 嘅完整交易日。
- 指數（^HSI ^HSCE ^N225 ^KS11 ^KQ11）：直接 Yahoo chart API（/api/ohlcv 唔收 ^ 代號）；只用嚟核對收市同升跌，攞唔到唔會失敗。
- 最後一根 K 線要＝DATE（否則 DATE 唔係該市場交易日或 Yahoo 未更新）；DATE 當日 bar 喺當地收市後 15 分鐘前攞到就當盤中，拒絕。
存 amarket/data/<mkt>/<t>.json、IDX_<名>.json、_meta.json。輸出最後一行 JSON。"""
import datetime as dt, json, os, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alib import *
SITE = os.environ.get('JLAW_SITE', 'https://jlaw-report-a74806.up.railway.app')


def fetch(t):
    last = None
    for _ in range(2):                                    # /api/ohlcv 曾回 502，重試一次
        try:
            with urllib.request.urlopen(f'{SITE}/api/ohlcv?t={t}&range=2y', timeout=90) as r: return json.load(r)
        except Exception as e: last = e
    raise last


def yahoo_index(sym):
    """Yahoo chart API 日線 → rows [{d,o,h,l,c,v}]（日期按交易所時區）；缺 close 嘅 bar 略過"""
    last = None
    for host in ('query1', 'query2'):
        try:
            req = urllib.request.Request(f'https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=2y&interval=1d',
                                         headers={'User-Agent': 'Mozilla/5.0 (jlawreportgenerate)'})
            with urllib.request.urlopen(req, timeout=60) as r: j = json.load(r)['chart']['result'][0]
            q, off, meta = j['indicators']['quote'][0], j['meta'].get('gmtoffset', 0), j['meta']
            rows = []
            for i, ts in enumerate(j['timestamp']):
                c = q['close'][i]
                if c is None and i == len(j['timestamp']) - 1 and meta.get('regularMarketPrice') and (meta.get('regularMarketTime') or 0) >= ts + 6.4 * 3600:
                    # Yahoo 收市後最後一根 close 間中係 null（2026-11-06 ^N225），已收市就用 regularMarketPrice 補（同報告中心 fillMissingClose 一樣）
                    c = meta['regularMarketPrice']
                    q['high'][i] = max(x for x in (q['high'][i], c) if x is not None); q['low'][i] = min(x for x in (q['low'][i], c) if x is not None)
                if c is None: continue
                d = dt.datetime.fromtimestamp(ts + off, dt.timezone.utc).date().isoformat()
                rows.append(dict(d=d, o=q['open'][i] or c, h=q['high'][i] or c, l=q['low'][i] or c, c=c, v=q['volume'][i] or 0))
            return rows
        except Exception as e: last = e
    raise last


def fix_scale(rows):
    """Yahoo 間中有幾日價格細咗／大咗 10、100、1000 倍（2026-11-06 發現：1321 10/05–06 收 7.28／7.35，正常約 710；
    1306 03/30–31 收 37.6／37.1，正常約 383；成交量反方向放大），會搞亂 MA50／MA200／52 週高同 50 日均量。
    同前後各 5 根收市中位數比，比例接近 10 嘅次方（±10%）就將開高低收乘返、成交量除返。回傳修正咗嘅日期 list。"""
    import statistics
    fixed = []
    for i, x in enumerate(rows):
        nb = [r['c'] for r in rows[max(0, i - 5):i] + rows[i + 1:i + 6] if r.get('c')]
        if len(nb) < 4 or not x.get('c'): continue
        k = statistics.median(nb) / x['c']
        for f in (10, 100, 1000, 0.1, 0.01, 0.001):
            if abs(k / f - 1) <= 0.10:
                for key in ('o', 'h', 'l', 'c'): x[key] = x[key] * f
                x['v'] = x['v'] / f; fixed.append(f'{x["d"]}×{f:g}'); break
    return fixed


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith('-'): sys.exit(__doc__)
    date = a[0]; dt.date.fromisoformat(date)
    extra = json.loads(a[a.index('--extra') + 1]) if '--extra' in a else {}
    if dt.date.fromisoformat(date).weekday() >= 5: sys.exit(f'{date} 係週末，唔係{PR["name"]}交易日')
    os.makedirs(DATA, exist_ok=True)
    for f in os.listdir(DATA): os.remove(os.path.join(DATA, f))      # 唔好用到上一日留低嘅檔
    have, missing, last, warn = [], [], {}, []
    hh, mm = map(int, PR['close'].split(':'))
    close_local = dt.datetime.fromisoformat(date).replace(hour=hh, minute=mm, tzinfo=LOC) + dt.timedelta(minutes=15)
    close_utc = close_local.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
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
        fx = fix_scale(rows)
        if fx: warn.append(f'{t} Yahoo 日線有價格比例錯誤，已還原（價×倍數、量÷倍數）：{"、".join(fx)}；報告第二節要註明')
        if t not in extra and rows[-1].get('fa', '9') < close_utc:
            sys.exit(f'{t} {date} 嘅 bar 係盤中攞（fa={rows[-1].get("fa")} < 收市後 {close_utc}），唔可以用；收市後再跑')
        if len(rows) < 210: warn.append(f'{t} 只有 {len(rows)} 根日線，MA200 唔可靠')
        rows = rows[-400:]
        json.dump({'symbol': j.get('symbol', t), 'rows': [{k: x[k] for k in ('d', 'o', 'h', 'l', 'c', 'v')} for x in rows]}, open(f'{DATA}/{t}.json', 'w'))
        have.append(t); last[t] = [rows[-1]['d'], rows[-1]['c'], rows[-1]['v']]
    idx_have = []
    for x in PR['index']:
        try:
            rows = [r for r in yahoo_index(x['y']) if r['d'] <= date]
            if not rows or rows[-1]['d'] != date:
                missing.append({'t': x['shot'], 'err': f'指數 {x["y"]} 最後一根 {rows[-1]["d"] if rows else None} ≠ {date}'}); continue
            json.dump({'symbol': x['y'], 'rows': rows[-400:]}, open(f'{DATA}/IDX_{x["shot"]}.json', 'w'))
            idx_have.append(x['shot']); last[x['shot']] = [rows[-1]['d'], rows[-1]['c']]
        except Exception as e:
            missing.append({'t': x['shot'], 'err': f'指數 {x["y"]}：{str(e)[:100]}'})
    gone = [t for t in CORE if t not in have]
    meta = {'date': date, 'market': MKT, 'have': have, 'index': idx_have, 'missing': missing, 'chart_only': CHART_ONLY, 'warn': warn, 'last': last}
    if LEAD in have: meta['prev'] = json.load(open(f'{DATA}/{LEAD}.json'))['rows'][-2]['d']
    json.dump(meta, open(f'{DATA}/_meta.json', 'w'), ensure_ascii=False)
    for w in warn: print('⚠', w, file=sys.stderr)
    for m_ in missing: print('✗ 缺項', m_['t'], m_['err'], file=sys.stderr)
    print(json.dumps({'market': MKT, 'date': date, 'prev': meta.get('prev'), 'have': len(have), 'index': idx_have, 'core_missing': gone,
                      'lead': last.get(LEAD)}, ensure_ascii=False))
    if gone: sys.exit(f'核心標的缺 {gone}：build 會失敗，等 Yahoo 更新（或用 --extra 補）')


if __name__ == '__main__': main()
