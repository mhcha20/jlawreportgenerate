#!/usr/bin/env python3
"""build.py <TICKER> <DATE> <work.py> [--card] [--out DIR] — 個股 V2.0 報告 PDF（網站版，由 Jlaw-report tools/stockreport/build.py 改）
--card：只出行動卡（work 檔可用 template_card.py，texts 只需 biggest／cost_tail／corr／foot）
work.py 要有 spec(m)、texts(m, S)，網站版（STOCK_STRICT=1）另要 qa(m, S, T)（用 sqa.chk／chk_true 重算寫死數字，≥20 項全過）。
先跑 `python3 prep.py data <TICKER> <DATE>`。輸出：out/<DATE>_<TICKER>_{行動卡,股票分析終極報告,核對附錄}.pdf（有 --out 就複製一份去 DIR）
擋位：今日動作 ≤40 字、朗讀稿字數、行動卡 1 頁、本體報告 ≤10 頁、work 檔冇 TODO、行動卡經 signals.js 解析（日期／評等／分數／三條價位／3 個警報／V2.0 標記）、
STOCK_STRICT=1 時 QA ≥20 項全過＋format_stock.py 格式擋位。任何一項失敗 exit 1。"""
import importlib.util, json, os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
from lib import *
import gen
from gen import *
from gen2 import *
import render, sqa

def die(msg): print('✗', msg, file=sys.stderr); sys.exit(1)

a = sys.argv[1:]
t, date, work = a[0], a[1], os.path.abspath(a[2])
CARD_ONLY = '--card' in a[3:]
OUT = os.path.abspath(a[a.index('--out') + 1]) if '--out' in a else None
STRICT = os.environ.get('STOCK_STRICT') == '1'
os.environ['JL_DATE'] = date
gen.DATE = date
import gen2; gen2.DATE = date
y, mo, d = date.split('-'); wd = '一二三四五六日'[__import__('datetime').date(int(y), int(mo), int(d)).weekday()]
gen.DATE_ZH = gen2.DATE_ZH = f'{date}（{wd}）'
spec_ = importlib.util.spec_from_file_location('work', work); w = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(w)
m = metrics(t); S = w.spec(m); S = plan_numbers(m, S); T = w.texts(m, S)
s_all = json.dumps([S, T], ensure_ascii=False, default=str)
if 'TODO' in s_all: die('work 檔仍有 TODO：' + str(re.findall(r'.{20}TODO.{10}', s_all)[:3]))
if len(S['action']) > 40: die(f'今日動作超過 40 字（{len(S["action"])} 字）：{S["action"]}')
if not CARD_ONLY and not (len(T['script3']) <= 950 and len(T['scriptfull']) <= 3500): die(f'朗讀稿超出字數上限（3 分鐘 {len(T["script3"])}／950；完整 {len(T["scriptfull"])}／3500）')
# 分數同評等要對應（用戶 2026-11-05 決定：每 20 分一級＝九構面平均星數四捨五入）
BANDS = [(90, 5, '強烈買入'), (70, 4, '值得買入'), (50, 3, '觀察'), (30, 2, '不建議'), (0, 1, '避免交易')]
def rating_for(score): return next((st, nm) for lo, st, nm in BANDS if score >= lo)
if STRICT:
    st_need, nm_need = rating_for(S['score'])
    want = '★' * st_need + ' ' + nm_need
    if S.get('stars') != st_need or re.sub(r'\s+', ' ', str(S.get('rating', ''))).strip() != want:
        die(f'評等同分數唔對應：分數 {S["score"]:.1f}／100 應該係「{want}」（★ <30｜★★ 30–49｜★★★ 50–69｜★★★★ 70–89｜★★★★★ ≥90），'
            f'而家寫 rating={S.get("rating")!r}、stars={S.get("stars")}。照分數改 rating／stars；如果覺得評等先啱，就逐格覆核九構面星數（分數由星數計），唔好兩樣唔夾。')
    # 價位次序（用戶 2026-11-06 要求）：減倉線 ≤ 回踩區下限；離場線 ≤ 減倉線；回踩止損 ≤ 離場線（唔可以喺回踩區入面就要減倉）
    zlo, zhi = sorted(S['B']['zone'])[:2]; red, ext, bstop = S.get('reduce'), S.get('exitp'), S['B'].get('stop')
    bad = [x for x, ok in ((f'減倉線 {red:.2f} 喺回踩區 {zlo:.2f}–{zhi:.2f} 入面或上面（要 ≤ 回踩區下限 {zlo:.2f}）', red <= zlo + 1e-9),
                           (f'離場線 {ext:.2f} 高過減倉線 {red:.2f}（要離場線 ≤ 減倉線）', ext <= red + 1e-9),
                           (f'回踩止損 {bstop:.2f} 高過離場線 {ext:.2f}（要止損 ≤ 離場線）', bstop <= ext + 1e-9)) if not ok]
    if bad and len(str(S.get('level_note', ''))) < 20:
        die('價位次序唔夾：' + '；'.join(bad) + '。重訂嘅價位照呢個次序改（回踩區下限 ≥ 減倉 ≥ 離場 ≥ 止損）；'
            '如果係未失效嘅承襲價本身唔夾（規則唔准改），就照用承襲值，喺 S["level_note"] 寫明邊條係承襲、點解唔夾（≥20 字）。')
    if not hasattr(w, 'qa'): die('work 檔要有 qa(m, S, T)：用 sqa.chk()／chk_true() 重算 spec／texts 入面寫死嘅數字（52 週高低、均線、ATR、量比、各價位距離％、R 值、升跌％、計數同日期序列）')
    w.qa(m, S, T)
    nq, nbad = sqa.qa_report()
    if nq < 20: die(f'QA 檢查數只有 {nq}，太少（≥20，應覆蓋寫死數字）')
    if nbad: die(f'QA 失敗 {nbad} 項（見上面「QA 失敗」行）')
