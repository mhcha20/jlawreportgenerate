import json, os, math
HERE = os.path.dirname(os.path.abspath(__file__))

def load(t):
    jd = os.environ.get('JL_DATE')            # build.py 設定：優先用該日專屬數據檔，避免同一股票兩日同時做互相覆寫
    p = f'{HERE}/data/{t}_{jd}.json'
    d = json.load(open(p if jd and os.path.exists(p) else f'{HERE}/data/{t}.json'))
    return d['closes'], d['bars']          # bars: [md,o,h,l,c,vol_k]

def sma(c, k, end=None):
    end = len(c) if end is None else end
    if end < k: return float('nan')       # 日線不足（新上市）：顯式 NaN，唔好靜默算錯
    return sum(c[end-k:end]) / k

def pct(a, b, d=2):                       # a/b-1 in %
    return (a / b - 1) * 100

def sg(x, d=2, p='%'):
    """signed number with ▲/▼ (V2.0 §六)"""
    cls = 'up' if x >= 0 else 'dn'
    ar = '▲' if x >= 0 else '▼'
    return f'<span class="{cls}">{ar}{abs(x):.{d}f}{p}</span>'

def metrics(t):
    c, b = load(t)
    n = len(b)
    O = [x[1] for x in b]; H = [x[2] for x in b]; L = [x[3] for x in b]; C = [x[4] for x in b]; V = [x[5] for x in b]
    assert C == c[-n:], 'closes/bars mismatch'
    m = dict(t=t, n=n, bars=b, closes=c)
    m['close'] = C[-1]; m['prev'] = C[-2]; m['open'] = O[-1]; m['high'] = H[-1]; m['low'] = L[-1]
    m['chg'] = C[-1] - C[-2]; m['chgp'] = pct(C[-1], C[-2])
    m['gap'] = O[-1] - C[-2]; m['gapp'] = pct(O[-1], C[-2]); m['intrap'] = pct(C[-1], O[-1])
    m['clv'] = (C[-1] - L[-1]) / (H[-1] - L[-1]) * 100 if H[-1] != L[-1] else 50.0   # 平盤 K 線
    m['vol'] = V[-1]; m['volprev'] = V[-2]
    m['v50'] = sum(V[-51:-1]) / 50; m['v20'] = sum(V[-21:-1]) / 20          # 不含當日（群組口徑）
    m['v50i'] = sum(V[-50:]) / 50; m['v20i'] = sum(V[-20:]) / 20          # 含當日（並列）
    m['volr50'] = V[-1] / m['v50'] * 100; m['volr20'] = V[-1] / m['v20'] * 100
    m['volrprev'] = V[-1] / V[-2] * 100
    for k in (10, 20, 50, 200):
        m[f'ma{k}'] = sma(c, k)
        m[f'ma{k}_5'] = sma(c, k, len(c) - 5)
        m[f'd{k}'] = pct(C[-1], m[f'ma{k}'])
    m['ma50_10'] = sma(c, 50, len(c) - 10)
    m['hi52'] = max(H[-126:]) if n >= 126 else max(H)   # 126 bars ≈ 6M; true 52w computed from Longbridge jq below
    m['atr14'] = sum(max(H[i]-L[i], abs(H[i]-C[i-1]), abs(L[i]-C[i-1])) for i in range(n-14, n)) / 14
    m['atrp'] = m['atr14'] / C[-1] * 100
    trs = [max(H[i]-L[i], abs(H[i]-C[i-1]), abs(L[i]-C[i-1])) for i in range(1, n)]
    wa = sum(trs[:14]) / 14
    for x in trs[14:]: wa = (wa * 13 + x) / 14
    m['atr14w'] = wa; m['atrpw'] = wa / C[-1] * 100
    m['ret5'] = pct(C[-1], C[-6]); m['ret20'] = pct(C[-1], C[-21])
    # distribution days (down day, volume > previous day and > own 50-day average), last 25 sessions
    dist = []
    for i in range(n-25, n):
        a50 = sum(V[i-50:i]) / 50
        if C[i] < C[i-1] and V[i] > V[i-1] and V[i] > a50:
            dist.append(b[i][0])
    m['dist'] = dist
    # days closing above own 50MA over last 30
    ab = 0
    for i in range(len(c)-30, len(c)):
        if c[i] > sum(c[i-49:i+1]) / 50: ab += 1
    m['above50_30'] = ab
    m['H'] = H; m['L'] = L; m['C'] = C; m['O'] = O; m['V'] = V
    return m

