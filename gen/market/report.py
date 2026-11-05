"""report.py — 大盤報告通用版面（V1.0 第十節九節＋摘要＋註明）。
build_html(m, S, T)：m＝mlib.Market；S＝work.spec(m)（圖表讀數／價位清單／後設）；T＝work.texts(m, S)（敘述 html／表格行）。
自動計算嘅表：比較表、燭身、均線、價位距離、盤後、成交量、派發日、板塊、VIX、廣度、宏觀；其餘敘述由 T 提供。
T 欄位見 template_work.py；缺嘅可選欄位會略過，必填欄位缺或含 'TODO' 由 build.py 擋住。"""
from mlib import *

def _g(T, k, default=''): return T.get(k, default)
def _rows(T, k): return T.get(k) or []

def head(m, S, T):
    d = m.date
    o = [f'<h1>美股大盤分析　{d}（{wd(d)}）收市</h1>']
    ai = S['meta']
    o.append(f'<p class="meta">分析框架：JW 大盤分析指令｜共用補充版 V1.0｜AI：{ai["ai"]}｜分析日期 {ai["analysis_date"]}（香港 UTC＋8）</p>')
    o.append(f'<p class="meta">{T["inherit_note"]}</p>')
    return o

def s1(m, S, T):
    o = [sec('一', '重點摘要')]
    for h, cls in T['sum_boxes']: o.append(box(h, cls))
    o.append(table(None, T['sum_rows'], widths=['13%', '87%'], kv=True))
    return o

def sjl(m, S, T):   # 選填：J Law 觀點（用戶提供嘅 J Law Update PDF／影片）逐項對數據核實
    if not T.get('jlaw_html'): return []
    return [sec('', 'J Law 觀點對照及逐項核實'), T['jlaw_html']]

def s2(m, S, T):
    o = [sec('二', '資料截止時間、來源及缺項（V1.0 第三節）')]
    et, hk, edt = utc_to(S['meta']['shot_utc'])
    assert edt.strftime('%Y-%m-%d') >= m.date and (edt.strftime('%Y-%m-%d') > m.date or edt.hour >= 16), f'截圖時間 {et} 未收市（16:00 ET）'
    ret, _ = et_hk(m.date, '16:00')
    rows = [['美國交易日', f'{m.date}（星期{wd(m.date)}），正常交易時段收市；前一交易日 {m.pdate}（由 SPY 日線得出）'],
            ['資料截止時間', f'截圖拍攝：{S["meta"]["shot_src"]}｜<b>{et}</b>｜香港 {hk}（UTC＋8）。行情只取 {m.date} 或以前日線，之後數據一律唔用（V1.0 第三節第 9 條）。'],
            ['時段確認', f'收市為 {ret}；截圖時已收市，所有日 K 線為完整交易日。盤後價只記錄，唔參與判定。DXY、US10Y、GC1! 日線截圖時通常未收（有倒數計時），只當快照。圖面右下角 UTC 鐘係截圖時間，唔係 K 線時間。']]
    rows += _rows(T, 'src_rows')
    rows.append(['行情來源', f'網站 /api/ohlcv（Yahoo 日線，正常時段、不復權）：{"、".join(sorted(m.sym))}；均量口徑：50 日{"含" if m.basis == "incl" else "不含"}當日。'
                 + ('' if not m.meta.get('warn') else ' ⚠ ' + '；'.join(m.meta['warn']))])
    o.append(table(None, rows, widths=['16%', '84%'], kv=True))
    if T.get('verify_box'): o.append(sub('★ 本份核實動作')); o.append(box(T['verify_box']))
    # 自動：圖面讀數 vs 行情
    ch, dv = [], []
    for t in INDEXES + [x for x, _ in SECTORS]:
        r = S['readings'].get(t) or {}; s = m[t]
        if 'c' in r:
            ok = chk(f'圖面收市 {t}', r['c'], s.c, 0.0051)
            ch.append((t, r['c'], s.c, ok))
            if 'pc' in r: chk(f'圖面前收 {t}', r['pc'], s.pc, 0.0051)
        if 'ma' in r:
            for k, v in r['ma'].items(): chk(f'圖面 MA{k} {t}', v, s.ma(int(k)), 0.0051)
        if 'vol_m' in r:
            diff = pct(r['vol_m'] * 1e6, s.v)
            dv.append(([t, f'{r["vol_m"]:.2f}M', f'{s.v:,.0f}', f'{diff:+.2f}%', '用行情做分子同 50 日均量做分母（同一來源），圖面量只作對照' if abs(diff) > 0.5 else '吻合'], 'y' if abs(diff) > 3 else ''))
    o.append(sub('★ 缺項（逐項申報，V1.0 第三節第 5／6 條）'))
    gaps = [[a, b] for a, b in _rows(T, 'gaps')]
    gaps.append(['Yahoo 無行情嘅項目', '、'.join(CHART_ONLY) + '：只有截圖讀數（標「圖表讀數」），冇外部對照；SOX 無成交量／均線可用，量能判定只用 SPY／QQQ／IWM／板塊 ETF'
                 + ('；SMH 可作半導體 ETF 並列對照' if 'SMH' in m.sym else '')])
    o.append(table(['缺項', '說明同影響'], gaps, widths=['23%', '77%']))
    o.append(sub('★ 數據分歧（V1.0 第三節第 8 條：唔可以默默混用）'))
    o.append(table(['項目', '截圖讀數', '行情（Yahoo 日線）', '差距', '處理'], dv + _rows(T, 'divergence_extra'), widths=['10%', '13%', '17%', '10%', '50%'], align=['l', 'r', 'r', 'r', 'l']))
    return o

