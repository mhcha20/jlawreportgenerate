# 亞洲（香港／日本／韓國）大盤報告 work 檔範本：將所有 'TODO' 同 0 換成當日截圖／行情得出嘅內容。
# 只提供結構（欄位名同類型），冇任何分析內容。build.py 會載入 spec(m)、texts(m, S)、qa(m, S, T)。
# m＝alib.Market：m.core（主指數 ETF 代號 list）、m.sectors（[(代號, 名)]）、m.lead（基準 ETF）、m[t].c／.pc／.chgp／.ma(50)／.v50()／.vr()／
#   .candle()／.dist_days()…；m.idx['HSI']（Yahoo 指數，可能冇）；m.date／m.pdate；m.name(t)；SHOT_OF[t]＝截圖名（02800 → 2800）。
# 價錢用 F(x)（自動小數位）；百分比 P(x)（2 位）。數字寫入文字時一律用 f-string 由 m／S 取值；寫死嘅數字要喺 qa() 重算。
from alib import *      # P N AR F FD CALC INF CHART EXT tag box table lvl loc_hk chk chk_true pct clv md wd PR CORE SECTORS SHOT_OF SHOT_TICKERS …

BASIS = 'incl'          # 50 日均量口徑：'incl' 含當日；'excl' 不含當日。報告會自動聲明

def spec(m):
    """圖表讀數（逐張睇圖得出，睇唔清寫 None，唔好估）＋ 價位清單 ＋ 後設。亞洲截圖係 TradingView 完整圖表頁：冇均線、冇 RSI。"""
    rd = {t: {'c': 0, 'pc': None, 'vol_m': None} for t in CORE + [x for x, _ in SECTORS]}   # c 會自動同行情核對；pc 睇唔到就 None
    return {
        'meta': {'ai': 'TODO', 'ai_note': 'TODO', 'mode': 'TODO', 'analysis_date': 'TODO', 'sources': 'TODO',
                 'shot_utc': 'YYYY-MM-DD HH:MM', 'shot_src': 'TODO（Drive 檔案建立時間／圖面 UTC 鐘）', 'ocr_used': False},
        'viewed': [],     # 已睇圖嘅截圖名：要齊 SHOT_TICKERS，build 會擋
        'readings': rd,   # key＝行情代號（02800 等）
        # 指數截圖讀數（key＝截圖名：HSI／HSTECH／HSCEI／NI225／TOPIX／KOSPI／KOSDAQ）；Yahoo 有嘅會自動核對
        'index_readings': {x['idx']: {'c': 0, 'pc': None} for x in PR['core']},
        'vol': ({'o': None, 'h': None, 'l': None, 'c': 0, 'pc': None, 'hist': []} if PR.get('vol') else None),   # 只有香港（VHSI）
        'breadth': [{'name': '升跌家數', 'scope': 'TODO', 'cur': None, 'note': 'TODO（上網核實到先填數字，附來源；冇就寫缺）'},
                    {'name': '新高／新低數目', 'scope': 'TODO', 'cur': None}],
        'macro': [{'name': x['name'], 'c': 0, 'chg': 'TODO', 'open': True, 'note': 'TODO'} for x in PR['macro']],
        # 價位清單：t＝行情代號（或 m.idx 嘅指數名）；key＝ma10|ma20|ma50|ma200|h52|l52|h|l|pc（自動取值）；或寫 v=價位
        'levels': [{'name': 'TODO', 't': CORE[0], 'key': 'ma50', 'status': 'TODO', 'cls': 'g'},
                   {'name': 'TODO', 't': CORE[0], 'v': 0, 'status': 'TODO', 'cls': ''}],
    }

