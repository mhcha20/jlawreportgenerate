"""report.py — 香港／日本／韓國大盤報告版面（由 gen/market/report.py 改：JW V1.0 第十節順序，標的由 profiles.py 決定）。
build_html(m, S, T)：m＝alib.Market；S＝work.spec(m)；T＝work.texts(m, S)。自動計算嘅表：圖面讀數對行情、主指數 ETF 比較表、燭身、
均線、價位距離、成交量、派發日、波動指數、廣度、宏觀、板塊；其餘敘述由 T 提供。欄位見 template_work.py。"""
from alib import *

def _g(T, k, default=''): return T.get(k, default)
def _rows(T, k): return T.get(k) or []
U = PR['unit']

def head(m, S, T):
    d = m.date
    o = [f'<h1>{PR["title"]}　{d}（{wd(d)}）收市</h1>']
    ai = S['meta']
    o.append(f'<p class="meta">分析框架：JW 大盤分析指令｜共用補充版 V1.0（{PR["name"]}市場應用）｜AI：{ai["ai"]}｜分析日期 {ai["analysis_date"]}（香港 UTC＋8）</p>')
    o.append(f'<p class="meta">{T["inherit_note"]}</p>')
    return o

def s1(m, S, T):
    o = [sec('一', '重點摘要')]
    for h, cls in T['sum_boxes']: o.append(box(h, cls))
    o.append(table(None, T['sum_rows'], widths=['13%', '87%'], kv=True))
    return o

def sjl(m, S, T):   # 選填：J Law 觀點（私人材料）同本市場有關嘅講法逐項對數據核實
    if not T.get('jlaw_html'): return []
    return [sec('', 'J Law 觀點對照及逐項核實'), T['jlaw_html']]

def s2(m, S, T):
    o = [sec('二', '資料截止時間、來源及缺項（V1.0 第三節）')]
    loc, hk, edt = utc_to(S['meta']['shot_utc'])
    hh, mm = map(int, PR['close'].split(':'))
    assert edt.strftime('%Y-%m-%d') > m.date or (edt.strftime('%Y-%m-%d') == m.date and (edt.hour, edt.minute) >= (hh, mm)), f'截圖時間 {loc} 未收市（{PR["close"]} {PR["tzname"]}）'
    ret, rhk = loc_hk(m.date, PR['close'])
    rows = [[f'{PR["name"]}交易日', f'{m.date}（星期{wd(m.date)}），正常交易時段收市；前一交易日 {m.pdate}（由 {m.lead} 日線得出）'],
            ['資料截止時間', f'截圖拍攝：{S["meta"]["shot_src"]}｜<b>{loc}</b>｜香港 {hk}（UTC＋8）。行情只取 {m.date} 或以前日線，之後數據一律唔用（V1.0 第三節第 9 條）。'],
            ['時段確認', f'收市為 {ret}（香港 {rhk}）；截圖時已收市，日 K 線為完整交易日。匯率、債息、期貨（如有）截圖時仍然交易緊，只當快照。圖面右下角 UTC 鐘係截圖時間，唔係 K 線時間。']]
    rows += _rows(T, 'src_rows')
    rows.append(['行情來源', f'網站 /api/ohlcv（Yahoo 日線，正常時段、不復權）：{"、".join(f"{t} {m.name(t)}" for t in sorted(m.sym))}；'
                 f'指數（只核對收市同升跌）：{"、".join(sorted(m.idx)) or "冇"}（Yahoo chart API）；均量口徑：50 日{"含" if m.basis == "incl" else "不含"}當日。'
                 + ('' if not m.meta.get('warn') else ' ⚠ ' + '；'.join(m.meta['warn']))])
    o.append(table(None, rows, widths=['16%', '84%'], kv=True))
    if T.get('verify_box'): o.append(sub('★ 本份核實動作')); o.append(box(T['verify_box']))
    ch, dv = [], []
    for t in YAHOO_OK:
        r = S['readings'].get(t) or {}
        if t not in m.sym: continue
        s = m[t]
        if r.get('c') is not None: chk(f'圖面收市 {t}', r['c'], s.c, 0.0051 if s.c < 1000 else 0.51)
        if r.get('pc') is not None: chk(f'圖面前收 {t}', r['pc'], s.pc, 0.0051 if s.c < 1000 else 0.51)
        if r.get('vol_m') is not None and s.v:
            diff = pct(r['vol_m'] * 1e6, s.v)
            dv.append(([f'{SHOT_OF[t]}', f'{r["vol_m"]:.2f}M', f'{s.v:,.0f}', P(diff), '用行情做分子同 50 日均量做分母（同一來源），圖面量只作對照' if abs(diff) > 0.5 else '吻合'], 'y' if abs(diff) > 3 else ''))
    for k, r in (S.get('index_readings') or {}).items():
        if k in m.idx and r.get('c') is not None:
            s = m.idx[k]; ok = chk(f'圖面收市 {k}', r['c'], s.c, 0.051)
            dv.append(([k, FI(r['c']), FI(s.c), N(r['c'] - s.c), '吻合' if ok else '指數收市同 Yahoo 唔一致：以 Yahoo 為準，查日期'], '' if ok else 'y'))
    o.append(sub('★ 缺項（逐項申報，V1.0 第三節第 5／6 條）'))
    gaps = [[a, b] for a, b in _rows(T, 'gaps')]
    gaps.append(['Yahoo 無行情嘅項目', '、'.join(CHART_ONLY + [x['shot'] for x in PR['index'] if x['shot'] not in m.idx]) +
                 '：只有截圖讀數（標「圖表讀數」），冇外部對照。亞洲截圖用 TradingView 完整圖表頁，圖上冇均線同 RSI；均線一律由行情重算。'])
    gaps.append(['市場廣度／資金流', PR['breadth_note']])
    o.append(table(['缺項', '說明同影響'], gaps, widths=['23%', '77%']))
    o.append(sub('★ 數據分歧（V1.0 第三節第 8 條：唔可以默默混用）'))
    o.append(table(['項目', '截圖讀數', '行情（Yahoo 日線）', '差距', '處理'], dv + _rows(T, 'divergence_extra'), widths=['10%', '13%', '17%', '10%', '50%'], align=['l', 'r', 'r', 'r', 'l']))
    return o