os.makedirs('out', exist_ok=True)
names = {'card': f'{date}_{t}_行動卡', 'rep': f'{date}_{t}_股票分析終極報告', 'app': f'{date}_{t}_核對附錄'}
open(f'{names["card"]}.html', 'w').write(page(f'{t} 一頁行動卡', build_card(m, S, T), S))
jobs = [dict(html=f'{names["card"]}.html', pdf=f'out/{names["card"]}.pdf', footer=f'{t} 一頁行動卡 · {date}')]
if not CARD_ONLY:
    open(f'{names["rep"]}.html', 'w').write(page(f'{t} 本體報告', build_report(m, S, T), S))
    open(f'{names["app"]}.html', 'w').write(page(f'{t} 核對附錄', build_appendix(m, S, T), S))
    jobs += [dict(html=f'{names["rep"]}.html', pdf=f'out/{names["rep"]}.pdf', footer=f'{t} 本體報告 · {date}'),
             dict(html=f'{names["app"]}.html', pdf=f'out/{names["app"]}.pdf', footer=f'{t} 核對附錄 · {date}')]
for j in jobs:
    if re.search(r'\bNaN\b|\binf\b', open(j['html'], encoding='utf-8').read()): die(f'{j["html"]} 有 NaN／inf')
render.render(jobs)
res = {}
for j in jobs:
    n = subprocess.run(['pdfinfo', j['pdf']], capture_output=True, text=True).stdout
    res[j['pdf']] = int([l for l in n.splitlines() if l.startswith('Pages')][0].split()[1])
