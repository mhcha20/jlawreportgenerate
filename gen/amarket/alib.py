"""alib.py — 香港／日本／韓國大盤報告通用函數（由 gen/market/mlib.py 改：標的由 profiles.py 決定）。
市場由環境變數 AMARKET（hk／jp／kr）揀；build.py／prep.py 會設定。只放通用代碼；每日讀數同敘述喺 work 檔。
m['02800']／m.core／m.sectors／m.idx['HSI']；價錢格式用 F()（按價位大細自動揀小數位），百分比用 P(x)（2 位）。"""
import datetime as dt, json, os
from zoneinfo import ZoneInfo
from profiles import PROFILES

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # gen/
MKT = os.environ.get('AMARKET', 'hk')
PR = PROFILES[MKT]
DATA = os.path.join(HERE, 'data', MKT)
HK = ZoneInfo('Asia/Hong_Kong'); NY = ZoneInfo('America/New_York'); LOC = ZoneInfo(PR['tz'])
CORE = [x['t'] for x in PR['core']]                 # 報告主角 ETF（等同 SPY／QQQ／IWM）
SECTORS = [(x['t'], x['name']) for x in PR['sectors']]
SECTOR_NAME = dict(SECTORS)
NAME = {x['t']: x['name'] for x in PR['core'] + PR['sectors']}
SHOT_OF = {x['t']: x['shot'] for x in PR['core'] + PR['sectors']}
YAHOO_OK = CORE + [t for t, _ in SECTORS]          # /api/ohlcv（Yahoo）攞得到
INDEXES = [x['shot'] for x in PR['index']]          # Yahoo 指數（只核對收市同升跌）
CHART_ONLY = PR['chart_only']
SHOT_TICKERS = PR['shots']
LEAD = CORE[0]                                      # 板塊相對強弱嘅基準（主指數 ETF）

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
    """m[t]＝Sym（core＋sectors，最後一根＝報告日）；m.idx[shot]＝Sym（Yahoo 指數，冇就唔喺度）。"""
    def __init__(s, date, basis='incl'):
        s.date, s.basis, s.sym, s.idx = date, basis, {}, {}
        s.pr, s.core, s.sectors, s.lead = PR, CORE, SECTORS, LEAD
        meta = os.path.join(DATA, '_meta.json')
        s.meta = json.load(open(meta)) if os.path.exists(meta) else {}
        assert s.meta.get('date') == date, f'data/{MKT}/_meta.json 日期 {s.meta.get("date")} ≠ {date}：先跑 AMARKET={MKT} python3 amarket/prep.py {date}'
        for t in YAHOO_OK:
            f = os.path.join(DATA, f'{t}.json')
            if not os.path.exists(f): continue
            rows = [r for r in json.load(open(f))['rows'] if r['d'] <= date]
            if rows and rows[-1]['d'] == date and len(rows) >= 210: s.sym[t] = Sym(t, rows, basis)
        for x in PR['index']:
            f = os.path.join(DATA, f'IDX_{x["shot"]}.json')
            if not os.path.exists(f): continue
            rows = [r for r in json.load(open(f))['rows'] if r['d'] <= date]
            if rows and rows[-1]['d'] == date and len(rows) >= 30: s.idx[x['shot']] = Sym(x['shot'], rows, basis)
        s.missing = [t for t in YAHOO_OK if t not in s.sym] + [x['shot'] for x in PR['index'] if x['shot'] not in s.idx] + CHART_ONLY
        for t in CORE:
            assert t in s.sym, f'{t} 日線缺或最後一根唔係 {date}（prep.py 再跑；Yahoo 未更新就等收市後）'
        s.pdate = s.sym[LEAD].pdate
    def __getitem__(s, t): return s.sym[t]
    def name(s, t): return NAME.get(t, t)

def loc_hk(date, hhmm, tz=None):
    """當地（或 tz='ET' 美東）date hhmm → (當地字串, 香港字串)"""
    z = NY if tz == 'ET' else LOC
    y, mo, d = map(int, date.split('-')); h, mi = map(int, hhmm.split(':'))
    e = dt.datetime(y, mo, d, h, mi, tzinfo=z); k = e.astimezone(HK)
    lab = e.tzname() if tz == 'ET' else PR['tzname']
    return e.strftime('%H:%M') + ' ' + lab, k.strftime('%m/%d（') + wd(k.strftime('%Y-%m-%d')) + k.strftime('）%H:%M')
def utc_to(date_hhmm_utc):
    """'2026-11-06 09:52'（UTC）→ (當地字串, HKT 字串, 當地 datetime)"""
    u = dt.datetime.strptime(date_hhmm_utc, '%Y-%m-%d %H:%M').replace(tzinfo=dt.timezone.utc)
    e, k = u.astimezone(LOC), u.astimezone(HK)
    return f'{e:%Y-%m-%d %H:%M} {PR["tzname"]}', f'{k:%Y-%m-%d %H:%M}', e

# ---------------------------------------------------------------- 格式
def _sg(x, d): return '' if round(x, d) == 0 else ('▲' if x > 0 else '▼')   # 升跌一律用符號（用戶 2026-11-06：唔好一時 ▼ 一時 ＋）
def P(x, d=2): return _sg(x, d) + f'{abs(x):.{d}f}%'
def N(x, d=2): return _sg(x, d) + f'{abs(x):.{d}f}'
def AR(x, d=2, p=False): return _sg(x, d) + f'{abs(x):.{d}f}' + ('%' if p else '')
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

def dp(x):
    """價錢小數位：≥10000 → 0；≥1000 → 1；≥100 → 2；其餘 3（港股 ETF 3.994、日股 36,680、韓股 79,005）"""
    a = abs(x); return 0 if a >= 10000 else 1 if a >= 1000 else 2 if a >= 100 else 3
def F(x, d=None): return f'{x:,.{dp(x) if d is None else d}f}'
def FI(x): return f'{x:,.2f}'                   # 指數一律 2 位小數
def FD(x, ref): return f'{x:,.{dp(ref)}f}'     # 用 ref 嘅小數位（差額、均線同收市一齊比較時）

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
