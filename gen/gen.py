import sys, json
from lib import *

DATE = '2026-10-21'; DATE_ZH = '2026-10-21（三）'   # build.py 會覆寫
def md(): return DATE[5:].replace('-', '/')

# ------------------------------------------------------------------ per-stock specs
# 每隻股票嘅 spec（S）同敘述（T）由每日排程按截圖／行情產生，唔放喺 repo；欄位定義見 README.md

# ------------------------------------------------------------------ shared builders
def R(entry, stop, tgt): return (tgt - entry) / (entry - stop)

MARKETS = {
    'US': dict(mkt='US', asof='16:00 ET（香港 次日 04:00）', asof_full='美東 當日 16:00＝香港 次日 04:00', ccy='USD', cur='$', src_name='Longbridge', smart_hard='13F／Form 4', cov='覆蓋率 100%', ma_chk='同 TradingView 圖示一致到兩位小數'),
    'HK': dict(mkt='HK', asof='16:00 HKT', asof_full='香港當日 16:00 HKT', ccy='HKD', cur='HK$', src_name='Yahoo', smart_hard='披露易持股／機構持股頁', cov='覆蓋率按實際有圖格數列出', ma_chk='同 Futubull 圖面對照（除息調整價並列唔採用）', mkt_ref='無（只用圖面指數）'),
    'JP': dict(mkt='JP', asof='15:30 JST（＝14:30 HKT）', asof_full='東京當日 15:30 JST＝香港 14:30 HKT', ccy='JPY', cur='¥', src_name='Yahoo', smart_hard='大量持股報告／機構持股頁', cov='覆蓋率按實際有圖格數列出', ma_chk='同 Futubull 圖面對照（除息調整價並列唔採用）', mkt_ref='無（只用圖面指數）'),
    'KR': dict(mkt='KR', asof='15:30 KST（＝14:30 HKT）', asof_full='首爾當日 15:30 KST＝香港 14:30 HKT', ccy='KRW', cur='₩', src_name='Yahoo', smart_hard='機構持股頁', cov='覆蓋率按實際有圖格數列出', ma_chk='同 Futubull 圖面對照（除息調整價並列唔採用）', mkt_ref='無（只用圖面指數）'),
}
def market_of(t):
    t = str(t)
    if t.isdigit(): return 'HK' if len(t) == 5 else 'KR' if len(t) == 6 else 'JP'
    return 'US'
def us_close_hk(d=None):
    """美東 16:00 收市＝香港幾點：夏令（EDT）次日 04:00，冬令（EST，11 月第一個星期日起）次日 05:00"""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    t = datetime.fromisoformat((d or DATE) + 'T16:00').replace(tzinfo=ZoneInfo('America/New_York'))
    return t.astimezone(ZoneInfo('Asia/Hong_Kong')).strftime('%H:%M'), t.tzname()
def market_defaults(t):
    d = dict(MARKETS[market_of(t)])
    if d['mkt'] == 'US':
        hk, tz = us_close_hk()
        d['asof'] = f'16:00 {tz}（香港 次日 {hk}）'; d['asof_full'] = f'美東 當日 16:00 {tz}＝香港 次日 {hk}'
    return d