def _vis(x):   # 欄位可見字數（去 HTML 標籤）
    if isinstance(x, dict): return sum(_vis(v) for v in x.values())
    if isinstance(x, (list, tuple)): return sum(_vis(v) for v in x)
    return len(re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', str(x)))) if isinstance(x, str) else 0
def _cut_hint(pages, limit):
    import inspect
    src = inspect.getsource(gen2.build_report)   # 只計本體報告用到嘅欄位（朗讀稿、附錄欄位刪咗都唔會少頁）
    keys = set(re.findall(r"T\[['\"](\w+)['\"]\]", src)) | set(re.findall(r"T\.get\(['\"](\w+)['\"]", src))
    body = {k: v for k, v in T.items() if k in keys}
    tot = sum(_vis(v) for v in body.values()); need = int(tot * (pages - limit) / pages) + 300
    top = sorted(((k, _vis(v)) for k, v in body.items()), key=lambda kv: -kv[1])[:10]
    return (f'。本體報告用到嘅 texts 合共約 {tot:,} 字（唔計朗讀稿同附錄欄位），要刪大約 {need:,} 字先夠（一次刪夠，唔好每次刪少少）；本體最長嘅欄位：'
            + '、'.join(f'{k} {n:,}' for k, n in top) + '。刪重複嘅敘述，唔好刪到格式擋位最低字數以下')
if res[jobs[0]['pdf']] != 1: die(f'行動卡 {res[jobs[0]["pdf"]]} 頁，要 1 頁：行動卡各格寫精簡啲（biggest／cost_tail／corr／foot 等）')
if not CARD_ONLY and res[jobs[1]['pdf']] > 10: die(f'本體報告 {res[jobs[1]["pdf"]]} 頁，超過 10 頁' + _cut_hint(res[jobs[1]['pdf']], 10))
# 行動卡用 Jlaw-report 網站同一個 signals.js 解析（買賣訊號／回測靠佢）
sig = None
try:
    p = subprocess.run(['node', os.path.join(HERE, 'sig', 'sigcheck.js'), jobs[0]['pdf']], capture_output=True, text=True, timeout=120)
    if p.returncode == 0: sig = json.loads(p.stdout.strip().splitlines()[-1])
    else: print('⚠ signals.js 解析失敗：', p.stderr[-300:], file=sys.stderr)
except Exception as e: print('⚠ 跑唔到 signals.js：', e, file=sys.stderr)
if sig is None and STRICT: die('行動卡解析唔到（signals.js）：檢查第 1–7 格標題同字眼')
if sig:
    bad = []
    if sig['date'] != date: bad.append(f'分析交易日解析成 {sig["date"]!r}（要 {date}）')
    if sig['gen'] != 'v2': bad.append('冇 V2.0 生成器標記')
    if not sig['rating'] or not sig['stars']: bad.append('評等（★＋固定字眼）解析唔到：只可用 強烈買入／值得買入／買入／觀察／不建議／避免交易')
    if sig['score'] is None: bad.append('分數（xx／100）解析唔到')
    for k, nm in (('buy', '買入觸發'), ('trim', '減倉'), ('stop', '離場')):
        if k not in (sig['levels'] or {}): bad.append(f'第 3 格「{nm} 價位 ▲▼x.xx%」解析唔到')
    if sig['alerts'] != 3: bad.append(f'第 5 格警報價解析到 {sig["alerts"]} 個（要 3 個）')
    if not sig['flat'] or not sig['held']: bad.append('第 2 格今日動作要寫「未持倉：…。已持倉：…。」')
    if bad: die('行動卡 signals.js 解析有問題：' + '；'.join(bad) + '\n解析結果：' + json.dumps(sig, ensure_ascii=False))
if STRICT and CARD_ONLY:   # 只出行動卡：照樣擋行動卡各格篇幅（用戶 2026-11-08 加呢個模式）
    import format_stock
    errs = format_stock.check_card(S, T)
    if errs: die('行動卡格式未跟足範本（' + str(len(errs)) + ' 項），逐項補返再提交：\n- ' + '\n- '.join(errs))
if STRICT and not CARD_ONLY:
    import format_stock
    errs = format_stock.check(S, T, {k: res[jobs[i]['pdf']] for i, k in enumerate(['card', 'rep', 'app'][:len(jobs)])})
    if errs: die('格式未跟足範本（' + str(len(errs)) + ' 項），逐項補返再提交：\n- ' + '\n- '.join(errs))
pdfs = [j['pdf'] for j in jobs]
if OUT:
    os.makedirs(OUT, exist_ok=True); pdfs = []
    for j in jobs:
        dst = os.path.join(OUT, os.path.basename(j['pdf'])); shutil.copy(j['pdf'], dst); pdfs.append(dst)
print(json.dumps({'ticker': t, 'date': date, 'score': round(S['score'], 1), 'rating': S['rating'], 'tier': S['tier'], 'action': S['action'],
                  'pages': {os.path.basename(k): v for k, v in res.items()}, 'pdfs': pdfs, 'qa_work': len(sqa.QA),
                  'signals': ({'flat': sig['cls']['flat']['label'], 'held': sig['cls']['held']['label'], 'levels': sig['levels']} if sig else None)}, ensure_ascii=False))
