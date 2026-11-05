# stockreport｜V2.0 個股報告生成器（行動卡／本體報告／核對附錄／跨股總表）

純 Python（標準庫＋Pillow 唔需要）＋ Playwright（Chromium）出 PDF。**只放通用框架**；每隻股票嘅 spec（S）同敘述（T）由每日排程按截圖／行情產生，唔提交（內部分析內容，repo 係公開嘅）。

## 檔案
- `lib.py`：指標計算（SMA、均量不含當日、派發日、ATR 簡單／Wilder、雜訊被掃率 `sweep`、`count_prints`）、SVG 圖表（K 線＋均線＋成交量、計劃圖）、HTML helper、`▲▼`／內容標籤後處理。
- `gen.py`：`plan_numbers()`（R 值、被掃率、R4 四項測試、檔位）、`build_card()`（一頁行動卡）、`mv_table()`。
- `gen2.py`：`build_report()`（本體報告，照 HPE 範本 9 頁）、`build_appendix()`、`build_daily()`。
- `style.css`、`render.js`（`node render.js jobs.json`，jobs＝`[{html,pdf,footer}]`，A4，footer 置中）。
- 字體：`npm i @fontsource/noto-sans-tc`，HTML 內用 `<link>` 引用（見 `lib.FONTS`）。

## 數據輸入
`data/<TICKER>.json` ＝ `{"closes":[…≥300 收市價…], "bars":[["MM-DD",o,h,l,c,volume_千股],…最近 135 根]}`（Longbridge 日線，正常時段、不復權、只取完整交易日）。`closes[-135:]` 要同 `bars` 收市價一致。

## S（spec）欄位
`t zh exch sector hi52 hi52_date lo52 lo52_date prior rating stars sub dims(9 構面：趨勢／成交量／圖形／Momentum／基本面／市場配合／機構支持／Pullback／Breakout，(名,星,理由)) A{name trig trig_rule cond_px stop stop_note T[] Tn[]} B{name zone entry stop stop_note T[] Tn[]} reduce exitp stage_ok action stage earn`。`plan_numbers(m,S)` 再補 `risk R sweep* tests tier score alert_txt mv_line …`。

## T（敘述）欄位
`oneliner setup biggest next3[] review chart1_lines[] p1a p1b p1c(各 (表現,判斷)) stage_txt hhhl mom vol_rows[] pattern pattern_notes[] sr_rows[] pb_star pb[] bo_star bo[] canslim[] canslim_line analyst_line smart_line sector_line fund_rows[] smart[] risk_lvl risk["類別：內容"] zone_lo_def zone_hi_def rrr_note r3_note stage_test tier_tail addon swing_only earn_line f1_B f1_A f1_note f2_interp alerts_txt flat held keep[] noup[] vsprior next3_line plan_line q1..q4 thr[] caliber[] conflicts[] corr corr_html sources[] open[] script3 scriptfull cost_tail foot daily_*`。

## 約定（同 `signals.js` 對版，改動前先跑解析測試）
行動卡七格標題固定為「1 評等／2 今日動作一句／3 三條價位／4 同上一份最大變化／5 三個警報價／6 唔做嘅代價／7 今日更正」。第 2 格要用「未持倉：…。已持倉：…。」；**已持倉唔好寫「減倉／離場」字眼**（會被機械歸類成賣出訊號），價位寫喺第 3、5 格：`買入觸發 227.00 ▲2.27%`、`減倉 212.77 ▼4.14%`、`離場 203.00 ▼8.55%`、`227.00 要升 2.27% 說明`。上載前用 `signals.js` 嘅 `parseCard`／`classify` 測一次。

## 口徑（同群組 HPE 範本一致）
九構面分數＝星數 ÷ 45 × 100；均量不含當日；派發日＝下跌日且量大過前日及當日 50 日均量（25 日窗口）；雜訊被掃率＝過去 60 個交易日、5 日窗口、入場價×(1−止損%)；距離％ ÷ 現價、止損％ ÷ 入場價；百分比兩位小數、▲▼ 取代 +／−。

## 大盤報告（market/）
每日美股大盤報告（JW 大盤分析指令 V1.0）通用框架：`market/prep.py DATE`（行情）→ `market/build.py DATE work.py`（PDF＋QA）；`market/template_work.py` 係空範本，完整流程見 `WORKER_MARKET.md`。
