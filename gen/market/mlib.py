"""mlib.py — 大盤報告通用函數：行情載入（SPY／QQQ／IWM／板塊 ETF）、指標、HTML helper、QA 登記。
只放通用代碼；每日嘅讀數同敘述喺 work 檔（spec／texts）。"""
import datetime as dt, json, os
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # tools/stockreport
DATA = os.path.join(HERE, 'data')
NY, HK = ZoneInfo('America/New_York'), ZoneInfo('Asia/Hong_Kong')

INDEXES = ['SPY', 'QQQ', 'IWM']
SECTORS = [('XLK', '科技'), ('XLF', '金融'), ('XLE', '能源'), ('XLV', '醫療'), ('XLY', '非必需消費'), ('XLP', '必需消費'),
           ('XLI', '工業'), ('XLB', '原材料'), ('XLU', '公用'), ('XLRE', '房地產'), ('XLC', '通訊')]
SECTOR_NAME = dict(SECTORS)
YAHOO_OK = INDEXES + [s for s, _ in SECTORS] + ['SMH']       # 網站 /api/ohlcv（Yahoo）攞得到
CHART_ONLY = ['VIX', 'SOX', 'DXY', 'GC1!', 'US10Y']          # Yahoo 唔識（指數／期貨／債息）→ 只可讀截圖，報告標「圖表讀數」缺外部對照
# 截圖資料夾每日 19 張：NN_TICKER_Daily.png（編號每日固定，但以代號判斷齊唔齊）
SHOT_TICKERS = ['IWM', 'VIX', 'SPY', 'QQQ', 'SOX'] + [s for s, _ in SECTORS] + ['DXY', 'GC1!', 'US10Y']

def pct(a, b): return (a / b - 1) * 100
def clv(c, h, l): return (c - l) / (h - l) * 100 if h != l else 50.0
def wd(date): y, m, d = map(int, date.split('-')); return '一二三四五六日'[dt.date(y, m, d).weekday()]
def md(date): return date[5:].replace('-', '/')

# ---------------------------------------------------------------- 行情
class Sym:
    """一個標的日線（rows 最後一根＝報告日）。均量口徑 basis：'incl'＝50 日含當日（10/19–10/21 大盤報告口徑），'excl'＝不含當日。"""
    def __init__(s, t, rows, basis='incl'):
        s.t, s.rows, s.n, s.basis = t, rows, len(rows), basis
        s.C = [r['c'] for r in rows]; s.H = [r['h'] for r in rows]; s.L = [r['l'] for r in rows]
        s.O = [r['o'] for r in rows]; s.V = [r['v'] for r in rows]; s.D = [r['d'] for r in rows]
        s.date = s.D[-1]; s.pdate = s.D[-2]
        s.o, s.h, s.l, s.c, s.v = s.O[-1], s.H[-1], s.L[-1], s.C[-1], s.V[-1]
        s.po, s.ph, s.pl, s.pc, s.pv = s.O[-2], s.H[-2], s.L[-2], s.C[-2], s.V[-2]
        s.ppc = s.C[-3]
        s.chg = s.c - s.pc; s.chgp = pct(s.c, s.pc); s.pchgp = pct(s.pc, s.ppc)
        s.gapp = pct(s.o, s.pc); s.ocp = pct(s.c, s.o)
        s.h52 = max(s.H[-252:]); s.l52 = min(s.L[-252:])
        s.ret5 = pct(s.c, s.C[-6]); s.ret20 = pct(s.c, s.C[-21])
    def ma(s, k, back=0):
        e = s.n - back
        return sum(s.C[e - k:e]) / k if e >= k else float('nan')
    def v50(s, back=0, basis=None):
        e = s.n - back
        if (basis or s.basis) == 'incl': return sum(s.V[e - 50:e]) / 50
        return sum(s.V[e - 51:e - 1]) / 50
    def vr(s, back=0): return s.V[s.n - 1 - back] / s.v50(back) * 100          # 當日量÷50 日均量 %（唔係 RVOL20）
    def candle(s, back=0):
        i = s.n - 1 - back; o, h, l, c = s.O[i], s.H[i], s.L[i], s.C[i]; r = (h - l) or 1e-9
        return dict(o=o, h=h, l=l, c=c, body=abs(c - o) / r * 100, up=(h - max(c, o)) / r * 100, lo=(min(c, o) - l) / r * 100,
                    clv=clv(c, h, l), oc=pct(c, o), col='陽燭' if c >= o else '陰燭', updown='升日' if c >= s.C[i - 1] else '跌日')
    def above(s):
        return [k for k in (10, 20, 50, 200) if s.c > s.ma(k)]
    def dist_days(s, window=25, micro=0.2):
        """派發日：下跌日（strict）或微升日（升幅≤micro%）＋ 量＞前日 ＋ 量＞當日滾動 50 日均量；回傳 (strict 日期 list, 含微升日 list)"""
        st, mi = [], []
        for i in range(s.n - window, s.n):
            e = i + 1
            a50 = sum(s.V[e - 50:e]) / 50 if s.basis == 'incl' else sum(s.V[e - 51:e - 1]) / 50
            if s.V[i] > s.V[i - 1] and s.V[i] > a50:
                p = pct(s.C[i], s.C[i - 1])
                if p < 0: st.append(s.D[i])
                if p <= micro: mi.append(s.D[i])
        return st, mi

