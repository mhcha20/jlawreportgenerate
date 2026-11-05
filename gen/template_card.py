# 只出「一頁行動卡」嘅 work 檔範本（build.py … --card）：複製成 work/<TICKER>_<DATE>.py，將所有 'TODO' 同 0 換成當日截圖／行情得出嘅內容。
# 同 template_work.py 嘅 spec(m) 一樣（九構面、A／B 路徑、減倉／離場、今日動作全部要填）；texts(m, S) 只需四個欄位。
# S 欄位可選覆蓋：asof、asof_full、mkt_ref（非美股默認已按市場設好）、ccy、cur、src_name、cov、ma_chk、prior_same。
from lib import *

def spec(m):
    S = {'t': 'TODO',               # 代號
     'zh': 'TODO',                  # 短中文名（避免標題換行）
     'exch': 'TODO',                # 交易所
     'sector': 'TODO',              # 板塊（同大盤報告嘅板塊名對應）
     'hi52': 0, 'hi52_date': 'TODO',
     'lo52': 0, 'lo52_date': 'TODO',
     'prior': 'TODO',               # 上一份：『YYYY-MM-DD 評等 分數／100（來源）』；冇就『無』
     'prior_cl': 0,                 # 上一份收市價（冇就 0）
     'prior_same': False,           # 上一份係本生成器出嘅 V2.0 卡→True（可直接比較升降）
     'rating': 'TODO',              # 要連星：例如 '★★★ 觀察'（固定字眼：強烈買入／值得買入／買入／觀察／不建議／避免交易；星數同 stars 一致）
     'stars': 0,                    # 1–5
     'sub': 'TODO',                 # 評等一句補充（≤40 字）
     'dims': [('趨勢', 0, 'TODO'),   # 九構面：(名, 星 1–5, 理由一句)，分數＝星數÷45×100 由 plan_numbers 計
              ('成交量', 0, 'TODO'),
              ('圖形', 0, 'TODO'),
              ('Momentum', 0, 'TODO'),
              ('基本面', 0, 'TODO'),
              ('市場配合', 0, 'TODO'),
              ('機構支持', 0, 'TODO'),
              ('Pullback', 0, 'TODO'),
              ('Breakout', 0, 'TODO')],
     'A': {'name': '順勢路徑',        # 突破入場
           'trig': 0,               # 觸發價（結構位）
           'trig_rule': 'TODO',     # 觸發條件一句（收市高過＋量）
           'cond_px': 0,            # 買入觸發價（行動卡第 3／5 格用）
           'stop': 0, 'stop_note': 'TODO',
           'T': [0, 0], 'Tn': ['TODO', 'TODO'],   # 目標價同理由
           'risk': 0, 'R': [0, 0]},
     'B': {'name': '回踩路徑',        # 機械式入場區
           'zone': (0, 0),          # 回踩區（低, 高）
           'entry': 0,              # 區內參考入場價
           'stop': 0, 'stop_note': 'TODO',
           'T': [0, 0], 'Tn': ['TODO', 'TODO'],
           'risk': 0, 'R': [0, 0]},
     'reduce': 0,                   # 減倉線（收市跌穿）
     'exitp': 0,                    # 離場線（收市跌穿）
     'stage_ok': False,             # 第二階段成立？
     'action': 'TODO',              # ≤40 字：「未持倉：…。已持倉：續抱，按警報價處理。」（已跌穿減倉／離場線先寫「減倉」／「今日離場」）
     'tier': 'TODO', 'tier_reason': 'TODO',
     'stage': 'TODO',               # Weinstein 階段一句
     'earn': 'TODO',                # 下次財報（查唔到寫「未公布」）
     'prev_md': 'TODO',             # 上一個交易日 MM/DD
     'mkt_ref': 'TODO',             # 美股：『YYYY-MM-DD 大盤報告』；亞洲：『無（只用圖面指數）』
     'prev_note': '', 'mkt_state': 'TODO',   # 大盤市況分類（照大盤報告）
     'ver_note': 'TODO', 'shot_note': 'TODO'}
    return S

def texts(m, S):
    T = {'biggest': 'TODO',    # 第 4 格：同上一份最大變化（一句，含數字）
         'cost_tail': 'TODO',  # 第 6 格尾句（R4 四項測試邊項唔過／檔位）
         'corr': 'TODO',       # 第 7 格：『今日覆核更正 N 項：…』（QA 後填）
         'foot': 'TODO'}       # 卡底一句（資料來源／口徑／承襲）
    return T