def sweep(m, stop_pct, fwd=5, win=60):
    """雜訊被掃率：過去 win 個交易日（只計有完整 fwd 日窗口者）每日收市假想入場，其後 fwd 日內最低價觸及 入場價×(1−止損%) 嘅比例"""
    n = m['n']; C = m['C']; L = m['L']
    idx = list(range(n - 1 - fwd - win + 1, n - 1 - fwd + 1))
    hit = sum(1 for i in idx if min(L[i+1:i+1+fwd]) <= C[i] * (1 - stop_pct))
    return hit, len(idx), m['bars'][idx[0]][0], m['bars'][idx[-1]][0]

def count_prints(m, lo, hi, days=20):
    """days (last `days`) whose low<=hi and high>=lo; returns count, last date"""
    n = m['n']; hits = []
    for i in range(n-days, n):
        if m['L'][i] <= hi and m['H'][i] >= lo:
            hits.append(m['bars'][i][0])
    return len(hits), (hits[-1] if hits else None)

# ---------------------------------------------------------------- charts
def fmtp(x):
    return f'{x:.2f}'

def chart(m, nbars, ma_list=(10, 20, 50, 200), zones=(), hlines=(), right_pad=0, width=700, height=300, show_vol=True, labels=(), vol_ma=None):
    c, b = m['closes'], m['bars']; n = len(b)
    i0 = n - nbars
    seg = b[i0:]
    allc = c
    def ma_at(k, i):     # i index in bars
        e = len(c) - (n - i)
        return sum(c[e-k+1:e+1]) / k
    pad_l, pad_r, pad_t, pad_b = 6, 62, 8, 16
    vol_h = 46 if show_vol else 0
    W, Hh = width, height
    ph = Hh - pad_t - pad_b - vol_h
    prices = [x[2] for x in seg] + [x[3] for x in seg]
    for k in ma_list:
        prices += [ma_at(k, i) for i in range(i0, n)]
    for z in zones:
        if not z.get('noscale'): prices += [z['lo'], z['hi']]
        else: prices += [z['lo']]
    for h in hlines:
        if not h.get('noscale'): prices.append(h['p'])
    pmin, pmax = min(prices), max(prices)
    span = pmax - pmin
    pmin -= span * 0.10; pmax += span * 0.10           # V2.0: Y axis ±10%
    tot = nbars + right_pad
    cw = (W - pad_l - pad_r) / tot
    def X(i): return pad_l + (i - i0 + 0.5) * cw
    def Y(p): return pad_t + (pmax - p) / (pmax - pmin) * ph
    s = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<rect x="0" y="0" width="{W}" height="{Hh}" fill="#fff"/>')
    # grid / y labels
    step = nice_step((pmax - pmin) / 6)
    g = math.ceil(pmin / step) * step
    while g <= pmax:
        y = Y(g)
        s.append(f'<line x1="{pad_l}" x2="{W-pad_r}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e8ec" stroke-width=".6"/>')
        s.append(f'<text x="{W-pad_r+4}" y="{y+3:.1f}" font-size="8" fill="#555">{g:.2f}</text>')
        g += step
    # zones (translucent) — start from the bar that formed them
    for z in zones:
        xs = X(z.get('start', i0)) - cw / 2
        xe = (W - pad_r) if not z.get('right') else (W - pad_r)
        if z.get('right'):                               # right-side margin only (risk/reward boxes)
            xs = X(n - 1) + cw / 2
        y1, y2 = Y(min(z['hi'], pmax)), Y(max(z['lo'], pmin))
        s.append(f'<rect x="{xs:.1f}" y="{y1:.1f}" width="{xe-xs:.1f}" height="{y2-y1:.1f}" fill="{z["color"]}" fill-opacity="{z.get("op",0.16)}"/>')
        if z.get('label'):
            s.append(f'<text x="{xs+3:.1f}" y="{y1+9:.1f}" font-size="7.5" fill="{z["color"]}">{z["label"]}</text>')
    # volume
    if show_vol:
        vmax = max(x[5] for x in seg)
        base = Hh - pad_b
        for j, x in enumerate(seg):
            i = i0 + j
            up = x[4] >= x[1]
            hgt = x[5] / vmax * (vol_h - 6)
            s.append(f'<rect x="{X(i)-cw*0.34:.1f}" y="{base-hgt:.1f}" width="{cw*0.68:.1f}" height="{hgt:.1f}" fill="{"#7fc4a0" if up else "#e59a92"}"/>')
        if vol_ma:
            yv = base - vol_ma / vmax * (vol_h - 6)
            s.append(f'<line x1="{pad_l}" x2="{W-pad_r}" y1="{yv:.1f}" y2="{yv:.1f}" stroke="#1f3a5f" stroke-dasharray="3,2" stroke-width=".7"/>')
            s.append(f'<text x="{W-pad_r+4}" y="{yv+3:.1f}" font-size="7" fill="#1f3a5f">50日均量</text>')
    # candles (陽綠陰紅)
    for j, x in enumerate(seg):
        i = i0 + j
        up = x[4] >= x[1]
        col = '#1a9e5c' if up else '#d6453d'
        xc = X(i)
        s.append(f'<line x1="{xc:.1f}" x2="{xc:.1f}" y1="{Y(x[2]):.1f}" y2="{Y(x[3]):.1f}" stroke="{col}" stroke-width=".8"/>')
        y1, y2 = Y(max(x[1], x[4])), Y(min(x[1], x[4]))
        s.append(f'<rect x="{xc-cw*0.34:.1f}" y="{y1:.1f}" width="{cw*0.68:.1f}" height="{max(y2-y1,.8):.1f}" fill="{col}"/>')
    # MAs
    cols = {10: '#e08a1e', 20: '#8e44ad', 50: '#2e86c1', 200: '#7f8c8d'}
    for k in ma_list:
        pts = ' '.join(f'{X(i):.1f},{Y(ma_at(k,i)):.1f}' for i in range(i0, n))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{cols[k]}" stroke-width="1.1"/>')
    # horizontal lines；右側價位標籤若互相重疊（例如現價貼近入場價）就上下推開，線本身唔郁
    hl = [(Y(min(h['p'], pmax)), h) for h in hlines]
    LBH = 11.5
    ly = [y for y, _ in hl]
    order = sorted(range(len(ly)), key=lambda i: ly[i])
    for _ in range(20):
        moved = False
        for a, b2 in zip(order, order[1:]):
            gap = ly[b2] - ly[a]
            if gap < LBH:
                d = (LBH - gap) / 2; ly[a] -= d; ly[b2] += d; moved = True
        if not moved: break
    for (y, h), yl in zip(hl, ly):
        clipped = h['p'] > pmax
        s.append(f'<line x1="{pad_l}" x2="{W-pad_r}" y1="{y:.1f}" y2="{y:.1f}" stroke="{h["color"]}" stroke-width="{h.get("w",1)}" stroke-dasharray="{h.get("dash","4,3")}"/>')
        if abs(yl - y) > 0.5: s.append(f'<line x1="{W-pad_r}" x2="{W-pad_r+1}" y1="{y:.1f}" y2="{yl:.1f}" stroke="{h["color"]}" stroke-width=".8"/>')
        s.append(f'<rect x="{W-pad_r+1}" y="{yl-6:.1f}" width="{pad_r-2}" height="11" fill="{h["color"]}"/>')
        s.append(f'<text x="{W-pad_r+3}" y="{yl+2.5:.1f}" font-size="7.6" fill="#fff">{h["p"]:.2f}{"↑" if clipped else ""}</text>')
        if h.get('label'):
            s.append(f'<text x="{pad_l+3}" y="{y-2:.1f}" font-size="7.5" fill="{h["color"]}">{h["label"]}</text>')
    # x labels (month starts)
    last = ''
    for j, x in enumerate(seg):
        mo = x[0][:2]
        if mo != last:
            s.append(f'<text x="{X(i0+j):.1f}" y="{Hh-3}" font-size="7.5" fill="#555">{int(mo)}月</text>')
            last = mo
    # legend
    lx = pad_l + 4
    for k in ma_list:
        s.append(f'<line x1="{lx}" x2="{lx+12}" y1="{pad_t+4}" y2="{pad_t+4}" stroke="{cols[k]}" stroke-width="1.6"/><text x="{lx+15}" y="{pad_t+7}" font-size="7.5" fill="#333">MA{k}</text>')
        lx += 48
    s.append('</svg>')
    return ''.join(s)

