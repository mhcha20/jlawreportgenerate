"""format_stock.py — 個股報告硬性格式擋位（STOCK_STRICT=1，build.py 出完三份 PDF 後跑）。
標準＝用戶 2026-11-05 指定嘅範本 2026-10-30 ESTC（行動卡 1 頁／本體報告 9 頁／核對附錄 4 頁）：每格要寫到範本咁詳細，
門檻約為範本篇幅嘅六至七成。回傳錯誤 list（空＝通過），每條寫明欄位、要求、實際，方便 AI 照改。改門檻改呢個檔。"""
import os, re


def _txt(x):
    if isinstance(x, (list, tuple)): return ' '.join(_txt(i) for i in x)
    if isinstance(x, dict): return ' '.join(_txt(v) for v in x.values())
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(x if x is not None else ''))).strip()


def _n(x): return len(_txt(x))


def check_card(S, T):
    """只出行動卡（build.py --card）用：行動卡各格＋九構面理由"""
    err = []
    def need(ok, msg):
        if not ok: err.append(msg)
    def length(key, lim, src=T, label=None):
        need(_n(src.get(key)) >= lim, f'{label or key} 太短（{_n(src.get(key))} 字，要 ≥{lim}，照範本寫具體數字同理由）')
    def rows(key, n_min, each=0, col=None):
        rr = T.get(key) or []
        need(len(rr) >= n_min, f'{key} 要 ≥{n_min} 項（而家 {len(rr)}）')
        if each:
            for i, r in enumerate(rr):
                v = r[col] if (col is not None and isinstance(r, (list, tuple)) and len(r) > col) else r
                need(_n(v) >= each, f'{key}[{i}] 太短（{_n(v)} 字，要 ≥{each}）：「{_txt(v)[:30]}」')

    # 行動卡（範本每格都有具體數字）
    length('sub', 35, S, "S['sub']（第 1 格評等補充）")
    length('biggest', 150, label='biggest（第 4 格同上一份最大變化）')
    length('cost_tail', 80, label='cost_tail（第 6 格尾句）')
    length('corr', 40, label='corr（第 7 格今日更正）')
    length('foot', 60, label='foot（卡底證據層級／下次財報）')
    need('回踩區入場（主目標' in _txt(T.get('cost_tail')) or '回踩區入場（主目標' in _txt(T), '第 6 格要有固定句「回踩區入場（主目標 x.xxR）」')

    # 九構面理由（範本每格一句連數字，約 40–70 字）
    for d in S.get('dims') or []:
        need(_n(d[2]) >= 30, f'九構面「{d[0]}」理由太短（{_n(d[2])} 字，要 ≥30，要有數字同升降原因）')

    return err


def check(S, T, pages):
    err = []
    def need(ok, msg):
        if not ok: err.append(msg)
    def length(key, lim, src=T, label=None):
        need(_n(src.get(key)) >= lim, f'{label or key} 太短（{_n(src.get(key))} 字，要 ≥{lim}，照範本寫具體數字同理由）')
    def rows(key, n_min, each=0, col=None):
        rr = T.get(key) or []
        need(len(rr) >= n_min, f'{key} 要 ≥{n_min} 項（而家 {len(rr)}）')
        if each:
            for i, r in enumerate(rr):
                v = r[col] if (col is not None and isinstance(r, (list, tuple)) and len(r) > col) else r
                need(_n(v) >= each, f'{key}[{i}] 太短（{_n(v)} 字，要 ≥{each}）：「{_txt(v)[:30]}」')

    # 頁數（範本：本體 9 頁、附錄 4 頁）
    need(pages.get('rep', 0) >= int(os.environ.get('STOCK_MIN_REPORT_PAGES', '9')), f'本體報告只有 {pages.get("rep")} 頁（範本 9 頁，要 ≥9、≤10）：各部分照範本寫足')
    need(pages.get('app', 0) >= int(os.environ.get('STOCK_MIN_APPENDIX_PAGES', '3')), f'核對附錄只有 {pages.get("app")} 頁（範本 4 頁，要 ≥3）：口徑、對照差異、更正清單、資料來源要寫足')

    err += check_card(S, T)

    # 本體報告各部分
    length('oneliner', 120, label='oneliner（第一頁一句話結論）')
    for k in ('p1a', 'p1b', 'p1c'):
        v = T.get(k) or ('', '')
        need(_n(v[0]) >= 45, f'{k}（第一部分大市三問）表現欄太短（{_n(v[0])} 字，要 ≥45）')
        need(_n(v[1]) >= 10, f'{k} 判斷欄太短（{_n(v[1])} 字，要 ≥10）')
    length('stage_txt', 120, label='stage_txt（第二部分生命週期）')
    length('hhhl', 80, label='hhhl（Higher High／Higher Low）')
    length('mom', 50, label='mom（Momentum）')
    rows('vol_rows', 6, 40, col=1)
    length('pattern', 40, label='pattern（目前屬於）')
    rows('pattern_notes', 2, 30)
    rows('sr_rows', 5, 6, col=2)
    rows('pb', 3, 35); rows('bo', 3, 35)
    rows('canslim', 7)
    rows('fund_rows', 6)
    for i, r in enumerate(T.get('fund_rows') or []):
        need(sum(1 for c in r if _n(c) >= 2) >= 3, f'fund_rows[{i}] 要至少 3 格有內容（項目／最近一季／比較／意義）')
    rows('risk', 5, 15)
    for k, lim in (('analyst_line', 40), ('smart_line', 40), ('sector_line', 40), ('canslim_line', 30), ('mv_line', 0)):
        if lim: length(k, lim)
    for k, lim in (('zone_lo_def', 10), ('zone_hi_def', 10), ('rrr_note', 40), ('r3_note', 20), ('stage_test', 30), ('swing_only', 15),
                   ('earn_line', 20), ('f1_note', 30), ('f2_interp', 40), ('plan_line', 60), ('next3_line', 40), ('vsprior', 60), ('setup', 15)):
        length(k, lim)
    length('flat', 50, label='flat（強制欄位 3 未持倉）'); length('held', 30, label='held（強制欄位 3 已持倉）')
    rows('next3', 3, 12)
    rows('keep', 4, 15); rows('noup', 4, 15)
    for k in ('q1', 'q2', 'q3', 'q4'): length(k, 25, label=f'{k}（最後四問）')
    rows('open', 2, 30)
    # 朗讀稿（範本：3 分鐘 ≤950 字、完整 ≤3,500 字，要寫到接近上限）
    length('script3', 550, label='script3（3 分鐘朗讀稿）'); length('scriptfull', 1800, label='scriptfull（完整朗讀稿）')
    # 核對附錄
    rows('thr', 5); rows('caliber', 4, 25); rows('conflicts', 4); rows('sources', 4, 15); rows('smart', 4, 20)
    length('corr_html', 120, label='corr_html（附錄更正清單）')
    return list(dict.fromkeys(err))
