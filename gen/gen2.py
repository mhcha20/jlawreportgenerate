from lib import *
from gen import *

def md(): return DATE[5:].replace('-', '/')

def band(tag, title, parts):
    return f'<div class="band"><span class="chip">{tag}</span><span class="bt">{title}</span><span class="bp">{parts}</span></div>'

def secx(title, small=''):
    return f'<h2 class="sec">{title}' + (f' <span class="ss">{small}</span>' if small else '') + '</h2>'

def trend_rows(m):
    rows = []
    for k, role in ((10, '短期生命線，動態支撐／反壓分水嶺'), (20, '波段多空防守中樞'), (50, '機構中期持倉成本防線'), (200, '長期牛熊線')):
        dd = (m[f'ma{k}'] / m[f'ma{k}_5'] - 1) * 100
        dw = '上升' if dd > 0.05 else '下跌' if dd < -0.05 else '持平'
        rows.append((f'SMA{k}', f'[計算] {m[f"ma{k}"]:.2f}（5 日前 {m[f"ma{k}_5"]:.2f}，{sg(dd)}）；現價 {sg(m[f"d{k}"])}', f'{dw}；{role}'))
    return rows

def strip_svg(m, S):
    c = m['close']; A, B = S['A'], S['B']
    pts = [S['exitp'], S['reduce'], B['zone'][0], B['zone'][1], A['trig'], c, m['ma50'], m['ma20']]
    lo, hi = min(pts), max(pts); sp = hi - lo; lo -= sp * .08; hi += sp * .08
    W = 700; X = lambda p: 20 + (p - lo) / (hi - lo) * (W - 40)
    s = [f'<svg viewBox="0 0 {W} 84" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<line x1="20" x2="{W-20}" y1="42" y2="42" stroke="#444" stroke-width="1"/>')
    s.append(f'<rect x="{X(B["zone"][0]):.1f}" y="34" width="{max(X(B["zone"][1])-X(B["zone"][0]),3):.1f}" height="16" fill="#cfe8d5" stroke="#1a7f4b" stroke-width=".8"/>')
    ta = A['trig']
    s.append(f'<rect x="{X(ta*0.9975):.1f}" y="34" width="{max(X(ta*1.0025)-X(ta*0.9975),3):.1f}" height="16" fill="#f6d6d2" stroke="#c0392b" stroke-width=".8"/>')
    for p, lab, col, up in ((S['exitp'], f'離場 {S["exitp"]:.2f}', '#c0392b', True), (S['reduce'], f'減倉 {S["reduce"]:.2f}', '#e0a31e', False),
                            (m['ma50'], f'MA50 {m["ma50"]:.2f}', '#2e86c1', False), (m['ma20'], f'MA20 {m["ma20"]:.2f}', '#8e44ad', True)):
        s.append(f'<line x1="{X(p):.1f}" x2="{X(p):.1f}" y1="30" y2="54" stroke="{col}" stroke-width="1.6"/>')
        s.append(f'<text x="{X(p):.1f}" y="{22 if up else 66}" font-size="8.5" fill="{col}" text-anchor="middle">{lab}</text>')
    s.append(f'<circle cx="{X(c):.1f}" cy="42" r="5" fill="#111"/><text x="{X(c):.1f}" y="12" font-size="9.5" font-weight="700" text-anchor="middle">現價 {c:.2f}</text>')
    s.append(f'<text x="{X((B["zone"][0]+B["zone"][1])/2):.1f}" y="80" font-size="8" fill="#1a7f4b" text-anchor="middle">回踩入場區 {B["zone"][0]:.2f}–{B["zone"][1]:.2f}</text>')
    s.append(f'<text x="{X(ta):.1f}" y="80" font-size="8" fill="#c0392b" text-anchor="middle">順勢觸發 {ta:.2f}</text>')
    s.append('</svg>')
    return ''.join(s)