def _idx(m, S, T):
    o = [sub('主要指數（Yahoo 日線核對；指數成交量唔用）')]
    rows = []
    for x in PR['index']:
        k = x['shot']
        if k not in m.idx: rows.append(([x['name'], '—', '—', '—', 'Yahoo 未有當日指數，只有截圖讀數'], '')); continue
        s = m.idx[k]; ab = [n for n in (20, 50, 200) if s.n >= n and s.c > s.ma(n)]
        rows.append(([f'<b>{x["name"]}</b>', FI(s.pc), f'<b>{FI(s.c)}</b>', f'{N(s.chg)}<br>= {P(s.chgp)}',
                      f'高 {FI(s.h)}、低 {FI(s.l)}；近 5 日 {P(s.ret5)}、近 20 日 {P(s.ret20)}；高於 MA{"／".join(map(str, ab)) if ab else "（20／50／200 全部低於）"}。' + _g(T.get('idx_notes', {}), k, '')],
                     'g' if s.chg >= 0 else 'r'))
    for x in PR['core']:
        r = (S.get('index_readings') or {}).get(x['idx'])
        if x['idx'] not in m.idx and r and r.get('c') is not None:
            pc = r.get('pc'); ch = '' if pc is None else f'{N(r["c"] - pc)}<br>= {P(pct(r["c"], pc))}'
            rows.append(([f'<b>{x["idx_name"]}</b>', '—' if pc is None else FI(pc), f'<b>{FI(r["c"])}</b>', ch or '—', '圖表讀數（Yahoo 冇呢個指數）' + CHART + _g(T.get('idx_notes', {}), x['idx'], '')], ''))
    o.append(table(['指數', f'{md(m.pdate)} 收市', f'{md(m.date)} 收市', '變化', '說明'], rows, widths=['15%', '13%', '13%', '14%', '45%'], align=['l', 'r', 'r', 'l', 'l']))
    return o