def _cmp(m, S, T):
    o = [sub('比較表（V1.0 第四節指定格式）')]
    pd = md(m.pdate); td = md(m.date); rows = []
    for t in INDEXES:
        s = m[t]; c, p = s.candle(), s.candle(1)
        cls = 'g' if s.chg >= 0 else 'r'
        rows.append(([f'{t} 收市', f'{s.pc:.4f}', f'<b>{s.c:.4f}</b>', f'{AR(s.chg)}<br>= {P(s.chgp)}',
                      f'開 {s.o:.2f}（{"高" if s.o >= s.pc else "低"}開 {P(s.gapp)}，{N(s.o - s.pc, 2)} 蚊）、高 {s.h:.2f}、低 {s.l:.2f}，振幅 {(s.h - s.l) / s.l * 100:.4f}%；由開市到收市 {P(s.ocp)}。' + _g(T.get('cmp_notes', {}), t, '')], cls))
        dchg = c['clv'] - p['clv']
        rows.append(([f'{t} 燭身', f'{p["updown"]}{p["col"]}<br>CLV {p["clv"]:.4f}%', f'<b>{c["updown"]}{c["col"]}</b><br>CLV {c["clv"]:.4f}%',
                      f'CLV {"改善" if dchg > 0 else "惡化"}<br>{N(dchg)}pp',
                      f'實體 {c["body"]:.4f}%｜上影 {c["up"]:.4f}%｜下影 {c["lo"]:.4f}%｜開收 {P(c["oc"])}。' + _g(T.get('candle_notes', {}), t, '')], cls))
    o.append(table(['項目', f'上一交易日 {pd}', f'本交易日 {td}', '變化', '解讀'], rows, widths=['11%', '16%', '17%', '14%', '42%'], align=['l', 'r', 'r', 'l', 'l']))
    if T.get('sync_box'): o.append(box(T['sync_box']))
    return o

def _ma(m, S, T):
    o = [sub('均線位置、方向同趨勢結構（SMA，行情重算）')]
    def cell(s, k, slope=False):
        v = s.ma(k); p = pct(s.c, v)
        r = f'{v:.4f}<br>{"高於" if p >= 0 else "<b>低於</b>"} {abs(p):.4f}%'
        if slope: r += f'<br><b>{"向上" if v > s.ma(k, 1) else "向下"}</b>'
        return r
    rows = []
    for t in INDEXES:
        s = m[t]; ab = s.above(); v = [s.ma(k) for k in (10, 20, 50, 200)]
        arr = '完整多頭排列（MA10＞MA20＞MA50＞MA200）' if v == sorted(v, reverse=True) else ('完整空頭排列' if v == sorted(v) else '均線排列交錯')
        auto = f'{"四條全部高於" if len(ab) == 4 else ("四條全部低於" if not ab else "高於 MA" + "／".join(map(str, ab)))}；{arr}。'
        rows.append(([f'<b>{t}</b>', f'{s.c:.4f}', cell(s, 10), cell(s, 20), cell(s, 50, True), cell(s, 200, True), auto + _g(T.get('ma_notes', {}), t, '')],
                     'g' if len(ab) >= 3 else ('r' if len(ab) <= 1 else '')))
    o.append(table(['指數', '收市', 'MA10', 'MA20', 'MA50', 'MA200', '均線排列'], rows, widths=['8%', '10%', '13%', '13%', '13%', '13%', '30%'], align=['l', 'r', 'r', 'r', 'r', 'r', 'l']))
    if T.get('ma_box'): o.append(box(T['ma_box']))
    return o