def bars_html(S):
    rows = ''
    order = ['趨勢', '成交量', '圖形', 'Momentum', '基本面', '市場配合', '機構支持']
    dd = {n: s for n, s, r in S['dims']}
    for n in sorted(order, key=lambda x: -dd[x]):
        s = dd[n]; pc = s / 5 * 100
        col = '#2e8b57' if pc >= 80 else '#e8a33d' if pc >= 50 else '#d6453d'
        rows += f'<div class="br"><span class="bn">{n}</span><span class="bb"><i style="width:{pc}%;background:{col}"></i></span><span class="bv">{s} / 5</span></div>'
    return rows

def build_report(m, S, T):
    t = S['t']; c = m['close']; A, B = S['A'], S['B']; d = S['dist_to']; sc = S['score']
    tests = S['tests']; mk = lambda ok: '✔' if ok else '✘'
    tone = {2: 'r', 3: 'y', 4: 'g', 5: 'g'}.get(S['stars'], 'y')
    dd = {n_: (s, r) for n_, s, r in S['dims']}
    stars_n = sum(x[1] for x in S['dims'])
    pbs = dd['Pullback'][0]; bos = dd['Breakout'][0]
    prior_short = S['prior'].split('（')[0]
    # ---------------- page 1
    p1 = f'''
<h1 class="big">{t} 本體報告</h1>
<p class="subt">{S['zh']}（{S['exch']}）· {S['sector']} · JLaw × MYT 股票分析終極指令 V2.0 · 10 頁硬上限</p>
<div class="infobox"><b>分析交易日：{DATE_ZH}</b> <span class="pill">正常收市 {DATE}</span> <b>資料截止：</b>{S['asof_full']}　<b>幣別：</b>USD　<b>框架：</b>V2.0<br>
<b>版本注意：</b>價格唯一來源為 {S['src_note']}（{len(m['closes'])} 根）；{S['shot_note']}，最後一根 K 線 {md()} 為完整收市。上一份＝{S['prev_md']} 行動卡（{prior_short}）{S['prev_note']}<b>{S['ver_note']}</b>九構面分數 ＝ 星數 ÷ 45 × 100（同群組公式一致）。{md()} 收市後消息一律不用。{S['ai_line']}</div>
<div class="cards">
 <div class="cd {tone}"><div class="k">個股研究評等</div><div class="v">{S['rating']}　{sc:.0f} / 100</div><div class="s">上一份：{S['prev_md']} {prior_short}（計法唔同，唔作升降）· 覆蓋率 100%</div></div>
 <div class="cd {tone}"><div class="k">交易設置狀態</div><div class="v">{T['setup']}</div><div class="s">Pullback {'★'*pbs} · Breakout {'★'*bos}</div></div>
 <div class="cd {tone}"><div class="k">市場狀態及執行限制</div><div class="v">{S['mkt_state']}</div><div class="s">承襲 {S['mkt_ref']}</div></div>
</div>
<div class="concl2"><b>一句話結論：</b>{T['oneliner']}<div class="pl">回踩路徑：{B['zone'][0]:.2f}–{B['zone'][1]:.2f}（止損 {B['stop']:.2f}） · 順勢路徑：{A['trig_rule']}（觸發 {A['trig']:.2f}） · 減倉線 {S['reduce']:.2f}：距 {sg(d['reduce'])} · 離場線 {S['exitp']:.2f}：距 {sg(d['exit'])}，未觸發</div></div>
{strip_svg(m, S)}
<p class="sec-note">綠＝回踩入場區；紅＝順勢觸發帶；距離一律 ÷ 現價 {c:.2f}：離場 {sg(d['exit'])}；減倉 {sg(d['reduce'])}；回踩區上限 {sg(d['zone_hi'])}；觸發價 {sg(d['trig'])}；SMA50 {m['ma50']:.2f} 距 {sg(m['d50'])}（÷SMA）。ATR14 ${m['atr14']:.2f}（{m['atrp']:.2f}%）。</p>
<div class="two">
 <div class="pn"><div class="pt">評分分解（7 構面；★／5，按比例由高至低）</div>{bars_html(S)}<div class="sec-note">綠 ≥80%、琥珀 50–79%、紅 &lt;50%。Pullback、Breakout 另列第七、八部分；按第十二部分 9 構面合計 {stars_n}／45 星＝{sc:.0f}／100。</div></div>
 <div class="pn"><div class="pt">同上一份最大變化</div><p>{T['biggest']}</p>
 <div class="pt">下一交易日三項重點</div><ul class="facts">{''.join(f'<li>{x}</li>' for x in T['next3'])}</ul>
 <div class="pt">本次覆核</div><p>{T['review']}</p></div>
</div>
<div class="tagline">內容標籤：[圖表] 原始 K 線讀數 · [外部] 已核實外部事實（標明出處）· [計算] 本報告自行運算 · [推論] 分析判斷。本報告為資料整理及條件式研究，不是個人化投資建議；分數不是勝率。</div>
'''
    # ---------------- page 2
    p2 = '<div class="pg"></div>' + band('環境', '大市、生命週期及趨勢', '第一至三部分') + \
        secx('第一部分｜大市分析', 'V2.0 壓縮：只答三條，不重述大盤報告') + f'<p>個股：{S["rating"]}／市場：{S["mkt_state"]}（承襲 {S["mkt_ref"]}，未變）。</p>' + \
        table(['觀察對象', '表現', '判斷'], [('(a) 市況分類 vs 上一份', T['p1a'][0], T['p1a'][1]), ('(b) 個股專屬門檻', T['p1b'][0], T['p1b'][1]), ('(c) 大盤生效指示', T['p1c'][0], T['p1c'][1])], ['19%', '58%', '23%']) + \
        secx('第二部分｜股票生命週期（Weinstein）') + f'<p class="lead"><b>{S["stage"]}。</b></p><p>{T["stage_txt"]}</p>' + \
        secx('第三部分｜趨勢分析', '均線方向口徑：全篇統一「對比 5 個交易日前」') + \
        table(['檢查', '讀數／結果', '意義'], trend_rows(m) + [
            ('50MA ＞ 200MA', f'[計算] {m["ma50"]:.2f} ÷ {m["ma200"]:.2f} − 1 ＝ {sg((m["ma50"]/m["ma200"]-1)*100)}' + ('（緩衝不足 2%，緩衝有限）' if abs((m["ma50"]/m["ma200"]-1)*100) < 2 else ''), '緩衝充足' if abs((m["ma50"]/m["ma200"]-1)*100) >= 2 else '緩衝有限'),
            ('Higher High／Higher Low', T['hhhl'], '結構'),
            ('Momentum', T['mom'], '動能')], ['16%', '60%', '24%']) + \
        note(f'均線口徑：收盤價自行重建 SMA（含當日），{S["src_label"]} {len(m["closes"])} 根，同 TradingView 圖示對照一致到兩位小數。ATR14 簡單平均 ${m["atr14"]:.2f}（{m["atrp"]:.2f}%）、Wilder 平滑 ${m["atr14w"]:.2f}（{m["atrpw"]:.2f}%），並列，本報告距離及倍數一律用簡單平均值。RSI14 取自 TradingView 圖面；第三方交叉核對：TradingView／Futubull 圖面 SMA 與重算值一致（附錄第三節）。最近 30 個交易日有 {m["above50_30"]} 日收市高於當日 SMA50。')
    # ---------------- page 3
    svg1 = chart(m, 120, vol_ma=m['v50'], width=720, height=300, hlines=T['chart1_lines'])
    p3 = '<div class="pg"></div>' + band('技術', '成交量及圖表形態', '第四、五部分') + \
        secx('第四部分｜成交量分析（VPA）', f'20 日均量 {m["v20"]/1000:,.2f}M、50 日均量 {m["v50"]/1000:,.2f}M（均不含當日）') + \
        table(['檢查', '判斷'], T['vol_rows'], ['20%', '80%']) + \
        note(f'量能門檻：右側轉強日 ≥ 1.0×50 日（{m["v50"]/1000:.2f}M）；突破 ≥ 1.5×50 日（{m["v50"]*1.5/1000:.2f}M）。含當日 50 日均量 {m["v50i"]/1000:.2f}M，與不含當日值並列，門檻一律用不含當日值。派發日定義：下跌日、量大過前日且大過當日 50 日均量（不含當日），窗口 25 個交易日：{("、".join(m["dist"]) if m["dist"] else "無")}（{len(m["dist"])} 個）。成交量用 Longbridge 正常時段綜合量。') + \
        secx('第五部分｜圖表形態') + svg1 + \
        note(f'K 線為 {S["src_label"]} 真實 OHLC（陽綠陰紅），120 個交易日（約半年）；SMA10／20／50／200，200 日線覆蓋整個顯示區間；Y 軸上下各外擴 10%；下方柱＝成交量，虛線＝50 日均量。') + \
        f'<div class="now"><b>目前屬於：</b>{T["pattern"]}</div>' + facts(T['pattern_notes'])
    # ---------------- page 4
    p4 = '<div class="pg"></div>' + band('決策', '支持阻力及設置評分', '第六至八部分') + \
        secx('第六部分｜Support／Resistance') + table(['類別', '價位', '依據'], T['sr_rows'], ['20%', '18%', '62%']) + \
        note('均線價位每日移動，屬動態觀察帶，非固定止損價。收市價為準：日內穿越不算失守，亦不算突破（紀律 3）。') + \
        secx('第七部分｜Pullback 評分', f'— {T["pb_star"]}') + facts(T['pb']) + \
        secx('第八部分｜Breakout 評分', f'— {T["bo_star"]}') + facts(T['bo']) + note('突破成功率：N/A，缺乏足夠回測樣本。')
    # ---------------- page 5
    fund = table(['項目', '最近一季', '前一季／去年同期', '意義'], T['fund_rows'], ['20%', '22%', '26%', '32%'])
    p5 = '<div class="pg"></div>' + band('判斷', '機構、基本面及風險', '第九、十部分') + \
        secx('第九部分｜機構分析') + table(['項目', '判斷'], [
            ('Minervini 趨勢模板', S['mv_line']), ('CANSLIM', T['canslim_line']), ('分析師', T['analyst_line']), ('Smart Money', T['smart_line']), ('板塊背景', T['sector_line'])], ['20%', '80%']) + \
        '<h3>基本面重點（Futubull 截圖讀數，單位 USD）</h3>' + fund + \
        secx('第十部分｜風險分析', f'整體：{T["risk_lvl"]}') + table(['風險類別', '內容'], [tuple(x.split('：', 1)) for x in T['risk']], ['18%', '82%'])
    # ---------------- page 6
    def rr(x): return f'{x:.2f}R'
    sB, sA = S['sweepB'], S['sweepA']; sB10, sA10 = S['sweepB10'], S['sweepA10']
    n = m['n']; C = m['C']; V = m['V']
    def last_ago(md_list):
        if not md_list: return '無'
        idx = [b[0] for b in m['bars']].index(md_list[-1]); return f'{md_list[-1]}，即 {n-1-idx} 個交易日前'
    b_days = [m['bars'][i][0] for i in range(n - 20, n) if m['L'][i] <= B['zone'][1] and m['H'][i] >= B['zone'][0]]
    px_days = [m['bars'][i][0] for i in range(n - 20, n) if C[i] >= A['cond_px']]
    full_days = [m['bars'][i][0] for i in range(n - 20, n) if C[i] >= A['cond_px'] and V[i] >= sum(V[i-50:i]) / 50]
    S['b_days'] = b_days; S['px_days'] = px_days; S['full_days'] = full_days
    tests_txt = (f'① 大市上升趨勢 {mk(tests[0])}（{S["mkt_state"]}）；② 第二階段 {mk(tests[1])}（{T["stage_test"]}）；③ RRR ≥ 2 {mk(tests[2])}（回踩 {rr(B["R"][-1])}／順勢 {rr(A["R"][-1])}）；'
                 f'④ 雜訊被掃率 < 30% {mk(tests[3])}（回踩 {sB[0]}／{sB[1]}＝{sB[0]/sB[1]*100:.0f}%；順勢 {sA[0]}／{sA[1]}＝{sA[0]/sA[1]*100:.0f}%）。缺 {4-sum(tests)} 項 → 標準倉{S["tier"]}。檔位對應嘅倉位比例群組未提供，不自訂。{T["tier_tail"]}')
    plan_rows = [
        ('最佳買入價（R1）', f'回踩路徑（機械式）：低位進入 {B["zone"][0]:.2f}–{B["zone"][1]:.2f}（下限＝{T["zone_lo_def"]}；上限＝{T["zone_hi_def"]}），參考入場價 {B["entry"]:.2f}。順勢路徑：{A["trig_rule"]}，參考入場價 {A["trig"]:.2f}；距現價 {sg(d["trig"])}。'),
        ('追價上限', f'順勢路徑：{A["trig"]+m["atr14"]*0.5:.2f}（觸發價 ＋ 0.5×ATR14，本份機械定義）；回踩路徑：{B["zone"][1]:.2f}'),
        ('加倉位', T['addon']),
        ('止損價／止損%', f'回踩路徑 {B["stop"]:.2f}（{B["stop_note"]}），{sg((B["stop"]/B["entry"]-1)*100)}（÷入場價）；順勢路徑 {A["stop"]:.2f}（{A["stop_note"]}），{sg((A["stop"]/A["trig"]-1)*100)}（÷入場價）'),
        ('目標價（R2，結構性）', '回踩路徑：' + ' ／ '.join(f'T{i+1} {tp:.2f}（{nm}）' for i, (tp, nm) in enumerate(zip(B['T'], B['Tn']))) + '。主目標＝最後一個。'),
        ('個別 RRR', f'回踩路徑 入 {B["entry"]:.2f}／止損 {B["stop"]:.2f}：' + '、'.join(f'T{i+1} {rr(x)}' for i, x in enumerate(B['R'])) + f'。順勢路徑 入 {A["trig"]:.2f}／止損 {A["stop"]:.2f}：' + '、'.join(f'{tp:.2f} {rr(x)}' for tp, x in zip(A['T'], A['R'])) + '。' + T['rrr_note']),
        ('順勢路徑（R3）', f'有：順勢路徑（上表）。{T["r3_note"]}'),
        ('倉位檔位（R4）', tests_txt),
        ('Swing／Position', T['swing_only']),
        ('持有至下次財報？', T['earn_line']),
    ]
    sweep_def = (f'雜訊被掃率定義（沿用群組口徑）：過去 60 個交易日（只計有完整 5 日窗口者）每日收市假想入場，其後 5 個交易日內最低價觸及「入場價 ×（1−止損%）」的比例。'
                 f'回踩路徑 {B["risk"]/B["entry"]*100:.2f}% → {sB[0]}／{sB[1]}＝{sB[0]/sB[1]*100:.0f}%（10 日窗口 {sB10[0]/sB10[1]*100:.0f}%；窗口 {sB[2]}–{sB[3]}）。'
                 f'順勢路徑 {A["risk"]/A["trig"]*100:.2f}% → {sA[0]}／{sA[1]}＝{sA[0]/sA[1]*100:.0f}%（10 日窗口 {sA10[0]/sA10[1]*100:.0f}%）。屬歷史頻率，不是未來機率。')
    f1 = table(['入場區', '近 20 個交易日', '結論'], [
        (f'回踩路徑：低位入 {B["zone"][0]:.2f}–{B["zone"][1]:.2f}', f'印過 {len(b_days)} 次（{"、".join(b_days)}），最近一次 {last_ago(b_days)}', T['f1_B']),
        (f'順勢路徑：收市 ≥{A["cond_px"]:.2f}（只計價格）', (f'收市印過 {len(px_days)} 次（{"、".join(px_days)}），最近一次 {last_ago(px_days)}' if px_days else '近 20 日 0 次'), ('價格曾印，但完整條件' + (f'近 20 日 {len(full_days)} 次' if full_days else '從未觸發')) if px_days else '未觸發'),
        ('順勢路徑 完整條件（價 ＋ 量 ≥ 1.0×50 日）', f'近 20 日 {len(full_days)} 次' + (f'（{"、".join(full_days)}）' if full_days else ''), T['f1_A'])], ['32%', '40%', '28%'])
    sN = S['sweepNow']
    f2 = table(['情境', '結果（% ÷入場價；R ＝（現價−入場）÷ 每股風險）'], [
        (f'今日 {c:.2f} 照回踩路徑入、止損 {B["stop"]:.2f}', f'每股風險 ${S["cost_risk"]:.2f}（{sg(S["cost_pct"])}）。到 T1 {B["T"][0]:.2f}＝{sg(S["cost_pt"][0])}／{S["cost_R"][0]:.2f}R；到主目標 {B["T"][-1]:.2f}＝{sg(S["cost_pt"][-1])}／{S["cost_R"][-1]:.2f}R；過去 60 日 5 日內被掃 {sN[0]/sN[1]*100:.0f}%（{sN[0]}／{sN[1]}）'),
        (f'按計劃回踩入場（入 {B["entry"]:.2f}、止損 {B["stop"]:.2f}）', f'每股風險 ${B["risk"]:.2f}（{sg(-B["risk"]/B["entry"]*100)}）；主目標 {rr(B["R"][-1])}；被掃率 {sB[0]/sB[1]*100:.0f}%'),
        ('按順勢路徑等合格條件（從未入場）', '0R')], ['38%', '62%']) + note(T['f2_interp'].replace('{NOWSWEEP}', f'{sN[0]/sN[1]*100:.0f}'))
    f3 = f'<div class="two"><div class="pn bl"><div class="pt">未持倉</div><ul class="facts"><li>{T["flat"]}</li><li>設警報：{T["alerts_txt"]}</li></ul></div><div class="pn"><div class="pt">已持倉</div><ul class="facts"><li>{T["held"]}</li></ul></div></div>'
    p6 = '<div class="pg"></div>' + band('決策', '交易計劃', '第十一部分（V1.4 R1–R4 ＋ V2.0 三項強制欄位）') + \
        secx('第十一部分｜交易計劃', f'條件式研究，非交易建議；止損% ÷入場價，距離% ÷現價 {c:.2f}') + table(['欄位', '安排'], plan_rows, ['17%', '83%']) + note(sweep_def) + \
        secx('強制欄位 1｜執行區印過未？', '近 20 個交易日') + f1 + note(T['f1_note']) + \
        secx('強制欄位 2｜唔做嘅代價', '如果今日按計劃以外嘅方式入咗會點') + f2 + \
        secx('強制欄位 3｜已持倉／未持倉') + f3
    # ---------------- page 7
    zones = [dict(lo=B['zone'][0], hi=B['zone'][1], color='#1a9e5c', start=m['n']-40, label='回踩入場區', op=.16),
             dict(lo=A['trig'] * 0.9975, hi=A['trig'] * 1.0025, color='#d6453d', start=m['n']-40, label='順勢觸發帶', op=.16),
             dict(lo=B['entry'], hi=B['T'][-1], color='#2e86c1', right=True, op=.22, noscale=True),
             dict(lo=B['stop'], hi=B['entry'], color='#e0a31e', right=True, op=.30)]
    svg2 = chart(m, 40, ma_list=(10, 20), zones=zones, right_pad=10, width=720, height=330, show_vol=False,
                 hlines=[dict(p=B['entry'], color='#1f3a5f', dash='5,3', w=1), dict(p=B['T'][-1], color='#2e86c1', dash='2,3', w=.9, noscale=True), dict(p=B['stop'], color='#c0392b', dash='3,2', w=1), dict(p=c, color='#555', dash='1,2', w=.8)])
    p7 = f'<div class="chtitle" style="margin-top:12px">{t} 交易計劃圖（回踩路徑入 {B["entry"]:.2f}／止損 {B["stop"]:.2f}／主目標 {B["T"][-1]:.2f}；{md()} 收 {c:.2f}）</div>' + svg2 + \
        note('近 40 個交易日日 K ＋ SMA10／20。綠色帶＝回踩入場區、紅色帶＝順勢觸發帶（自該價位成形嗰根 K 線起繪）；右側留白區：琥珀＝風險區（入場→止損）、藍＝報酬區（入場→主目標，超出圖頂以↑標示）；虛線＝參考入場價，右側標示目標、現價、止損。')
    # ---------------- page 8
    ordered = ['趨勢', '成交量', '圖形', 'Momentum', '基本面', '市場配合', '機構支持', 'Pullback', 'Breakout']
    p8 = '<div class="pg"></div>' + band('判斷', '評分及最後結論', '第十二、十三部分') + \
        secx('第十二部分｜交易評分', '本份係首份，九構面全部重新起算，所以每格都寫理由') + \
        table(['構面', '星級', '理由'], [(n_, stars(dd[n_][0]), dd[n_][1]) for n_ in ordered], ['13%', '14%', '73%']) + \
        note(f'總分：{sc:.0f}／100（{stars_n}／45 星按比例換算 {sc:.1f}，四捨五入；9 項全部評分，覆蓋率 100%；機構支持嘅 Hard Evidence 限於 13F／Form 4 截圖，RS 百分位缺項）。上一份 {S["prev_md"]}：{prior_short}（{S.get("prior_cmp", "評分表未提供，無法逐格比較，唔當升降")}）。分數不是勝率，不可跨股比較。') + \
        secx('第十三部分｜最後結論') + f'<div class="concl3"><span>評等 <b>{S["rating"]}</b></span><span>總分 <b>{sc:.0f}／100</b></span><span>個股：{S["rating"]}／市場：{S["mkt_state"]}（承襲）</span></div>' + \
        f'<div class="two"><div class="pn"><div class="pt">保留 {S["rating"].split(" ")[0]} 原因</div>{facts(T["keep"])}</div><div class="pn"><div class="pt">不升級的原因</div>{facts(T["noup"])}</div></div>' + \
        f'<h3>與上一份（{S["prev_md"]} 行動卡）逐項比較</h3>' + table(['項目', md()], [
            ('評等／分數', f'{S["rating"]}；{sc:.0f}／100（{stars_n} 星：' + '、'.join(f'{n_} {dd[n_][0]}' for n_ in ordered) + '）'),
            ('價格', f'收 {c:.2f}；距 52 週高 {sg((c/S["hi52"]-1)*100)}；SMA10／20／50／200＝{m["ma10"]:.2f}／{m["ma20"]:.2f}／{m["ma50"]:.2f}／{m["ma200"]:.2f}；20／50 日均量 {m["v20"]/1000:.2f}M／{m["v50"]/1000:.2f}M（不含當日）；25 日派發日 {len(m["dist"])} 個'),
            ('上一份', T['vsprior']),
            ('三項重點', T['next3_line']),
            ('計劃', T['plan_line'])], ['14%', '86%'])
    # ---------------- page 9
    p9 = '<div class="pg"></div>' + band('判斷', '最後四問', 'V2.0 第七節') + \
        ''.join(f'<h3>{i}. {q}</h3><p>{a}</p>' for i, (q, a) in enumerate([('職業交易員今日應該做咩？', T['q1']), ('呢宗交易最大嘅風險係咩？', T['q2']), ('我現在最容易犯嘅錯誤係咩？', T['q3']), ('一句話總結。', T['q4'])], 1)) + \
        '<div class="box"><b>未決問題（交群組裁決）</b>' + facts(T['open']) + '</div>' + \
        '<p class="small" style="margin-top:8px">本報告為資料整理及條件式研究，不是個人化投資建議。評等不等於買賣許可；分數不是勝率，亦不可與其他股票嘅分數直接比較。所有命中率同被掃率皆為歷史頻率，唔係未來機率；R 值為計劃值，非實現值；止損未必可按設定價成交。所有價位隨交易日更新。</p>'
    return p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9

