"""qa.py — PDF 文字回查：用獨立寫嘅最小計算（只讀 data/*.json 原始數據，唔經 mlib／report）重算主要數字，
確認每個數字都真係出現喺 PDF 文字入面（抓版面／格式／漏填錯）。回傳 (檢查數, 失敗 list)。"""
import json, os, re, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, 'data')
SECT = ['XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLP', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC']

def _rows(t, date):
    return [r for r in json.load(open(f'{DATA}/{t}.json'))['rows'] if r['d'] <= date]
def _sma(c, k): return sum(c[-k:]) / k

def pdf_text(pdf):
    return subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout

def run(date, pdf):
    txt = pdf_text(pdf); flat = re.sub(r'\s+', '', txt).replace(',', '')
    n, bad = 0, []
    def need(label, s):
        nonlocal n; n += 1
        if re.sub(r'\s+', '', s).replace(',', '') not in flat: bad.append((label, s))
    spy = _rows('SPY', date); spc = spy[-1]['c'] / spy[-2]['c'] - 1
    for t in ['SPY', 'QQQ', 'IWM']:
        r = _rows(t, date); c = [x['c'] for x in r]; v = [x['v'] for x in r]
        need(f'{t} 收市', f'{c[-1]:.4f}'); need(f'{t} 前收', f'{c[-2]:.4f}')
        need(f'{t} 升跌%', f'{abs((c[-1] / c[-2] - 1) * 100):.4f}%')
        for k in (10, 20, 50, 200): need(f'{t} MA{k}', f'{_sma(c, k):.4f}')
        need(f'{t} 量比', f'{v[-1] / (sum(v[-50:]) / 50) * 100:.2f}%')
        need(f'{t} 成交量', f'{v[-1]:,.0f}'); need(f'{t} 50日均量', f'{sum(v[-50:]) / 50:,.0f}')
        h, l = r[-1]['h'], r[-1]['l']; need(f'{t} CLV', f'{(c[-1] - l) / (h - l) * 100:.4f}%')
    for t in SECT:
        r = _rows(t, date); c = [x['c'] for x in r]
        p = (c[-1] / c[-2] - 1) * 100; need(f'{t} 當日%', f'{abs(p):.4f}%'); need(f'{t} 相對SPY', f'{abs(p - spc * 100):.4f}pp')
        need(f'{t} 近5日', f'{abs((c[-1] / c[-6] - 1) * 100):.4f}%'); need(f'{t} 近20日', f'{abs((c[-1] / c[-21] - 1) * 100):.4f}%')
        need(f'{t} 收市', f'{c[-1]:.4f}')
    return n, bad
