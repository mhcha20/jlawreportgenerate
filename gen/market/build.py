#!/usr/bin/env python3
"""market/build.py DATE work.py [--out DIR] — 每日美股大盤報告 PDF
前置：python3 market/prep.py DATE（行情）；work.py 要有 spec(m)、texts(m, S)、qa(m, S, T)（見 market/template_work.py）。
輸出：<out>/<DATE>_美股大盤分析_JW框架_Claude核實版.pdf（默認 tools/stockreport/out/）。
擋位：頁數 ≤ 16、work 檔無 TODO、19 張截圖都已睇圖、圖面讀數對行情、work.qa() 逐項重算、PDF 文字回查（qa.py）。任何一項失敗 exit 1，唔好上載。"""
import importlib.util, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(1, ROOT); os.chdir(ROOT)
from mlib import *
import report, qa as qamod
MAX_PAGES = 16
REQUIRED_T = ['inherit_note', 'sum_boxes', 'sum_rows', 'events', 'breadth_qa', 'sector_qa', 'past_events', 'next_week', 'history_html',
              'regime_rows', 'regime_box', 'scenario_rows', 'scenario_detail', 'next_rows', 'verify_rows', 'group_summary']
REQUIRED_S = ['meta', 'readings', 'viewed', 'vix', 'breadth', 'levels']

def die(msg): print('✗', msg, file=sys.stderr); sys.exit(1)

def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    date, work = a[0], os.path.abspath(a[1])
    out = os.path.abspath(a[a.index('--out') + 1]) if '--out' in a else os.path.join(ROOT, 'out')
    os.makedirs(out, exist_ok=True)
    sp = importlib.util.spec_from_file_location('mwork', work); w = importlib.util.module_from_spec(sp); sp.loader.exec_module(w)
    m = Market(date, basis=getattr(w, 'BASIS', 'incl'))
    S = w.spec(m); T = w.texts(m, S)
    for k in REQUIRED_S:
        if k not in S: die(f'spec 缺 {k}')
    for k in REQUIRED_T:
        if k not in T: die(f'texts 缺 {k}')
    # 截圖：19 張都要睇圖，唔准文字辨識
    miss = [t for t in SHOT_TICKERS if t not in S['viewed']]
    if miss: die(f'S["viewed"] 未列出已睇圖嘅截圖：{miss}（逐張睇圖先填；缺圖就停，唔好湊）')
    if S['meta'].get('ocr_used'): die('用咗文字辨識讀截圖：要改為睇圖像')
    s_all = json.dumps([S, T], ensure_ascii=False, default=str)
    if 'TODO' in s_all: die('work 檔仍有 TODO：' + str(re.findall(r'.{20}TODO.{10}', s_all)[:3]))
    html = report.build_html(m, S, T)
    if re.search(r'\bNaN\b|\bnan\b|\binf\b', html): die('HTML 有 NaN／inf')
    # work 檔自己嘅重算 QA（寫死數字／計數／日期序列）
    if not hasattr(w, 'qa'): die('work 檔要有 qa(m, S, T)：重算頁內寫死嘅數字、計數、「連續／最大／最小」斷言，用 mlib.chk()／chk_true() 登記')
    w.qa(m, S, T)
    nq, nbad = qa_report()
    if nq < 20: die(f'QA 檢查數只有 {nq}，太少（≥20，應覆蓋寫死數字）')
    if nbad: die(f'QA 失敗 {nbad} 項')
    wdz = wd(date); title = f'美股大盤分析 {date}（{wdz}）收市'
    fonts = ''.join(f'<link rel="stylesheet" href="file://{ROOT}/node_modules/@fontsource/noto-sans-tc/{x}.css">' for x in ('chinese-traditional-400', 'chinese-traditional-700', 'latin-400', 'latin-700'))
    doc = f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>{title}</title>{fonts}<link rel="stylesheet" href="file://{ROOT}/style.css"></head><body>{html}</body></html>'
    name = f'{date}_美股大盤分析_JW框架_' + os.environ.get('MARKET_SUFFIX', 'Claude核實版')   # 網站用 Grok 出時＝Grok核實版
    hp, pp = os.path.join(out, name + '.html'), os.path.join(out, name + '.pdf')
    open(hp, 'w', encoding='utf-8').write(doc)
    jf = os.path.join(out, f'jobs_market_{date}.json')
    json.dump([dict(html=hp, pdf=pp, footer=f'{title}｜JW 大盤分析指令 共用補充版 V1.0｜不構成投資建議')], open(jf, 'w'), ensure_ascii=False)
    import render; render.render(json.load(open(jf)))
    info = subprocess.run(['pdfinfo', pp], capture_output=True, text=True).stdout
    pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    n, bad = qamod.run(date, pp)
    print(json.dumps({'date': date, 'pdf': pp, 'pages': pages, 'qa_work': nq, 'qa_pdf': n, 'qa_pdf_fail': len(bad)}, ensure_ascii=False))
    for b in bad: print('PDF 文字回查失敗：', b, file=sys.stderr)
    if bad: die('PDF 文字回查有數字對唔上')
    lim = MAX_PAGES + (4 if T.get('jlaw_html') else 0)   # 加 J Law 觀點一節可多 4 頁
    if pages > lim: die(f'{pages} 頁，超過上限 {lim}')

if __name__ == '__main__': main()