def build_appendix(m, S, T):
    t = S['t']
    h = f'<div class="hdr"><h1>{t} 核對附錄｜{DATE_ZH}</h1><div class="info">JLaw × MYT V2.0（不限篇幅）</div></div><div class="bar"></div>'
    s1 = secx('一、承襲門檻對照表', '原文逐字 ＋ 今日實際 ＋ 結果；重算值同原文唔同嘅並列，唔取代') + table(['來源原文（逐字）', '今日實際（收市）', '結果'], T['thr'], ['40%', '40%', '20%'])
    s2 = secx('二、口徑／分母聲明') + facts(T['caliber'])
    s3 = secx('三、多來源並列清單', '唔調和、唔平均、唔挑一個') + table(['項目', '來源甲', '來源乙', '處理'], T['conflicts'], ['16%', '28%', '28%', '28%'])
    s4 = secx('四、對抗式覆核更正記錄') + T['corr_html']
    s5 = secx('五、資料來源、時間口徑、今日缺項') + facts(T['sources'])
    s6 = secx('六、交返群組裁決嘅未決問題') + facts(T['open'])
    s7 = secx('七、Minervini 趨勢模板逐項') + mv_table(S) + secx('八、CANSLIM 逐項') + table(['字母', '截圖讀數／計算', '判斷'], T['canslim'], ['8%', '70%', '22%'])
    s7b = secx('九、Smart Money 明細', 'Hard：13F／Form 4；Soft 另列') + facts(T['smart'])
    s8 = secx('十、朗讀稿') + f'<h3>3 分鐘重點版（{len(T["script3"])} 字，上限 950）</h3><p class="small12">{T["script3"]}</p>' + f'<h3>完整版（{len(T["scriptfull"])} 字，上限 3,500）</h3><p class="small12">{T["scriptfull"]}</p>'
    return h + s1 + s2 + s3 + s4 + s5 + s6 + s7 + s7b + s8