def nice_step(raw):
    e = 10 ** math.floor(math.log10(raw))
    for f in (1, 2, 2.5, 5, 10):
        if raw <= f * e: return f * e
    return 10 * e

# ---------------------------------------------------------------- html helpers
def table(headers, rows, widths=None, cls=''):
    h = ''
    if headers: h = '<thead><tr>' + ''.join(f'<th>{x}</th>' for x in headers) + '</tr></thead>'
    cg = ('<colgroup>' + ''.join(f'<col style="width:{w}">' for w in widths) + '</colgroup>') if widths else ''
    body = ''
    for r in rows:
        rc = ''
        if isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], (list, tuple)): r, rc = r
        body += f'<tr class="{rc}">' + ''.join(f'<td>{x}</td>' for x in r) + '</tr>'
    return f'<table class="{cls}">{cg}{h}<tbody>{body}</tbody></table>'

def sec(t, small=''): return f'<h2 class="sec">{t}' + (f' <span class="ss">{small}</span>' if small else '') + '</h2>'
def note(t): return f'<p class="sec-note">{t}</p>'
def facts(items): return '<ul class="facts">' + ''.join(f'<li>{i}</li>' for i in items) + '</ul>'

def stars(n): return '★' * n + '☆' * (5 - n)

FONTS = ''.join(f'<link rel="stylesheet" href="node_modules/@fontsource/noto-sans-tc/{x}.css">' for x in
                ('chinese-traditional-400', 'chinese-traditional-700', 'latin-400', 'latin-700'))