def _cmp(m, S, T):
    o = [sub('主指數 ETF 比較表（V1.0 第四節指定格式）')]
    pd = md(m.pdate); td = md(m.date); rows = []
    for t in CORE:
        s = m[t]; c, p = s.candle(), s.candle(1)
        cls = 'g' if s.chg >= 0 else 'r'
        rows.append(([f'{SHOT_OF[t]} 收市', FD(s.pc, s.c), f'<b>{F(s.c)}</b>', f'{AR(s.chg, dp(s.c))}<br>= {P(s.chgp)}',
                      f'{m.name(t)}。開 {F(s.o)}（{"高" if s.o >= s.pc else "低"}開 {P(s.gapp)}）、高 {F(s.h)}、低 {F(s.l)}，振幅 {(s.h - s.l) / s.l * 100:.2f}%；由開市到收市 {P(s.ocp)}。' + _g(T.get('cmp_notes', {}), t, '')], cls))
        dchg = c['clv'] - p['clv']
        rows.append(([f'{SHOT_OF[t]} 燭身', f'{p["updown"]}{p["col"]}<br>CLV {p["clv"]:.2f}%', f'<b>{c["updown"]}{c["col"]}</b><br>CLV {c["clv"]:.2f}%',
                      f'CLV {"改善" if dchg > 0 else "惡化"}<br>{N(dchg)}pp',
                      f'實體 {c["body"]:.2f}%｜上影 {c["up"]:.2f}%｜下影 {c["lo"]:.2f}%｜開收 {P(c["oc"])}。' + _g(T.get('candle_notes', {}), t, '')], cls))
    o.append(table(['項目', f'上一交易日 {pd}', f'本交易日 {td}', '變化', '解讀'], rows, widths=['11%', '16%', '17%', '14%', '42%'], align=['l', 'r', 'r', 'l', 'l']))
    if T.get('sync_box'): o.append(box(T['sync_box']))
    return o

def _ma(m, S, T):
    o = [sub('均線位置、方向同趨勢結構（SMA，行情重算；截圖冇均線）')]
    def cell(s, k, slope=False):
        v = s.ma(k); p = pct(s.c, v)
        r = f'{FD(v, s.c)}<br>{"高於" if p >= 0 else "<b>低於</b>"} {abs(p):.2f}%'
        if slope: r += f'<br><b>{"向上" if v > s.ma(k, 1) else "向下"}</b>'
        return r
    rows = []
    for t in CORE:
        s = m[t]; ab = s.above(); v = [s.ma(k) for k in (10, 20, 50, 200)]
        arr = '完整多頭排列（MA10＞MA20＞MA50＞MA200）' if v == sorted(v, reverse=True) else ('完整空頭排列' if v == sorted(v) else '均線排列交錯')
        auto = f'{"四條全部高於" if len(ab) == 4 else ("四條全部低於" if not ab else "高於 MA" + "／".join(map(str, ab)))}；{arr}。'
        rows.append(([f'<b>{SHOT_OF[t]}</b>', F(s.c), cell(s, 10), cell(s, 20), cell(s, 50, True), cell(s, 200, True), auto + _g(T.get('ma_notes', {}), t, '')],
                     'g' if len(ab) >= 3 else ('r' if len(ab) <= 1 else '')))
    o.append(table(['ETF', '收市', 'MA10', 'MA20', 'MA50', 'MA200', '均線排列'], rows, widths=['8%', '10%', '13%', '13%', '13%', '13%', '30%'], align=['l', 'r', 'r', 'r', 'r', 'r', 'l']))
    if T.get('ma_box'): o.append(box(T['ma_box']))
    return o

def _levels(m, S, T):
    o = [sub('突破／跌破／收復／回測 ＋ 支撐阻力')]
    o.append(table(['標的', '今日事件', '第一／第二支撐', '第一／第二阻力'], T['events'], widths=['8%', '34%', '29%', '29%']))
    o.append(pre('阻力／支撐依據：均線價位為本份重算 SMA（' + CALC + '），會隨交易日更新；前高前低取自圖表日線；52 週高取自行情日線。'))
    o.append(sub('★★★ 關鍵價位 × 今日實際'))
    lr = []
    for i, L in enumerate(S['levels'], 1):
        t = L['t']; s = m.idx[t] if t in m.idx and t not in m.sym else m[t]
        key = L.get('key'); v = {'ma10': lambda: s.ma(10), 'ma20': lambda: s.ma(20), 'ma50': lambda: s.ma(50), 'ma200': lambda: s.ma(200),
                                 'h52': lambda: s.h52, 'l52': lambda: s.l52, 'h': lambda: s.h, 'l': lambda: s.l, 'pc': lambda: s.pc}[key]() if key else L['v']
        px = L.get('px', s.c); dpx, dln = lvl(px, v); sg = '▲' if px > v else '▼'
        lr.append(([str(i), L['name'], FD(v, px), F(px), f'{sg}{abs(dpx):.2f}% ／ {sg}{abs(dln):.2f}%<br>差 {FD(abs(px - v), px)} {U}', L['status']], L.get('cls', '')))
    o.append(table(['#', '價位', '數值', f'{md(m.date)} 實際', '÷現價 ／ ÷線價', '狀態同角色'], lr, widths=['4%', '16%', '10%', '10%', '20%', '40%'], align=['c', 'l', 'r', 'r', 'r', 'l']))
    if T.get('levels_box'): o.append(box(T['levels_box']))
    return o

