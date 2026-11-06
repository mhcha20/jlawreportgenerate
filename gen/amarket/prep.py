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
            q, off = j['indicators']['quote'][0], j['meta'].get('gmtoffset', 0)
            rows = []
            for i, ts in enumerate(j['timestamp']):
                c = q['close'][i]
                if c is None: continue
                d = dt.datetime.fromtimestamp(ts + off, dt.timezone.utc).date().isoformat()
                rows.append(dict(d=d, o=q['open'][i] or c, h=q['high'][i] or c, l=q['low'][i] or c, c=c, v=q['volume'][i] or 0))
            return rows
        except Exception as e: last = e
    raise last


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
