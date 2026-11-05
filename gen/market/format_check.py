"""format_check.py — 網站版硬性格式擋位（FORMAT_STRICT=1 時 build.py 會跑）：
以 2026-10-30「美股大盤分析_JW框架_Claude核實版」為標準，每一節要有齊、行數同篇幅唔可以少過範本水平。
回傳錯誤 list（空＝通過）；每條錯誤寫明邊個欄位、要求、實際，方便 AI 照改。"""
import os, re

def _txt(x):
    if isinstance(x, (list, tuple)): return ' '.join(_txt(i) for i in x)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(x or ''))).strip()

def _n(x): return len(_txt(x))

def check(S, T, pages, jlaw_required=False):
    err = []
    def need(ok, msg):
        if not ok: err.append(msg)
    min_pages = int(os.environ.get('FORMAT_MIN_PAGES') or (10 if jlaw_required else 9))
    need(pages >= min_pages, f'頁數 {pages} 少過範本水平（要 ≥{min_pages} 頁）：各節敘述要寫到 10/30 範本咁詳細')
    need(_n(T.get('inherit_note')) >= 60, 'inherit_note（頁首說明）太短：要寫明本份點做（先睇 19 張原圖、同行情重算、冇承接舊報告嘅派發日數／門檻）')
    boxes = T.get('sum_boxes') or []
    need(len(boxes) >= 2, f'sum_boxes 要 ≥2 段（而家 {len(boxes)}）')
    for i, b in enumerate(boxes):
        need(_n(b[0] if isinstance(b, (list, tuple)) else b) >= 90, f'sum_boxes[{i}] 太短（{_n(b[0] if isinstance(b, (list, tuple)) else b)} 字，要 ≥90）：要有三指數升跌％同收市、板塊升跌家數、均線位置、量比、VIX 等具體數字')
    rows = T.get('sum_rows') or []
    need(len(rows) >= 6, f'sum_rows 要 6 行（市況分類／處置指示／前日主要變化／最強環節／最弱環節／關鍵風險），而家 {len(rows)}')
    for r in rows:
        k, v = (r[0], r[1]) if len(r) > 1 else (r[0], '')
        lim = 20 if '處置' in _txt(k) else 45
        need(_n(v) >= lim, f'sum_rows「{_txt(k)}」太短（{_n(v)} 字，要 ≥{lim}）：要分短線／中期／長期或列具體數字')
    need(len(T.get('gaps') or []) >= 3, f'gaps（缺項）要逐項申報 ≥3 項（而家 {len(T.get("gaps") or [])}）')
    for k in ('breadth_qa', 'sector_qa'):
        for q in T.get(k) or []:
            need(_n(q[1]) >= 35, f'{k}「{_txt(q[0])[:20]}」答案太短（{_n(q[1])} 字，要 ≥35，要有數字）')
    for k, lim in (('sync_box', 40), ('ma_box', 40), ('vol_box', 40), ('dist_box', 40), ('vix_para', 60), ('breadth_box', 40),
                   ('breadth_limits', 30), ('sector_box', 40), ('catalysts_box', 40), ('levels_box', 30), ('regime_box', 80),
                   ('history_html', 50), ('next_week_foot', 20)):
        need(_n(T.get(k)) >= lim, f'{k} 太短（{_n(T.get(k))} 字，要 ≥{lim}）')
    pe = T.get('past_events') or []
    need(len(pe) >= 5, f'past_events 要逐日列過去 5 個交易日（≥5 行，冇已核實催化劑都要寫「無單一已核實催化劑」＋當日 SPY／QQQ 升跌），而家 {len(pe)}')
    nw = T.get('next_week') or []
    need(len(nw) >= 4, f'next_week 未來一星期事件要 ≥4 項（經濟數據、重要業績、聯儲局講話等，附來源），而家 {len(nw)}')
    for k, n_ in (('regime_rows', 3), ('scenario_rows', 3), ('scenario_detail', 3)):
        rr = T.get(k) or []
        need(len(rr) >= n_, f'{k} 要 {n_} 行（而家 {len(rr)}）')
        for r in rr:
            for c in r[1:]:
                need(_n(c) >= 8, f'{k}「{_txt(r[0])}」有格太短：「{_txt(c)}」（每格要寫具體價位／條件）')
    need(len(T.get('next_rows') or []) >= 5, f'next_rows（下一交易日追蹤）要 ≥5 項（而家 {len(T.get("next_rows") or [])}）')
    need(len(T.get('verify_rows') or []) >= 4, f'verify_rows（需要核實）要 ≥4 項（而家 {len(T.get("verify_rows") or [])}）')
    ar = T.get('action_rows') or []
    need(len(ar) >= 3, f'action_rows（條件式行動清單，非買賣建議）要 ≥3 項（而家 {len(ar)}）：SPY／QQQ／IWM 各一項，寫收市條件同價位')
    need(_n(T.get('group_summary')) >= 150, f'group_summary（可直接轉貼嘅簡短摘要）太短（{_n(T.get("group_summary"))} 字，要 ≥150）')
    if jlaw_required:
        jh = T.get('jlaw_html') or ''
        need(_n(jh) >= 1200, f'jlaw_html（J Law 觀點對照及逐項核實）太短或冇寫（{_n(jh)} 字，要 ≥1200）：有提供 J Law 材料就一定要寫，格式照範本')
        need(jh.count('<tr') >= 6, f'jlaw_html 逐項表要 ≥5 項講法（而家 {max(jh.count("<tr") - 1, 0)}）')
    return list(dict.fromkeys(err))