def plan_numbers(m, S):
    c = m['close']
    A, B = S['A'], S['B']
    for k_, v_ in market_defaults(S['t']).items(): S.setdefault(k_, v_)
    for k_, v_ in dict(src_note='網站 /api/ohlcv（Yahoo Finance 日線，正常交易時段、不復權）', src_label='Yahoo 日線', mkt_state='反彈嘗試', prev_note='', ver_note='本份係 V2.0 首份試做：承襲帳同大盤執行規則未提供，唔套用、唔自行訂立。', ai_line='AI：Claude，直接閱讀截圖圖像。', shot_note='截圖於當日收市後拍攝', prev_md='前一交易日', mkt_ref='大盤報告').items(): S.setdefault(k_, v_)
    S['A']['risk'] = A['trig'] - A['stop']; S['B']['risk'] = B['entry'] - B['stop']
    S['A']['R'] = [R(A['trig'], A['stop'], t) for t in A['T']]
    S['B']['R'] = [R(B['entry'], B['stop'], t) for t in B['T']]
    S['cost_risk'] = c - B['stop']
    S['cost_pct'] = (c / B['stop'] - 1) * 100 * -1 if False else (B['stop'] / c - 1) * 100
    S['cost_R'] = [(t - c) / (c - B['stop']) for t in B['T']]
    S['cost_pt'] = [(t / c - 1) * 100 for t in B['T']]
    S['prints_B'] = count_prints(m, *B['zone'])
    # run-up zone for path A: price touched [trig-0.25%, trig+0.25%] region ~ use MA20 vicinity
    zlo = A['trig'] * 0.9975; zhi = A['trig'] * 1.0025
    S['prints_A'] = count_prints(m, zlo, zhi)
    # Plan-A signal days: close > then-MA20 and vol >= then-50d avg (last 20 sessions)
    c_all = m['closes']; n = m['n']; V = m['V']; C = m['C']; days = []
    for i in range(n - 20, n):
        e = len(c_all) - (n - i)
        ma20 = sum(c_all[e-19:e+1]) / 20
        a50 = sum(V[i-49:i+1]) / 50
        if C[i] > ma20 and V[i] >= a50: days.append(m['bars'][i][0])
    S['sigA'] = days
    S['alert_txt'] = '<br>'.join(f'{p:.2f} 要{"升" if p > c else "跌"} {abs(p/c-1)*100:.2f}% {nt}' for p, nt in ((A['cond_px'], '收市高過＋量 ≥ 50 日均量 → 順勢路徑啟動'), (S['reduce'], '收市跌穿 → 減倉'), (S['exitp'], '收市跌穿 → 離場')))
    S['dist_to'] = {k: (v / c - 1) * 100 for k, v in dict(trig=A['trig'], trig_cond=A['cond_px'], zone_hi=B['zone'][1], zone_lo=B['zone'][0], reduce=S['reduce'], exit=S['exitp']).items()}
    S['score'] = sum(d[1] for d in S['dims']) / 45 * 100
    # R4 四項測試（雜訊被掃率按群組定義：60 日、5 日窗口）
    S['sweepB'] = sweep(m, B['risk'] / B['entry']); S['sweepA'] = sweep(m, A['risk'] / A['trig'])
    S['sweepB10'] = sweep(m, B['risk'] / B['entry'], 10); S['sweepA10'] = sweep(m, A['risk'] / A['trig'], 10)
    S['sweepNow'] = sweep(m, (c - B['stop']) / c)
    t1 = False; t2 = S.get('stage_ok', False); t3 = (B['R'][-1] >= 2 or A['R'][-1] >= 2); t4 = (S['sweepB'][0] / S['sweepB'][1] < 0.30)
    S['tests'] = [t1, t2, t3, t4]
    miss = 4 - sum(S['tests'])
    S['tier'] = {0: '標準倉', 1: '降一檔', 2: '降兩檔', 3: '降三檔（＝零倉）', 4: '降四檔（＝零倉）'}[miss]
    # minervini
    c_ = m['closes']
    ma150 = sum(c_[-150:]) / 150; m['ma150'] = ma150
    ma200_21 = sum(c_[-221:-21]) / 200
    S['mv'] = [
        ('收市高於 MA150 及 MA200', m['close'] > ma150 and m['close'] > m['ma200'], f'收市 {m["close"]:.2f}；MA150 {ma150:.2f}；MA200 {m["ma200"]:.2f}'),
        ('MA150 高於 MA200', ma150 > m['ma200'], f'{ma150:.2f} vs {m["ma200"]:.2f}'),
        ('MA200 向上至少 1 個月', m['ma200'] > ma200_21, f'今日 {m["ma200"]:.2f}；21 個交易日前 {ma200_21:.2f}'),
        ('MA50 高於 MA150 及 MA200', m['ma50'] > ma150 and m['ma50'] > m['ma200'], f'MA50 {m["ma50"]:.2f}'),
        ('收市高於 MA50', m['close'] > m['ma50'], f'收市 {m["close"]:.2f} vs MA50 {m["ma50"]:.2f}（{m["d50"]:+.2f}%）'),
        ('高於 52 週低位 ≥30%', m['close'] / S['lo52'] - 1 >= 0.30, f'52 週低 {S["lo52"]:.2f}（{S["lo52_date"]}）；現價高 {(m["close"]/S["lo52"]-1)*100:.2f}%'),
        ('距 52 週高位 ≤25% 以內', m['close'] / S['hi52'] - 1 >= -0.25, f'52 週高 {S["hi52"]:.2f}（{S["hi52_date"]}）；現價低 {abs((m["close"]/S["hi52"]-1)*100):.2f}%'),
        ('相對強度評級 ≥70', None, '缺 RS 百分位數據（自訂 RS 線 ≠ RS 百分位）→ N/A'),
    ]
    ok7 = [x for x in S['mv'] if x[1] is not None]; nok = sum(1 for x in ok7 if x[1])
    bad = '；'.join(x[0] for x in ok7 if not x[1])
    S['mv_line'] = (f'[計算] 可量度 {len(ok7)} 項符合 {nok} 項' + (f'（不符：{bad}）' if bad else '') + f'；較 52 週低 {sg((m["close"]/S["lo52"]-1)*100)}；距 52 週高 {sg((m["close"]/S["hi52"]-1)*100)}（÷高位）。RS 百分位評級 待核實（逐項見附錄第七節）。')
    return S