import re
def arrows(h):
    # V2.0 §六：全篇 +／− → ▲／▼（綠／紅）
    h = re.sub(r'(?<![\w.\d])\+(\d[\d,.]*)(%| 點)', lambda m_: f'<span class="up">▲{m_.group(1)}{m_.group(2)}</span>', h)
    h = re.sub(r'(?<![\w.\d>])[-−](\d[\d,.]*)(%| 點)', lambda m_: f'<span class="dn">▼{m_.group(1)}{m_.group(2)}</span>', h)
    return h
def chips(h):
    for w in ('圖表', '外部', '計算', '推論'):
        h = h.replace(f'[{w}]', f'<span class="tg">{w}</span>')
    return h
def scrub_rules(h):
    """報告內任何位置唔提「群組執行規則」（群組有新規則會貼出）：刪走含呢個詞嘅句子／缺項項目，並清走空殼 <li>／<tr>"""
    h = re.sub(r'(?:本份(?:亦)?)?唔套用倉位上限[；，。]?', '', h)
    h = h.replace('未決問題（交群組裁決）', '未決問題').replace('六、交返群組裁決嘅未決問題', '六、未決問題')
    h = re.sub(r'[，、；]?(?:請|交)群組(?:裁決|確認|判斷|補充)[^。；？<]*[？]?', '', h)          # 唔向群組「交裁決／請確認」
    h = re.sub(r'[，、；]?群組想用邊[種個][^。；？<]*[？]?', '', h)
    h = re.sub(r'[（(]?(?:同群組公式一致|沿用群組口徑)[）)]?', '', h)
    h = h.replace('對齊群組慣例，', '').replace('（對齊群組慣例）', '').replace('按群組口徑用', '用').replace('群組窗口未提供，', '').replace('冇群組機械定義', '冇機械定義')
    h = re.sub(r'（或確認群組[^）]*）', '', h)
    h = re.sub(r'[，、；：]?群組(?:想|有冇|對|是否)[^。；？<]*[？]?', '', h)
    h = re.sub(r'[，、；]?[^。；<>，]*倉位比例群組未提供[，,]?不自訂', '', h)
    if '執行規則' not in h and '群組' not in h: return h
    h = re.sub(r'[；、]\s*(?:群組)?(?:大盤)?執行規則(?:（[^）]*）)?(?=[；。<])', '', h)          # 「…；承襲帳；大盤執行規則。」類缺項項目
    h = re.sub(r'(?:承襲帳|承襲帳同|承襲帳／)(?:群組)?(?:大盤)?執行規則', '承襲帳', h)
    def node(m):
        t = m.group(1)
        parts = re.split(r'(?<=[。？])', t)
        keep = [p for p in parts if '執行規則' not in p]
        out = ''.join(keep)
        if out.count('「') > out.count('」'): out += '」'
        if out.count('（') > out.count('）'): out += '）'
        out = re.sub(r'^[；，、：\s]+', '', out) if out.strip() else ''
        return '>' + out + '<'
    h = re.sub(r'>([^<>]*執行規則[^<>]*)<', node, h)
    def node2(m):
        t = m.group(1)
        out = ''.join(p for p in re.split(r'(?<=[。？])', t) if '群組' not in p)
        if out.count('「') > out.count('」'): out += '」'
        return '>' + (re.sub(r'^[；，、：\s]+', '', out) if out.strip() else '') + '<'
    h = re.sub(r'>([^<>]*群組[^<>]*)<', node2, h)
    h = re.sub(r'<li>\s*</li>', '', h)
    h = re.sub(r'<tr>(?:\s*<t[hd][^>]*>[^<]*</t[hd]>)?(?:\s*<td[^>]*>\s*</td>)+\s*</tr>', '', h)
    return h
