# 大盤報告 work 檔範本：複製成 work/market_<DATE>.py，將所有 'TODO' 同 0 換成當日截圖／行情得出嘅內容。
# 只提供結構（欄位名同類型），冇任何分析內容。build.py 會載入 spec(m)、texts(m, S)、qa(m, S, T)。
# m＝mlib.Market：m['SPY'].c／.pc／.chgp／.ma(50)／.v50()／.vr()／.candle()／.dist_days()…；m.date／m.pdate。
# 數字寫入文字時一律用 f-string 由 m／S 取值（唔好憑印象寫死）；寫死嘅數字／計數／日期序列要喺 qa() 重算。
from mlib import *      # P N AR CALC INF CHART EXT tag box table lvl et_hk chk chk_true pct clv md wd …

BASIS = 'incl'          # 50 日均量口徑：'incl' 含當日（10/19–10/21 報告口徑）；'excl' 不含當日。報告會自動聲明

def spec(m):
    """圖表讀數（逐張睇圖得出，睇唔清寫 None／缺，唔好估）＋ 價位清單 ＋ 後設。"""
    rd = {}   # 每個 INDEXES／SECTORS 代號一項：{'o','h','l','c','pc','vol_m'(圖面量，百萬股),'rsi','ma':{'10':..,'20':..,'50':..,'200':..},'post'(盤後價，圖面冇就唔填)}
    for t in INDEXES + [x for x, _ in SECTORS]:
        rd[t] = {'c': 0, 'pc': 0, 'rsi': 0}      # c／pc 會自動同行情核對（差 >0.0051 即失敗）
    rd['SPY'].update({'o': 0, 'h': 0, 'l': 0, 'vol_m': 0, 'ma': {'10': 0, '20': 0, '50': 0, '200': 0}, 'post': 0})
    return {
        'meta': {'ai': 'TODO', 'ai_note': 'TODO', 'mode': 'TODO', 'analysis_date': 'TODO', 'sources': 'TODO',
                 'shot_utc': 'YYYY-MM-DD HH:MM', 'shot_src': 'TODO（Drive 檔案建立時間／圖面 UTC 鐘）', 'post_time': 'TODO', 'ocr_used': False},
        'viewed': [],     # 已睇圖嘅截圖代號：要齊 SHOT_TICKERS（IWM VIX SPY QQQ SOX 11 板塊 DXY GC1! US10Y），build 會擋
        'readings': rd,
        'sox': {'o': 0, 'h': 0, 'l': 0, 'c': 0, 'pc': 0, 'ret5': None, 'rsi': None},          # SOX 指數：Yahoo 無，只有圖面
        'vix': {'o': 0, 'h': 0, 'l': 0, 'c': 0, 'pc': 0, 'h52': 0, 'hist': [0, 0, 0]},       # chg（圖面升跌）有填會做算術核對
        'breadth': [{'name': 'S5TH 高於 200 日線比率', 'scope': 'S&amp;P 500 成分股', 'date': 'TODO', 'prev': 0, 'cur': 0, 'note': 'TODO'},
                    {'name': '升跌股數', 'scope': '—', 'cur': None}, {'name': '新高／新低數目', 'scope': '—', 'cur': None}],
        'macro': [{'name': 'DXY', 'c': 0, 'chg': 'TODO', 'open': True, 'note': 'TODO'}],
        'post_missing': [],   # 圖面冇盤後價嘅代號
        # 價位清單：key＝ma10|ma20|ma50|ma200|h52|h|l|pc（自動取值）；或寫 v=價位；px 默認＝該標的收市
        'levels': [{'name': 'TODO', 't': 'SPY', 'key': 'ma50', 'status': 'TODO', 'cls': 'g'},
                   {'name': 'TODO', 't': 'SPY', 'v': 0, 'status': 'TODO', 'cls': ''}],
    }