def _levels(m, S, T):
    o = [sub('突破／跌破／收復／回測 ＋ 支撐阻力')]
    o.append(table(['指數', '今日事件', '第一／第二支撐', '第一／第二阻力'], T['events'], widths=['8%', '34%', '29%', '29%']))
    o.append(pre('阻力／支撐依據：均線價位為本份重算 SMA（' + CALC + '），會隨交易日更新；前高前低取自圖表日線；52 週高取自行情日線。'))
    o.append(sub('★★★ 關鍵價位 × 今日實際'))
    lr = []
    for i, L in enumerate(S['levels'], 1):
        t = L['t']; s = m[t]
        key = L.get('key'); v = {'ma10': lambda: s.ma(10), 'ma20': lambda: s.ma(20), 'ma50': lambda: s.ma(50), 'ma200': lambda: s.ma(200),
                                 'h52': lambda: s.h52, 'h': lambda: s.h, 'l': lambda: s.l, 'pc': lambda: s.pc}[key]() if key else L['v']
        px = L.get('px', s.c); dpx, dln = lvl(px, v); sg = '▲' if px > v else '▼'
        lr.append(([str(i), L['name'], f'{v:.4f}', f'{px:.4f}', f'{sg}{abs(dpx):.4f}% ／ {sg}{abs(dln):.4f}%<br>差 {abs(px - v):.4f} 蚊', L['status']], L.get('cls', '')))
    o.append(table(['#', '價位', '數值', f'{md(m.date)} 實際', '÷現價 ／ ÷線價', '狀態同角色'], lr, widths=['4%', '16%', '10%', '10%', '20%', '40%'], align=['c', 'l', 'r', 'r', 'r', 'l']))
    if T.get('levels_box'): o.append(box(T['levels_box']))
    # 盤後
    pr = []
    for t in INDEXES + [x for x, _ in SECTORS]:
        r = S['readings'].get(t) or {}
        if r.get('post') is not None:
            c = m[t].c; dd = r['post'] - c
            pr.append(([t, f'{c:.4f}', f'{r["post"]:.4f}', N(dd), P(pct(r['post'], c)), _g(T.get('post_notes', {}), t, '—')], ''))
        elif t in S.get('post_missing', []):
            pr.append(([t, f'{m[t].c:.4f}', '—', '—', '—', '圖面冇顯示盤後價，標缺，唔估算'], ''))
    if pr:
        o.append(sub('盤後價逐項記錄（V1.0 第三節第 3 條：區分時段，唔參與判定）'))
        o.append(table(['標的', '正常時段收市', f'盤後（{S["meta"].get("post_time", "截圖時")}）', '差額', '盤後變動%', '備註'], pr, widths=['9%', '15%', '15%', '11%', '13%', '37%'], align=['l', 'r', 'r', 'r', 'r', 'l']))
        if T.get('post_note'): o.append(pre(T['post_note']))
    return o

def s3(m, S, T):
    return [sec('三', 'SPY／QQQ／IWM 分析及前日比較'), pre('均線一律為 SMA（行情日線重算，' + CALC + '）。距離以收市價計。')] + _cmp(m, S, T) + _ma(m, S, T) + _levels(m, S, T)