def localize(h, S):
    """按市場（S['ccy']／['cur']…，plan_numbers 設默認）換走寫死嘅美股字眼，唔使每隻 worker 自己後處理"""
    h = re.sub(r'[（(]檔案[①②③][）)]', '', h)          # 唔再用「檔案①②③」字眼
    for a, b in (('檔案①', '行動卡'), ('檔案②', '本體報告'), ('檔案③', '核對附錄')): h = h.replace(a, b)
    h = re.sub(r'<span class="(?:up|dn)">[▲▼]nan%</span>', 'N/A', h)    # 新上市股：日線唔夠長嘅指標顯示 N/A，唔好出 nan
    h = re.sub(r'(?<![A-Za-z])nan(?![A-Za-z])', 'N/A', h)
    if S.get('prior_same'):     # 上一份係我哋自己同一套九構面計法 → 可直接比較升降（S['prior_same']=True）
        h = re.sub(r'分數由本份重新起算，唔可以同其他股票或上一份 (.*?) 直接比較。', r'分數唔可以同其他股票比較；同上一份 \1 係同一九構面計法，可直接比較升降。', h)
        h = h.replace('；計法不同，唔作升降', '；同一九構面計法，可直接比較升降').replace('（計法唔同，唔作升降）', '（同一九構面計法，可直接比較升降）').replace('計法唔同，唔作升降', '同一九構面計法，可直接比較升降')
        h = h.replace('成交量用 Longbridge', '成交量用 Yahoo')
        h = h.replace('（評分表未提供，無法逐格比較，唔當升降）', '（同一九構面計法，可直接比較升降）')
        h = h.replace('本份係首份，九構面全部重新起算，所以每格都寫理由', '九構面全部按當日數據重新評分，每格都寫理由')
    h = scrub_rules(h)
    h = re.sub(r'。(?:\s*。)+', '。', h)     # 句尾重複句號（例如 tier 字串後再加「。」）
    h = re.sub(r'[；，、]?(?:群組)?(?:大盤)?執行規則未收到[，,]唔套用倉位上限', '', h)    # 群組有新規則會貼出，唔使每份報告特別講
    h = re.sub(r'[，、]?按\s*V1\.0\s*唔套用倉位上限', '', h)
    ccy, cur = S.get('ccy', 'USD'), S.get('cur', '$')
    if ccy != 'USD': h = h.replace('USD', ccy)
    if cur != '$': h = re.sub(r'(?<![A-Za-z])\$(?=\d)', lambda _: cur, h)
    if S.get('src_name', 'Longbridge') != 'Longbridge':     # 只換範本預設嘅資料來源句；worker 自己寫嘅「Longbridge」（核實、MCP、並列）照留
        h = h.replace('成交量用 Longbridge', '成交量用 ' + S['src_name'])
    if S.get('smart_hard', '13F／Form 4') != '13F／Form 4': h = h.replace('13F／Form 4', S['smart_hard'])
    if S.get('cov', '覆蓋率 100%') != '覆蓋率 100%': h = h.replace('覆蓋率 100%', S['cov'])
    if S.get('ma_chk'): h = h.replace('同 TradingView 圖示一致到兩位小數', S['ma_chk'])
    return h
def page(title, body, S=None):
    body = chips(arrows(localize(body, S) if S else body))
    return f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>{title}</title>{FONTS}<link rel="stylesheet" href="style.css"></head><body>{body}</body></html>'

# ---- 朗讀稿用：數字→口語中文
D = '零一二三四五六七八九'
def _zh4(n):      # 0–9999
    s, zero = '', False
    for u, name in ((1000, '千'), (100, '百'), (10, '十'), (1, '')):
        q, n = divmod(n, u)
        if q:
            if zero: s += '零'
            s += D[q] + name; zero = False
        elif s: zero = True
    return s
def zhint(n):
    n = int(n)
    if n == 0: return '零'
    out, need0 = '', False
    for u, name in ((10**8, '億'), (10**4, '萬'), (1, '')):
        q, n = divmod(n, u)
        if q:
            if need0 or (out and q < 1000): out += '零'
            out += _zh4(q) + name; need0 = False
        elif out: need0 = True
    if out.startswith('一十'): out = out[1:]
    return out
def zh(x, d=2):
    s = f'{abs(x):.{d}f}'; a, b = s.split('.')
    return zhint(a) + '點' + ''.join(D[int(ch)] for ch in b)