def s3(m, S, T):
    names = '／'.join(f'{SHOT_OF[t]}' for t in CORE)
    return ([sec('三', f'主要指數及 {names} 分析、前日比較'), pre('均線一律為 SMA（行情日線重算，' + CALC + '）。距離以收市價計。ETF 代表指數做量價分析（指數本身冇可靠成交量）。')]
            + _idx(m, S, T) + _cmp(m, S, T) + _ma(m, S, T) + _levels(m, S, T))

def s4(m, S, T):
    o = [sec('四', '成交量、波動指數與市場廣度'), sub('4.1　成交量（V1.0 第五節：口徑逐項聲明）')]
    o.append(box(f'<b class="navy">口徑聲明（必須先讀）：</b>① 均線一律係 <b>SMA</b>，由行情日線重算。② 均量基準係 <b>50 日</b>（{"含" if m.basis == "incl" else "不含"}當日），冇用 20 日代替。③ 下表「當日量÷50 日均量」<b>唔係 RVOL20</b>。④ 分子分母同一來源（Yahoo 日線；圖面成交量只作對照）。⑤ 量用主指數 ETF 計，唔用指數本身。'))
    vr = []
    for t in CORE:
        s = m[t]; r = s.vr(); rp = s.vr(1)
        vr.append(([f'<b>{SHOT_OF[t]}</b>', f'{s.v:,.0f}', f'{s.pv:,.0f}', f'{s.v50():,.0f}', f'<b>{r:.2f}%</b>',
                    f'{"升" if s.chg >= 0 else "跌"}日 {P(s.chgp)}，量{"多" if s.v > s.pv else "少"}過前日 {abs(pct(s.v, s.pv)):.2f}%，{"高於" if r > 100 else "低於"} 50 日均量（前日 {rp:.2f}%）。' + _g(T.get('vol_notes', {}), t, '')],
                   'g' if (r > 100 and s.chg >= 0) or (r < 100 and s.chg < 0) else 'r'))
    o.append(table(['ETF', '今日成交量', '前日成交量', '50 日均量', '當日量÷50 日均量', '判讀'], vr, widths=['8%', '14%', '14%', '14%', '15%', '35%'], align=['l', 'r', 'r', 'r', 'r', 'l']))
    if T.get('vol_box'): o.append(box(T['vol_box']))
    o.append(sub('4.2　派發日判定（V1.0 第五節：先列定義）'))
    o.append(f'<p>採用定義：<b>派發日 ＝ 下跌日（或微升日，升幅 ≤ 0.2%），且 成交量 ＞ 前一日 且 ＞ 當日滾動 50 日均量（{"含" if m.basis == "incl" else "不含"}當日）</b>。窗口：近 25 個交易日（V1.0 冇定義窗口，只作示範計數）。用主指數 ETF 成交量計。{_g(T, "dist_def_note")}</p>')
    dr, dl = [], []
    for t in CORE:
        s = m[t]; c1, c2 = s.v > s.pv, s.vr() > 100; st, mi = s.dist_days()
        dr.append(([SHOT_OF[t], f'{"升" if s.chg >= 0 else "跌"} {P(s.chgp)}', f'{"是" if c1 else "否"}（{P(pct(s.v, s.pv))}）', f'{"是" if c2 else "否"}（{s.vr():.2f}%）',
                    ('<b>今日係派發日</b>' if (s.chgp <= 0.2 and c1 and c2) else '<b>唔構成派發日</b>')], ''))
        dl.append(([SHOT_OF[t], '、'.join(x[5:] for x in st) or '—', f'<b>{len(st)}</b>', f'{len(mi)}'], ''))
    o.append(table(['ETF', '方向', '量 ＞ 前一日？', '量 ＞ 50 日均量？', '今日判定'], dr, widths=['9%', '17%', '22%', '22%', '30%']))
    o.append(table(['ETF', '近 25 個交易日派發日（strict：下跌日）', '個數', '含微升日個數'], dl, widths=['9%', '63%', '12%', '16%'], align=['l', 'l', 'c', 'c']))
    if T.get('dist_box'): o.append(box(T['dist_box']))
    # 波動指數
    v = S.get('vol') or {}
    if PR.get('vol') and v.get('c') is not None:
        o.append(sub(f'4.3　{PR["vol"]["name"]}（圖表讀數，Yahoo 無對照）'))
        rows = [(['收市', '—' if v.get('pc') is None else f'{v["pc"]:.2f}', f'{v["c"]:.2f}', '—' if v.get('pc') is None else f'{N(v["c"] - v["pc"])} ＝ {P(pct(v["c"], v["pc"]))}', _g(T, 'vol_close_note') + CHART], '')]
        if v.get('h') is not None and v.get('l') is not None:
            rows.append((['日內', '—', f'開 {v.get("o", 0):.2f}｜高 {v["h"]:.2f}｜低 {v["l"]:.2f}', f'CLV {clv(v["c"], v["h"], v["l"]):.2f}%', _g(T, 'vol_range_note')], ''))
        if v.get('hist'): rows.append((['近日走勢', '—', ' → '.join(f'{x:.2f}' for x in v['hist']), '—', _g(T, 'vol_hist_note')], ''))
        o.append(table(['項目', md(m.pdate), md(m.date), '變化', '解讀'], rows, widths=['12%', '10%', '24%', '18%', '36%'], align=['l', 'r', 'r', 'r', 'l']))
    else:
        o.append(sub('4.3　波動指數'))
        o.append(box('本市場冇可用嘅波動指數截圖' + ('（截圖讀唔到）' if PR.get('vol') else '（日經 VI／VKOSPI 喺 TradingView 搵唔到，Yahoo 都冇）') + '：以下用主指數 ETF 振幅同燭身代替觀察波動，唔當作波動指數讀數。'))
    o.append(f'<p>⚠ 按 V1.0 第六節：<b>波動指數下跌唔可以單獨證明市場全面轉強</b>。{_g(T, "vix_para")}</p>')
    # 廣度
    o.append(sub('4.4　市場廣度（涵蓋範圍、日期、數值逐項列明）'))
    br = []
    for b in S['breadth']:
        if b.get('cur') is None: br.append(([b['name'], b['scope'], b.get('date', '—'), '—', '— 缺 —', b.get('note', '全程缺。')], '')); continue
        d_ = b['cur'] - b['prev'] if b.get('prev') is not None else None
        br.append(([b['name'], b['scope'], b['date'], '—' if d_ is None else f'{b["prev"]:,.2f}', f'<b>{b["cur"]:,.2f}</b>',
                    ('' if d_ is None else f'{AR(d_, 2)}（{P(pct(b["cur"], b["prev"]))}）。') + b.get('note', '')], ('g' if d_ and d_ > 0 else 'r' if d_ and d_ < 0 else '')))
    o.append(table(['指標', '涵蓋範圍', '日期', '前日', '本日', '變化同判讀'], br, widths=['17%', '17%', '10%', '10%', '10%', '36%'], align=['l', 'l', 'c', 'r', 'r', 'l']))
    if T.get('breadth_box'): o.append(box(T['breadth_box']))
    o.append(sub('V1.0 第六節要求逐條回答：')); o.append(table(['問題', '答案'], T['breadth_qa'], widths=['27%', '73%']))
    if T.get('breadth_limits'): o.append(box(T['breadth_limits']))
    if S.get('macro'):
        o.append(sub('4.5　宏觀快照（匯率、債息、期貨：圖表讀數；截圖時仍交易緊只當快照）'))
        mr = [([x['name'], f'{x["c"]:,.3f}', x.get('chg', '—'), '仍交易緊（快照）' if x.get('open', True) else '已收', x.get('note', '')], '') for x in S['macro']]
        o.append(table(['項目', '讀數', '圖面升跌', '狀態', '備註'], mr, widths=['18%', '12%', '16%', '16%', '38%'], align=['l', 'r', 'r', 'l', 'l']))
    return o