def s4(m, S, T):
    o = [sec('四', '成交量、VIX 與市場廣度'), sub('4.1　成交量（V1.0 第五節：口徑逐項聲明）')]
    o.append(box(f'<b class="navy">口徑聲明（必須先讀）：</b>① 均線一律係 <b>SMA</b>，由行情日線重算，唔係圖示 MA。② 均量基準係 <b>50 日</b>（{"含" if m.basis == "incl" else "不含"}當日），冇用 20 日代替。③ 下表「當日量÷50 日均量」<b>唔係 RVOL20</b>。④ 分子分母同一來源（圖面成交量只作對照，見第二節）。⑤ 所有 K 線為完整交易日，唔涉及未收盤量比較。'))
    vr = []
    for t in INDEXES:
        s = m[t]; r = s.vr(); rp = s.vr(1)
        vr.append(([f'<b>{t}</b>', f'{s.v:,.0f}', f'{s.pv:,.0f}', f'{s.v50():,.0f}', f'<b>{r:.2f}%</b>',
                    f'{"升" if s.chg >= 0 else "跌"}日 {P(s.chgp)}，量{"多" if s.v > s.pv else "少"}過前日 {abs(pct(s.v, s.pv)):.4f}%，{"高於" if r > 100 else "低於"} 50 日均量（前日 {rp:.2f}%）。' + _g(T.get('vol_notes', {}), t, '')],
                   'g' if (r > 100 and s.chg >= 0) or (r < 100 and s.chg < 0) else 'r'))
    o.append(table(['標的', '今日成交量', '前日成交量', '50 日均量', '當日量÷50 日均量', '判讀'], vr, widths=['8%', '14%', '14%', '14%', '15%', '35%'], align=['l', 'r', 'r', 'r', 'r', 'l']))
    if T.get('vol_box'): o.append(box(T['vol_box']))
    o.append(sub('4.2　派發日判定（V1.0 第五節：先列定義）'))
    o.append(f'<p>採用定義：<b>派發日 ＝ 下跌日（或微升日，升幅 ≤ 0.2%），且 成交量 ＞ 前一日 且 ＞ 當日滾動 50 日均量（{"含" if m.basis == "incl" else "不含"}當日）</b>。窗口：近 25 個交易日（V1.0 冇定義窗口，只作示範計數）。{_g(T, "dist_def_note")}</p>')
    dr, dl = [], []
    for t in INDEXES:
        s = m[t]; c1, c2 = s.v > s.pv, s.vr() > 100; st, mi = s.dist_days()
        dr.append(([t, f'{"升" if s.chg >= 0 else "跌"} {P(s.chgp)}', f'{"是" if c1 else "否"}（{P(pct(s.v, s.pv))}）', f'{"是" if c2 else "否"}（{s.vr():.2f}%）',
                    ('<b>今日係派發日</b>' if (s.chgp <= 0.2 and c1 and c2) else '<b>唔構成派發日</b>')], ''))
        dl.append(([t, '、'.join(x[5:] for x in st) or '—', f'<b>{len(st)}</b>', f'{len(mi)}'], ''))
    o.append(table(['標的', '方向', '量 ＞ 前一日？', '量 ＞ 50 日均量？', '今日判定'], dr, widths=['9%', '17%', '22%', '22%', '30%']))
    o.append(table(['標的', '近 25 個交易日派發日（strict：下跌日）', '個數', '含微升日個數'], dl, widths=['9%', '63%', '12%', '16%'], align=['l', 'l', 'c', 'c']))
    if T.get('dist_box'): o.append(box(T['dist_box']))
    # VIX
    o.append(sub('4.3　VIX（圖表讀數，Yahoo 無對照）'))
    v = S['vix']; vc = v['c'] - v['pc']; vcl = clv(v['c'], v['h'], v['l'])
    chk('VIX 前收＋升跌＝收', v['pc'] + v['chg'], v['c'], 0.0051) if 'chg' in v else None
    vrows = [(['VIX 收市', f'{v["pc"]:.4f}', f'{v["c"]:.4f}', f'{N(vc)} ＝ {P(pct(v["c"], v["pc"]))}', _g(T, 'vix_close_note') + CHART], ''),
             (['VIX 日內', '—', f'開 {v["o"]:.2f}｜高 {v["h"]:.2f}｜低 {v["l"]:.2f}', f'CLV {vcl:.4f}%', _g(T, 'vix_range_note')], '')]
    if v.get('h52'): vrows.append((['距 52 週高', '—', f'{P(pct(v["c"], v["h52"]))}（52 週高 {v["h52"]:.2f}）', '—', _g(T, 'vix_h52_note')], ''))
    if v.get('hist'): vrows.append((['近日走勢', '—', ' → '.join(f'{x:.2f}' for x in v['hist']), '—', _g(T, 'vix_hist_note')], ''))
    o.append(table(['項目', md(m.pdate), md(m.date), '變化', '解讀'], vrows, widths=['12%', '10%', '24%', '18%', '36%'], align=['l', 'r', 'r', 'r', 'l']))
    o.append(f'<p>⚠ 按 V1.0 第六節：<b>VIX 下跌唔可以單獨證明市場全面轉強</b>。{_g(T, "vix_para")}</p>')
    # 廣度
    o.append(sub('4.4　市場廣度（涵蓋範圍、日期、數值逐項列明）'))
    br = []
    for b in S['breadth']:
        if b.get('cur') is None: br.append(([b['name'], b['scope'], b.get('date', '—'), '—', '— 缺 —', b.get('note', '全程缺。')], '')); continue
        d_ = b['cur'] - b['prev'] if b.get('prev') is not None else None
        br.append(([b['name'], b['scope'], b['date'], '—' if d_ is None else f'{b["prev"]:.2f}', f'<b>{b["cur"]:.2f}</b>',
                    ('' if d_ is None else f'{AR(d_, 2)} 點（{P(pct(b["cur"], b["prev"]))}）。') + b.get('note', '')], ('g' if d_ and d_ > 0 else 'r' if d_ and d_ < 0 else '')))
    o.append(table(['指標', '涵蓋範圍', '日期', '前日圖面', '本日圖面', '變化同判讀'], br, widths=['17%', '17%', '10%', '10%', '10%', '36%'], align=['l', 'l', 'c', 'r', 'r', 'l']))
    if T.get('breadth_box'): o.append(box(T['breadth_box']))
    o.append(sub('V1.0 第六節要求逐條回答：')); o.append(table(['問題', '答案'], T['breadth_qa'], widths=['27%', '73%']))
    if T.get('breadth_limits'): o.append(box(T['breadth_limits']))
    # 宏觀
    if S.get('macro'):
        o.append(sub('4.5　宏觀快照（DXY、US10Y、GC1!：圖表讀數；日線未收只當快照）'))
        mr = [([x['name'], f'{x["c"]:.3f}', x.get('chg', '—'), '日線未收（倒數中）' if x.get('open', True) else '日線已收', x.get('note', '')], '') for x in S['macro']]
        o.append(table(['項目', '讀數', '圖面升跌', '狀態', '備註'], mr, widths=['14%', '12%', '16%', '18%', '40%'], align=['l', 'r', 'r', 'l', 'l']))
    return o