def mv_table(S):
    rows = []
    for i, (a, ok, d) in enumerate(S['mv'], 1):
        mark = '✔ 符合' if ok else ('N/A' if ok is None else '✘ 不符合')
        rows.append((str(i), a, d, mark))
    return table(['#', 'Minervini 趨勢模板', '實際數據', '符合？'], rows, ['4%', '30%', '52%', '14%'])

def dist(S, key): return S['dist_to'][key]

# ---------------------------------------------------------------- 1-page action card
def build_card(m, S, prev):
    t = S['t']; c = m['close']; A, B = S['A'], S['B']
    d = S['dist_to']
    sc = S['score']
    html = f'''
<div class="hdr"><h1>{t} {S['zh']}｜一頁行動卡</h1><div class="info">分析交易日 {DATE_ZH}｜資料截止 {S['asof']}｜正常收市｜USD｜框架 JLaw × MYT V2.0</div></div>
<div class="bar"></div>
<div class="notice">收市 {c:.2f}（USD）。口徑：距離一律 ÷ 現價 {c:.2f}。▲▼ ＝ 該價位相對現價方向。均線＝收市價 SMA（{S['src_label']} 重算，同 TradingView 圖示一致到兩位小數）。分數由本份重新起算，唔可以同其他股票或上一份 {S['prior']} 直接比較。</div>
<div class="stats"><div><b>{c:.2f}</b><span>收市 {sg(m['chgp'])}</span></div><div><b>{m['volr50']:.1f}%</b><span>成交量÷50 日均量</span></div><div><b>{sg(m['d50'])}</b><span>距 MA50 {m['ma50']:.2f}</span></div><div><b>{sg(m['d200'])}</b><span>距 MA200 {m['ma200']:.2f}</span></div><div><b>{m['atrp']:.2f}%</b><span>ATR14 {m['atr14']:.2f}</span></div></div>
<table class="card"><colgroup><col style="width:4%"><col style="width:15%"><col style="width:81%"></colgroup><tbody>
<tr><td class="cardn">1</td><td class="lbl">評等</td><td><b>今日 {S['rating']}｜{sc:.0f}／100</b>（同上一份並列：{S['prior']}；計法不同，唔作升降）。{S['sub']}。</td></tr>
<tr><td class="cardn">2</td><td class="lbl">今日動作一句</td><td><b>{S['action']}</b></td></tr>
<tr><td class="cardn">3</td><td class="lbl">三條價位（距現價％）</td><td>
 <b>買入觸發</b> {A['cond_px']:.2f} {sg(d['trig_cond'])}（順勢路徑：{A['trig_rule']}）；另一入口：回踩 {B['zone'][0]:.2f}–{B['zone'][1]:.2f}（{sg(d['zone_lo'])}至{sg(d['zone_hi'])}）出現止穩收市<br>
 <b>減倉</b> {S['reduce']:.2f} {sg(d['reduce'])}（收市跌穿）<br>
 <b>離場</b> {S['exitp']:.2f} {sg(d['exit'])}（收市跌穿）</td></tr>
<tr><td class="cardn">4</td><td class="lbl">同上一份最大變化</td><td>{prev['biggest']}</td></tr>
<tr><td class="cardn">5</td><td class="lbl">三個警報價（可入 TradingView）</td><td>{S['alert_txt']}</td></tr>
<tr><td class="cardn">6</td><td class="lbl">唔做嘅代價</td><td>如果 {md()} 收市價 {c:.2f} 照回踩路徑止損 {B['stop']:.2f} 入咗：風險每股 {S['cost_risk']:.2f}（{sg(S['cost_pct'])}）＝ 1R；到 {B['T'][0]:.2f} 只有 {S['cost_R'][0]:.2f}R（{sg(S['cost_pt'][0])}），到主目標 {B['T'][-1]:.2f} 有 {S['cost_R'][-1]:.2f}R（{sg(S['cost_pt'][-1])}）。{prev['cost_tail']}</td></tr>
<tr><td class="cardn">7</td><td class="lbl">今日更正</td><td>{prev['corr']}</td></tr>
</tbody></table>
<div class="notice" style="margin-top:6px">{prev['foot']}</div>
<div style="margin-top:3px;font-size:7pt;color:#888;text-align:right">JLaw V2.0 生成器</div>
'''
    return html

def B_trig_text(S):
    A, B = S['A'], S['B']; d = S['dist_to']
    return (f'① {A["name"]}：{A["trig_rule"]}，觸發價 {A["trig"]:.2f}（{sg(d["trig"])}）；'
            f'② {B["name"]}：回踩 {B["zone"][0]:.2f}–{B["zone"][1]:.2f}（{sg(d["zone_lo"])} 至 {sg(d["zone_hi"])}）出現止穩收市')