def s5(m, S, T):
    o = [sec('五', '板塊／權重股強弱與輪動')]
    sp = m[m.lead]
    o.append(pre(f'相對 {SHOT_OF[m.lead]} ＝ 當日% 減 {SHOT_OF[m.lead]}（{m.name(m.lead)}）當日%（{P(sp.chgp)}）。近 5／20 日表現由行情日線重算（{CALC}）。{SHOT_OF[m.lead]} 同期：近 5 日 {P(sp.ret5)}、近 20 日 {P(sp.ret20)}。'))
    rows = []
    sect = [(t, nm) for t, nm in SECTORS if t in m.sym]
    for t, nm in sorted(sect, key=lambda x: -m[x[0]].chgp):
        s = m[t]; ab = s.above()
        pos = '★ 四條全高' if len(ab) == 4 else '<b>四條全低</b>' if not ab else '高於 ' + '／'.join(map(str, ab))
        cls = 'g' if s.chgp >= sp.chgp and len(ab) >= 3 else ('r' if len(ab) <= 1 else '')
        rows.append(([f'<b>{SHOT_OF[t]} {nm}</b>', P(s.chgp), f'{N(s.chgp - sp.chgp)}pp', F(s.c), P(s.ret5), P(s.ret20), f'{s.vr():.1f}%', P(pct(s.c, s.h52)), pos], cls))
    o.append(table(['板塊／權重股', '當日%', f'相對 {SHOT_OF[m.lead]}', '收市', '近 5 日', '近 20 日', '量÷50均', '距 52 週高', '主要均線位置'], rows,
                   widths=['20%', '8%', '9%', '9%', '8%', '8%', '8%', '9%', '21%'], align=['l', 'r', 'r', 'r', 'r', 'r', 'r', 'r', 'l']))
    ch = [m[t].chgp for t, _ in sect]; up = sum(1 for c in ch if c > 0)
    beat = [SHOT_OF[t] for t, _ in sect if m[t].chgp > sp.chgp]
    b5 = sum(1 for t, _ in sect if m[t].ret5 > sp.ret5)
    o.append(pre(f'{len(sect)} 個板塊／權重股：收升 {up} 個、收跌 {len(ch) - up} 個（簡單平均 {P(sum(ch) / len(ch))}，{CALC}）；跑贏 {SHOT_OF[m.lead]} 當日：{"、".join(beat) or "無"}；近 5 日跑贏：{b5} 個。52 週高取自行情日線（不復權）。'))
    if T.get('sector_box'): o.append(box(T['sector_box']))
    o.append(sub('V1.0 第七節要求逐條回答')); o.append(table(['問題', '答案'], T['sector_qa'], widths=['27%', '73%']))
    o.append(pre('⚠ 按 V1.0 第七節：冇可核實嘅資金流或 ETF 申贖數據，全份不用「資金淨流入／淨流出」；只描述價格強弱同輪動跡象。'))
    if T.get('sector_flag'): o.append(sub('★ 需要標記嘅板塊特徵')); o.append(f'<p>{T["sector_flag"]}</p>')
    return o