def s5(m, S, T):
    o = [sec('五', '板塊強弱與輪動')]
    sp = m['SPY']
    o.append(pre(f'相對 SPY ＝ 板塊當日% 減 SPY 當日%（{P(sp.chgp)}）。近 5／20 日表現由行情日線重算（{CALC}）。SPY 同期：近 5 日 {P(sp.ret5)}、近 20 日 {P(sp.ret20)}。'))
    rows = []
    order = sorted(SECTORS, key=lambda x: -m[x[0]].chgp)
    for t, nm in order:
        s = m[t]; ab = s.above(); rs = (S['readings'].get(t) or {}).get('rsi')
        pos = '★ 四條全高' if len(ab) == 4 else '<b>四條全低</b>' if not ab else '高於 ' + '／'.join(map(str, ab))
        cls = 'g' if s.chgp >= sp.chgp and len(ab) >= 3 else ('r' if len(ab) <= 1 else '')
        rows.append(([f'<b>{t} {nm}</b>', P(s.chgp), f'{N(s.chgp - sp.chgp)}pp', f'{s.c:.4f}', P(s.ret5), P(s.ret20), f'{s.vr():.1f}%', '—' if rs is None else f'{rs:.2f}', P(pct(s.c, s.h52), 2), pos], cls))
    x = S.get('sox')
    if x:
        xc = pct(x['c'], x['pc'])
        rows.append((['<b>SOX 半導體</b>', P(xc), f'{N(xc - sp.chgp)}pp', f'{x["c"]:,.2f}', P(x['ret5']) + '（圖面計算）' if x.get('ret5') is not None else '—', '—', '—（指數無量）', '—' if x.get('rsi') is None else f'{x["rsi"]:.2f}', '—', '圖無均線，無法判定'], ''))
    o.append(table(['板塊', '當日%', '相對 SPY', '收市', '近 5 日', '近 20 日', '量÷50均', 'RSI', '距 52 週高', '主要均線位置'], rows,
                   widths=['12%', '8%', '9%', '8%', '8%', '8%', '7%', '6%', '8%', '18%'], align=['l', 'r', 'r', 'r', 'r', 'r', 'r', 'r', 'r', 'l']))
    ch = [m[t].chgp for t, _ in SECTORS]; up = sum(1 for c in ch if c > 0)
    beat = [t for t, _ in SECTORS if m[t].chgp > sp.chgp]
    b5 = sum(1 for t, _ in SECTORS if m[t].ret5 > sp.ret5)
    o.append(pre(f'十一個 SPDR 板塊：收升 {up} 個、收跌 {len(ch) - up} 個（簡單平均 {P(sum(ch) / 11)}，{CALC}）；跑贏 SPY 當日：{"、".join(beat) or "無"}；近 5 日跑贏 SPY：{b5} 個。RSI 取自圖面（{CHART}）；52 週高取自行情日線（不復權）。'))
    if T.get('sector_box'): o.append(box(T['sector_box']))
    o.append(sub('V1.0 第七節要求逐條回答')); o.append(table(['問題', '答案'], T['sector_qa'], widths=['27%', '73%']))
    o.append(pre('⚠ 按 V1.0 第七節：冇可核實嘅資金流或 ETF 申贖數據，全份不用「資金淨流入／淨流出」；只描述價格強弱同輪動跡象，依據係收市價、相對表現同成交量比率。'))
    if T.get('sector_flag'): o.append(sub('★ 需要標記嘅板塊特徵')); o.append(f'<p>{T["sector_flag"]}</p>')
    return o