class Market:
    def __init__(s, date, basis='incl'):
        s.date, s.basis, s.sym = date, basis, {}
        meta = os.path.join(DATA, '_meta.json')
        s.meta = json.load(open(meta)) if os.path.exists(meta) else {}
        assert s.meta.get('date') == date, f'data/_meta.json 日期 {s.meta.get("date")} ≠ {date}：先跑 python3 market/prep.py {date}'
        for t in YAHOO_OK:
            f = os.path.join(DATA, f'{t}.json')
            if not os.path.exists(f): continue
            rows = [r for r in json.load(open(f))['rows'] if r['d'] <= date]
            if rows and rows[-1]['d'] == date and len(rows) >= 210: s.sym[t] = Sym(t, rows, basis)
        s.missing = [t for t in YAHOO_OK if t not in s.sym] + CHART_ONLY
        for t in INDEXES + [x for x, _ in SECTORS]:
            assert t in s.sym, f'{t} 日線缺或最後一根唔係 {date}（prep.py 再跑；Yahoo 未更新就用 --extra 補，並喺報告註明來源）'
        s.pdate = s.sym['SPY'].pdate
    def __getitem__(s, t): return s.sym[t]

def et_hk(date, hhmm):
    """美東 date hhmm → ('10:00 EDT', '22:00', '日差')。夏令／冬令自動判斷"""
    y, mo, d = map(int, date.split('-')); h, mi = map(int, hhmm.split(':'))
    e = dt.datetime(y, mo, d, h, mi, tzinfo=NY); k = e.astimezone(HK)
    return e.strftime('%H:%M') + ' ' + e.tzname(), k.strftime('%m/%d（') + wd(k.strftime('%Y-%m-%d')) + k.strftime('）%H:%M')
def utc_to(date_hhmm_utc):
    """'2026-10-21 21:02'（UTC）→ (ET 字串, HKT 字串, ET datetime)"""
    u = dt.datetime.strptime(date_hhmm_utc, '%Y-%m-%d %H:%M').replace(tzinfo=dt.timezone.utc)
    e, k = u.astimezone(NY), u.astimezone(HK)
    return f'{e:%Y-%m-%d %H:%M} {e.tzname()}', f'{k:%Y-%m-%d %H:%M}', e

# ---------------------------------------------------------------- 格式
def P(x, d=4): return ('＋' if x >= 0 else '▼') + f'{abs(x):.{d}f}%'
def N(x, d=4): return ('＋' if x >= 0 else '▼') + f'{abs(x):.{d}f}'
def AR(x, d=4, p=False): return ('▲＋' if x >= 0 else '▼') + f'{abs(x):.{d}f}' + ('%' if p else '')
def tag(t): return f'<span class="tag">{t}</span>'
CALC, INF, CHART, EXT = tag('計算結果'), tag('分析推論'), tag('圖表讀數'), tag('外部已核實')
def sec(num, title): return f'<h2 class="sec"><span class="n">{num}</span>{title}</h2>'
def sub(t): return f'<h3>{t}</h3>'
def box(h, cls=''): return f'<div class="box {cls}">{h}</div>'
def pre(t): return f'<p class="pre">{t}</p>'
def table(headers, rows, widths=None, align=None, cls='', kv=False):
    h = ('<thead><tr>' + ''.join(f'<th>{c}</th>' for c in headers) + '</tr></thead>') if headers else ''
    body = ''
    for r in rows:
        cells, rc = r if isinstance(r, tuple) else (r, '')
        body += f'<tr class="{rc}">' + ''.join(
            f'<td class="{ {"l": "", "r": "num", "c": "ctr"}[(align[i] if align else "l")] }">{c}</td>' for i, c in enumerate(cells)) + '</tr>'
    cg = ('<colgroup>' + ''.join(f'<col style="width:{w}">' for w in widths) + '</colgroup>') if widths else ''
    return f'<table class="{cls}{" kv" if kv else ""}">{cg}{h}<tbody>{body}</tbody></table>'

def lvl(price, level):
    """價位距離：(÷現價 %, ÷線價 %)；level 喺上為正"""
    return (level / price - 1) * 100, (price / level - 1) * 100

# ---------------------------------------------------------------- QA 登記
QA = []
def chk(name, actual, expected, tol=0.00501):
    """數字覆核：actual（報告用嘅值）同 expected（獨立重算）差距 ≤ tol（要細過最後一位）"""
    ok = abs(actual - expected) <= tol
    QA.append((name, ok, actual, expected)); return ok
def chk_true(name, cond, detail=''):
    QA.append((name, bool(cond), detail, True)); return bool(cond)
def qa_report():
    bad = [q for q in QA if not q[1]]
    for q in bad: print('QA 失敗：', q)
    print(f'QA：共 {len(QA)} 項，失敗 {len(bad)} 項')
    return len(QA), len(bad)