def s6(m, S, T):
    o = [sec('六', '過去 5 個交易日催化劑及未來一星期事件')]
    if T.get('catalysts_box'): o.append(box(T['catalysts_box']))
    o.append(sub('6.1　過去 5 個交易日'))
    o.append(table(['事件日期', '事件及來源', '已知市場反應', '可能影響', '仍待確認'], T['past_events'], widths=['10%', '37%', '21%', '18%', '14%']))
    if T.get('past_note'): o.append(pre(T['past_note']))
    o.append(sub('6.2　未來一星期已確認事件'))
    o.append(pre(f'時間：當地時間（{PR["tzname"]}）或註明 ET（美東）者自動換算香港時間。' + _g(T, 'next_week_note')))
    nw = []
    for e in T['next_week']:                       # (事件, 日期, 'HH:MM'／'ET HH:MM'／None, 預期／前值, 關注點[, cls])
        name, d_, hm, exp, why = e[:5]; cls = e[5] if len(e) > 5 else ''
        if hm:
            tz = 'ET' if str(hm).startswith('ET') else None
            lo, hk = loc_hk(d_, str(hm).replace('ET', '').strip(), tz); a, b = f'{md(d_)}（{wd(d_)}）{lo}', hk
        else: a, b = f'{md(d_)}（{wd(d_)}）時間未核實', '時間未核實'
        nw.append(([name, a, b, exp, why], cls))
    o.append(table(['事件', '當地時間', '香港時間', '預期／前值', '市場關注點'], nw, widths=['22%', '15%', '15%', '21%', '27%']))
    if T.get('next_week_foot'): o.append(pre(T['next_week_foot']))
    return o