def s6(m, S, T):
    o = [sec('六', '過去 5 個交易日催化劑及未來一星期事件')]
    if T.get('catalysts_box'): o.append(box(T['catalysts_box']))
    o.append(sub('6.1　過去 5 個交易日'))
    o.append(table(['事件日期', '事件及來源', '已知市場反應', '可能影響', '仍待確認'], T['past_events'], widths=['10%', '37%', '21%', '18%', '14%']))
    if T.get('past_note'): o.append(pre(T['past_note']))
    o.append(sub('6.2　未來一星期已確認事件'))
    nxt = [d for d in [m.date]]
    o.append(pre('夏令時間核算：美東與香港時差按日期自動判斷（EDT＝UTC−4 相差 12 小時；EST＝UTC−5 相差 13 小時）。' + _g(T, 'next_week_note')))
    nw = []
    for e in T['next_week']:                       # (事件, 美東日期 YYYY-MM-DD, HH:MM, 預期／前值, 關注點[, cls])；時間 None＝待核實
        name, d_, hm, exp, why = e[:5]; cls = e[5] if len(e) > 5 else ''
        if hm:
            et, hk = et_hk(d_, hm); a, b = f'{md(d_)}（{wd(d_)}）{et}', hk
        else: a, b = f'{md(d_)}（{wd(d_)}）時間未核實', '時間未核實'
        nw.append(([name, a, b, exp, why], cls))
    o.append(table(['事件', '美東時間', '香港時間', '預期／前值', '市場關注點'], nw, widths=['22%', '15%', '15%', '21%', '27%']))
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
    rows = [['分析框架', 'JW 大盤分析指令｜共用補充版'], ['AI', a['ai_note']], ['模式', a['mode']],
            ['分析日期', f'{a["analysis_date"]}（香港 UTC＋8）｜美國交易日 {m.date}'], ['外部來源', a['sources']],
            ['免責', '分析框架與個人判讀，用於研究交流，<b>不構成投資建議</b>。價位隨交易日更新。不提供勝率或發生機率，亦不把市況分類當作買賣許可。']]
    o.append(table(None, rows, widths=['14%', '86%'], kv=True))
    return o

def build_html(m, S, T):
    parts = head(m, S, T) + s1(m, S, T) + sjl(m, S, T) + s2(m, S, T) + s3(m, S, T) + s4(m, S, T) + s5(m, S, T) + s6(m, S, T) + s7(m, S, T) + s8(m, S, T) + s9(m, S, T) + tail(m, S, T)
    return '\n'.join(parts)