def texts(m, S):
    row5 = ['TODO'] * 5
    return {
        'inherit_note': 'TODO（承襲上一份報告嘅說明、紀律聲明；第一份就寫明冇上一份）',
        'sum_boxes': [('TODO（最重要一件事）', 'hi'), ('TODO（第二件事）', 'hi')],
        'sum_rows': [['市況分類', 'TODO'], ['處置指示', 'TODO'], ['前日主要變化', 'TODO'], ['最強環節', 'TODO'], ['最弱環節', 'TODO'], ['關鍵風險', 'TODO']],
        'src_rows': [['圖表讀數', 'TODO（截圖列表、直接睇圖冇用文字辨識）']],
        'verify_box': 'TODO（SMA 由行情重算、收市價交叉核實…）',
        'gaps': [['TODO 缺項', 'TODO 說明同影響']],
        'divergence_extra': [],
        'idx_notes': {},                                   # {指數截圖名: 附加說明}
        'cmp_notes': {t: 'TODO' for t in CORE}, 'candle_notes': {t: '' for t in CORE},
        'sync_box': 'TODO（主指數同步性）',
        'ma_notes': {t: 'TODO' for t in CORE}, 'ma_box': 'TODO（結構觀察）',
        'events': [[f'<b>{SHOT_OF[t]}</b>', 'TODO', 'TODO', 'TODO'] for t in CORE],
        'levels_box': 'TODO',
        'vol_notes': {t: '' for t in CORE}, 'vol_box': 'TODO',
        'dist_def_note': '', 'dist_box': 'TODO',
        'vol_close_note': '', 'vol_range_note': '', 'vol_hist_note': '',   # 波動指數（香港 VHSI）
        'vix_para': 'TODO（波動指數或振幅觀察同價格配合）',
        'breadth_box': 'TODO（廣度資料來源同可靠度）',
        'breadth_qa': [['指數升跌是否得到多數股票支持？', 'TODO'], ['高於 50 日及 200 日線比例有否改善？', 'TODO'],
                       ['升跌股數及新高／新低是否支持指數方向？', 'TODO'], ['是否出現指數與廣度背離？', 'TODO'], ['波動指數（或振幅）嘅水平、變化及與價格走勢嘅配合？', 'TODO']],
        'breadth_limits': 'TODO',
        'sector_box': 'TODO',
        'sector_qa': [['邊啲板塊／權重股領漲、落後或轉弱？', 'TODO'], ['當日走勢是否改變中期走勢？', 'TODO'], ['科技、半導體、金融、消費及防守板塊是否同步？', 'TODO'],
                      ['領漲是否擴散，還是集中在少數權重股？', 'TODO'], ['邊啲板塊值得優先交由群友作個股研究？', 'TODO']],
        'sector_flag': '',
        'catalysts_box': 'TODO',
        'past_events': [row5],                      # [事件日期, 事件及來源, 已知市場反應, 可能影響, 仍待確認]
        'past_note': '',
        # (事件, 日期 YYYY-MM-DD, 'HH:MM'（當地時間）／'ET HH:MM'（美東）／None＝時間未核實, 預期／前值, 關注點[, cls])；香港時間自動換算
        'next_week': [('TODO', m.date, None, 'TODO', 'TODO')],
        'next_week_note': '', 'next_week_foot': 'TODO（日程以哪個來源為準；未核實日程唔補造）',
        # 'jlaw_html': 選填；有 J Law 觀點材料而且有講到本市場（或整體風險胃納）先寫：材料清單、風險胃納、逐項表（J Law 講法｜日期｜對今日數據核實｜一致／唔一致／未能核實）；冇關就刪走呢個 key
        # 'action_rows': 條件式行動清單 [[#, 項目, 條件／做法], …]，非買賣建議；每隻主指數 ETF 各一項
        'history_html': 'TODO（有充分證據才做；不足就寫明無法比較）',
        'regime_rows': [['<b>短線</b>', 'TODO', 'TODO', 'TODO'], ['<b>中期</b>', 'TODO', 'TODO', 'TODO'], ['<b>長期</b>', 'TODO', 'TODO', 'TODO']],
        'regime_box': 'TODO（總結分類、較前日有冇改變、市況標籤唔等於買賣許可）',
        'scenario_rows': [['<b>A 轉強延續</b>', 'TODO', 'TODO', 'TODO'], ['<b>B 震盪或分化持續</b>', 'TODO', 'TODO', 'TODO'], ['<b>C 轉弱或反彈失敗</b>', 'TODO', 'TODO', 'TODO']],
        'scenario_detail': [['A', 'TODO', 'TODO', 'TODO', 'TODO'], ['B', 'TODO', 'TODO', 'TODO', 'TODO'], ['C', 'TODO', 'TODO', 'TODO', 'TODO']],
        'next_rows': [['①', 'TODO', 'TODO', 'TODO']],
        'verify_rows': [['TODO', 'TODO']],
        'open_q': [],
        'group_summary': 'TODO（可直接貼群組嘅簡短摘要：主要判斷、關鍵價位、重要資料限制）',
    }

def qa(m, S, T):
    """重算頁內寫死嘅數字。每項用 chk(名, 報告值, 獨立重算值[, 容差]) 或 chk_true(名, 條件) 登記；build 要求 ≥20 項、全部通過。
    例：t = m.core[0]; chk(f'{t} 距 MA50 %', 4.75, pct(m[t].c, m[t].ma(50)), 0.005)"""
    pass