def s7(m, S, T): return [sec('七', '歷史比較'), T['history_html']]

def s8(m, S, T):
    o = [sec('八', '市況總結與三個後續情境'), sub('8.1　短線／中期／長期分開判斷')]
    o.append(table(['時間維度', '判斷', '支持證據', '反對證據'], T['regime_rows'], widths=['12%', '17%', '36%', '35%']))
    o.append(box(T['regime_box']))
    o.append(sub(f'8.2　三個情境（觀察條件為圖表價位，唔係承襲門檻）＋ {md(m.date)} 結算'))
    o.append(table(['情境', '觀察條件', '觸發／失效條件', f'{md(m.date)} 結算'], T['scenario_rows'], widths=['12%', '38%', '25%', '25%']))
    o.append(sub('8.3　每個情境嘅觀察條件、觸發、失效同影響'))
    o.append(table(['情境', '要睇嘅價格／量能／廣度', '觸發條件', '失效條件', '對後續判斷嘅影響'], T['scenario_detail'], widths=['6%', '37%', '17%', '17%', '23%']))
    o.append(pre('★ 關鍵價位來源：取自今日圖表同重算 SMA（' + CALC + '），均線價位會隨交易日更新。按 V1.0 第九節：不提供情境機率或勝率，不自行修改任何門檻。'))
    return o

def s9(m, S, T):
    o = [sec('九', '下一交易日需追蹤及核實嘅事項')]
    o.append(table(['#', '追蹤項目', '今日數值', '點解要睇'], T['next_rows'], widths=['4%', '27%', '25%', '44%'], align=['c', 'l', 'l', 'l']))
    o.append(sub('★ 需要核實（本份不能確認）')); o.append(table(['項目', '狀態'], T['verify_rows'], widths=['32%', '68%']))
    if T.get('open_q'): o.append(sub('★ 待裁問題（本份專用）')); o.append(table(['編號', '內容', '今日狀態'], T['open_q'], widths=['8%', '37%', '55%']))
    if T.get('action_rows'): o.append(sub('★ 條件式行動清單（非買賣建議）')); o.append(table(['#', '項目', '條件／做法'], T['action_rows'], widths=['4%', '22%', '74%'], align=['c', 'l', 'l']))
    o.append('<p class="small">分析框架與個人判讀，用於研究交流，不構成投資建議。</p>')
    return o

def tail(m, S, T):
    a = S['meta']
    o = [sec('', '可直接轉貼嘅簡短摘要'), box(T['group_summary']), sec('', '報告註明')]
    rows = [['分析框架', f'JW 大盤分析指令｜共用補充版（{PR["name"]}市場應用）'], ['AI', a['ai_note']], ['模式', a['mode']],
            ['分析日期', f'{a["analysis_date"]}（香港 UTC＋8）｜{PR["name"]}交易日 {m.date}'], ['外部來源', a['sources']],
            ['免責', '分析框架與個人判讀，用於研究交流，<b>不構成投資建議</b>。價位隨交易日更新。不提供勝率或發生機率，亦不把市況分類當作買賣許可。']]
    o.append(table(None, rows, widths=['14%', '86%'], kv=True))
    return o

def build_html(m, S, T):
    parts = head(m, S, T) + s1(m, S, T) + sjl(m, S, T) + s2(m, S, T) + s3(m, S, T) + s4(m, S, T) + s5(m, S, T) + s6(m, S, T) + s7(m, S, T) + s8(m, S, T) + s9(m, S, T) + tail(m, S, T)
    return '\n'.join(parts)