def texts(m, S):
    row5 = ['TODO'] * 5
    return {
        'inherit_note': 'TODO（承襲上一份報告／群組規則嘅說明、紀律聲明）',
        'sum_boxes': [('TODO（最重要一件事）', 'hi'), ('TODO（第二件事）', 'hi')],
        'sum_rows': [['市況分類', 'TODO'], ['處置指示', 'TODO'], ['前日主要變化', 'TODO'], ['最強環節', 'TODO'], ['最弱環節', 'TODO'], ['關鍵風險', 'TODO']],
        'src_rows': [['圖表讀數', 'TODO（19 張截圖列表、廣度同源只算一個、直接睇圖冇用文字辨識）']],
        'verify_box': 'TODO（SMA 確認、收市價交叉核實、50 日均量補返…）',
        'gaps': [['TODO 缺項', 'TODO 說明同影響']],
        'divergence_extra': [],      # 額外分歧行：[項目, 截圖讀數, 外部, 差距, 處理]
        'cmp_notes': {'SPY': 'TODO', 'QQQ': 'TODO', 'IWM': 'TODO'},       # 附加喺比較表收市行解讀後
        'candle_notes': {'SPY': '', 'QQQ': '', 'IWM': ''},
        'sync_box': 'TODO（三指數同步性）',
        'ma_notes': {'SPY': 'TODO', 'QQQ': 'TODO', 'IWM': 'TODO'},
        'ma_box': 'TODO（結構觀察）',
        'events': [['<b>SPY</b>', 'TODO', 'TODO', 'TODO'], ['<b>QQQ</b>', 'TODO', 'TODO', 'TODO'], ['<b>IWM</b>', 'TODO', 'TODO', 'TODO']],
        'levels_box': 'TODO',
        'post_notes': {}, 'post_note': '',
        'vol_notes': {'SPY': '', 'QQQ': '', 'IWM': ''}, 'vol_box': 'TODO',
        'dist_def_note': '', 'dist_box': 'TODO（窗口未定義聲明、同舊報告唔可對賬）',
        'vix_close_note': 'TODO', 'vix_range_note': 'TODO', 'vix_h52_note': '', 'vix_hist_note': '', 'vix_para': 'TODO',
        'breadth_box': 'TODO（廣度讀數可靠度；10/16 同 10/19 圖停滯教訓）',
        'breadth_qa': [['指數升跌是否得到多數股票支持？', 'TODO'], ['高於 50 日及 200 日線比例有否改善？', 'TODO'],
                       ['升跌股數及新高／新低是否支持指數方向？', 'TODO'], ['是否出現指數與廣度背離？', 'TODO'], ['VIX 嘅水平、變化及與價格走勢嘅配合？', 'TODO']],
        'breadth_limits': 'TODO',
        'sector_box': 'TODO',
        'sector_qa': [['邊啲板塊領漲、落後或轉弱？', 'TODO'], ['當日反彈是否改變中期走勢？', 'TODO'], ['科技、半導體、金融、消費及防守板塊是否同步？', 'TODO'],
                      ['領漲是否擴散，還是集中在少數板塊？', 'TODO'], ['邊啲板塊值得優先交由群友作個股研究？', 'TODO']],
        'sector_flag': '',
        'catalysts_box': 'TODO',
        'past_events': [row5],                      # [事件日期, 事件及來源, 已知市場反應, 可能影響, 仍待確認]
        'past_note': '',
        # (事件, 美東日期, 'HH:MM' 或 None＝時間未核實, 預期／前值, 關注點[, cls])；香港時間自動換算
        'next_week': [('TODO', m.date, None, 'TODO', 'TODO')],
        'next_week_note': '', 'next_week_foot': 'TODO（日程以哪個來源為準；未核實日程唔補造）',
        # 'jlaw_html': 選填；用戶有提供 J Law Update PDF／影片先寫（逐項：J Law 講法｜日期｜對今日數據核實（CHART／CALC／EXT）｜一致／唔一致／未能核實），冇就刪走呢個 key
        # 'action_rows': 選填；條件式行動清單 [[#, 項目, 條件／做法], …]，非買賣建議
        'history_html': 'TODO（有充分證據才做；不足就寫明無法比較，唔指定歷史年份）',
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
    """重算頁內寫死嘅數字（texts 入面手寫嘅價、%、計數、日期序列、「連續 N 日」「最大／最小」斷言）。
    每項用 chk(名, 報告值, 獨立重算值[, 容差]) 或 chk_true(名, 條件) 登記；build 要求 ≥20 項、全部通過。
    例：chk('SPY 距 MA50 %', 4.75, m['SPY'].c - m['SPY'].ma(50), 0.005)；
        chk_true('QQQ 連續 4 日收喺 MA50 下', all(m['QQQ'].C[-i] < m['QQQ'].ma(50, i - 1) for i in range(1, 5)))"""
    pass
