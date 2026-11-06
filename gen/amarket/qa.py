"""qa.py — PDF 文字回查（亞洲大盤）：用獨立寫嘅最小計算（只讀 data/<mkt>/*.json 原始數據，唔經 alib／report）重算主要數字，
確認每個數字都真係出現喺 PDF 文字入面。回傳 (檢查數, 失敗 list)。"""
import json, os, re, subprocess
from profiles import PROFILES
HERE = os.path.dirname(os.path.abspath(__file__))

def _dp(x):
    a = abs(x); return 0 if a >= 10000 else 1 if a >= 1000 else 2 if a >= 100 else 3

def run(date, pdf, mkt):
    pr = PROFILES[mkt]; data = os.path.join(HERE, 'data', mkt)
    rows = lambda t: [r for r in json.load(open(f'{data}/{t}.json'))['rows'] if r['d'] <= date]
    txt = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    flat = re.sub(r'\s+', '', txt).replace(',', '')
    n, bad = 0, []
    def need(label, s):
        nonlocal n; n += 1
        if re.sub(r'\s+', '', s).replace(',', '') not in flat: bad.append((label, s))
    lead = pr['core'][0]['t']; lc = [x['c'] for x in rows(lead)]; lchg = (lc[-1] / lc[-2] - 1) * 100
    for x in pr['core']:
        t = x['t']; r = rows(t); c = [y['c'] for y in r]; v = [y['v'] for y in r]; d = _dp(c[-1])
        need(f'{t} 收市', f'{c[-1]:,.{d}f}'); need(f'{t} 前收', f'{c[-2]:,.{d}f}')
        need(f'{t} 升跌%', f'{abs((c[-1] / c[-2] - 1) * 100):.2f}%')
        for k in (10, 20, 50, 200): need(f'{t} MA{k}', f'{sum(c[-k:]) / k:,.{d}f}')
        need(f'{t} 量比', f'{v[-1] / (sum(v[-50:]) / 50) * 100:.2f}%')
        need(f'{t} 成交量', f'{v[-1]:,.0f}'); need(f'{t} 50日均量', f'{sum(v[-50:]) / 50:,.0f}')
        h, l = r[-1]['h'], r[-1]['l']
        if h != l: need(f'{t} CLV', f'{(c[-1] - l) / (h - l) * 100:.2f}%')
    for x in pr['sectors']:
        t = x['t']
        if not os.path.exists(f'{data}/{t}.json'): continue
        r = rows(t); c = [y['c'] for y in r]
        if r[-1]['d'] != date: continue
        p = (c[-1] / c[-2] - 1) * 100
        need(f'{t} 當日%', f'{abs(p):.2f}%'); need(f'{t} 相對主指數', f'{abs(p - lchg):.2f}pp')
        need(f'{t} 近5日', f'{abs((c[-1] / c[-6] - 1) * 100):.2f}%'); need(f'{t} 近20日', f'{abs((c[-1] / c[-21] - 1) * 100):.2f}%')
        need(f'{t} 收市', f'{c[-1]:,.{_dp(c[-1])}f}')
    for x in pr['index']:
        f = f'{data}/IDX_{x["shot"]}.json'
        if not os.path.exists(f): continue
        r = [y for y in json.load(open(f))['rows'] if y['d'] <= date]
        if r[-1]['d'] != date: continue
        need(f'{x["shot"]} 收市', f'{r[-1]["c"]:,.2f}'); need(f'{x["shot"]} 升跌%', f'{abs((r[-1]["c"] / r[-2]["c"] - 1) * 100):.2f}%')
    return n, bad