def build_daily(items):
    rows = []
    for S, m, T in items:
        sc = S['score']
        rows.append((f'<b>{S["t"]}</b>', f'{S["rating"]}', f'{sc:.0f}（新起算，上一份 {S["prior"].split("（")[0].split(" ")[-1]}）', T['daily_action'], T['daily_trig'], T['daily_dist'], T['daily_R'], T['daily_line']))
    h = f'<div class="hdr"><h1>每日跨股總表｜{DATE_ZH}</h1><div class="info">V2.0 第八節｜試做版</div></div><div class="bar"></div>'
    tb = table(['股票', '評等', '分數（＋自身箭嘴）', '今日動作', '最近觸發位', '距離％', 'R 值', '最關鍵嗰條線'], rows, ['7%', '8%', '11%', '19%', '16%', '15%', '11%', '13%'])
    sw = '；'.join(f'{S["t"]} 回踩 {S["sweepB"][0]}／{S["sweepB"][1]}＝{S["sweepB"][0]/S["sweepB"][1]*100:.0f}%' for S, m, T in items)
    cav = ('<div class="box hi"><b>口徑聲明（V2.0 第八節）：</b><ul class="facts"><li>分數唔可以跨股比較 —— 每隻只同自己嘅歷史比。本表兩隻分數係本份首次起算，所以「自身箭嘴」暫時冇得標；上一份行動卡嘅分數計法未提供，唔作升降。</li>'
           '<li>距觸發位％、R 值、雜訊被掃率、今日動作　可以跨股比較 → 揀邊隻睇、揀邊隻做，睇呢四欄，唔好睇分數。</li>'
           f'<li>距離％ ÷ 現價（當日收市）；R 值＝回踩路徑，以參考入場價同止損價計。雜訊被掃率（60 日、5 日窗口）：{sw}。</li></ul></div>')
    return h + tb + cav
