# WORKER_MARKET.md — 每日美股大盤報告流程（排程子 session／子代理用）

輸入：`DATE`（美國交易日 YYYY-MM-DD，＝截圖日期資料夾 `DD mon YYYY`）。輸出：`YYYY-MM-DD_美股大盤分析_JW框架_Claude核實版.pdf` 上載到 Drive（經網站 `/api/upload`，cat 自動歸 market）＋回報一行 JSON。分析指令全文：`docs/jw-market-analysis-prompt.md`（開工前讀一次）。

## 0. 環境（每個新 session 做一次）
```
cd <repo>/tools/stockreport && npm ci --silent        # 字體 @fontsource/noto-sans-tc
```
Playwright／Chromium 已預裝（`/opt/node22/lib/node_modules/playwright`，唔好 `playwright install`）。冇 Drive 連接器，一律用 `drive.py`。

## 1. 取截圖（要齊 19 張，缺就停，回報 `incomplete`）
```
python3 drive.py market-shots <DATE> /tmp/mshots-<DATE>   # 搵「DD mon YYYY」資料夾、核對 19 張、下載；齊先印 OK，唔齊印 INCOMPLETE＋缺邊啲（exit 1）
```
19 張＝`NN_TICKER_Daily.png`：IWM、VIX、SPY、QQQ、SOX、11 個 SPDR 板塊（XLK XLF XLE XLV XLY XLB XLC XLI XLP XLU XLRE）、DXY、`GC1!`、US10Y。截圖通常收市後先上載；DATE 資料夾未出現或唔齊就等，唔好用上一日圖湊。

## 2. 逐張睇圖（最花時間，一定要做）
- **用 Read 工具直接睇圖像（圖約 3806px，會自動縮細）。唔好用 Drive `read_file_content` 嘅文字辨識**（部分圖回傳空白，亦會讀錯）。19 張全部睇，睇唔清嘅數字寫「無法辨識」，唔好估。
- 每張抄：O／H／L／C、升跌額同 %、Vol（圖面量，M）、MA10／20／50／200（圖面標籤）、RSI 14、盤後價（`Post` 標籤；冇就當缺，例如 XLRE 試過冇）。SPY 圖底部另有 S5FI（高於 50 日線）同 S5TH（高於 200 日線）兩條廣度線：抄 O／H／L／C 同升跌。VIX、SOX 抄 OHLC 同升跌。DXY、GC1!、US10Y 抄快照。
- **圖面右下角 UTC 鐘係截圖時間，唔係 K 線時間**（例：10/16 批其實係 10/17 星期六重新截，K 線係星期五最終數據）。`S['meta']['shot_utc']` 填呢個鐘；build 會擋「截圖時間未過美東 16:00」。
- **DXY、GC1!、US10Y 嘅日線截圖時通常未收**（價格標籤有倒數計時，例如 `02:00:31`），讀數只當快照，表內已標「日線未收」，唔好同收市價比較或寫成收市。
- 圖面 MA 一律同行情重算 SMA 對照（build 自動核到兩位小數）；對唔上先查復權、時段、自訂指標設定，不可混用（V1.0 第三節第 8 條）。

### 廣度圖（S5FI／S5TH）停滯教訓 — 必讀
- **10/19 圖上兩條廣度線嘅開高低收同 10/16 圖完全相同**（S5FI O52.08 H52.08 L42.94 C45.12；S5TH 升跌 0.00）；10/15、10/16、10/19 三日 S5TH 全部係 51.88，而 10/16 SPY 跌 1.11% 廣度反而升 → 圖面廣度**有資料停滯／落後跡象**。
- **10/22 再次證實落後一日**：SPY 圖 S5FI 55.26、S5TH 54.67，正正係 10/21 報告記錄嘅「18:20 ET 截圖讀到嘅 10/21 值」。即 17:02 ET 前後截嘅廣度線，顯示嘅係上一個交易日。
- 規則：每日必須同上一日圖面逐值比較（相同＝停滯）；引用前先核；廣度只作參考，**唔可以用嚟解釋當日價格**；同一來源喺多張圖重複出現只算一個；冇升跌股數、新高新低就寫缺項，唔可斷言「廣度持續改善」。建議截圖喺美東 18:30 後做。

## 3. 行情數據
```
python3 market/prep.py <DATE>      # 經網站 /api/ohlcv（Yahoo）攞 SPY QQQ IWM、11 板塊、SMH，存 market/data/；最後一根要＝DATE
```
- Yahoo 唔識嘅代號（**VIX、SOX、DXY、GC1!、US10Y**；`/api/ohlcv` 只收 `[A-Z0-9]{1,8}`，指數／期貨／債息一律失敗）prep 會列為「圖表讀數項」＝只有截圖，冇外部對照；SMH 可作半導體 ETF 並列對照（唔等於 SOX）。
- 若 Yahoo 未更新 DATE 嘅 bar（過咗 UTC 午夜有時唔再回傳前一日）：用 Longbridge `history_candlesticks_by_offset`（symbol=`SPY.US`，period=day，count 5，forward_adjust=false，trade_sessions=intraday）攞，經 `--extra '{"SPY":[{"d":"YYYY-MM-DD","o":..,"h":..,"l":..,"c":..,"v":股數}]}'` 補入，並喺第二節註明來源。Yahoo 同 Longbridge 日線量實測一致（SPY 10/22 54,035,400 vs 54,117,128 有細差，圖面 53.17M 另一口徑；並列唔平均）。
- 均量口徑：默認「50 日含當日」（同 10/19–10/21 報告一致；work 檔 `BASIS = 'excl'` 可改為不含當日），報告自動聲明，並一律寫「當日量÷50 日均量」，**唔係 RVOL20**。
- 一日內 prep 唔好重複跑多隻日期混用：`market/data/_meta.json` 記住日期，build 會擋日期唔對。

## 4. 寫 work 檔（`work/market_<DATE>.py`，唔提交）
複製 `market/template_work.py`，將所有 `TODO`／`0` 換成當日內容（`spec(m)`＝圖面讀數＋價位清單＋後設；`texts(m, S)`＝敘述；`qa(m, S, T)`＝重算）。`m` 係 `mlib.Market`：`m['SPY'].c／.pc／.chgp／.ma(50)／.v50()／.vr()／.candle()／.dist_days()`。敘述入面嘅數字**一律用 f-string 由 `m`／`S` 取值**，唔好憑印象寫死。必守（V1.0）：
- 開頭列美國交易日、截止時間、美東＋香港時間（build 自動出；夏令／冬令自動判斷）；區分截圖時間／檔名日期／最新 K 線日期；區分圖表讀數／外部事實／計算結果／分析推論（用 `CALC` `INF` `CHART` `EXT` 標籤）。
- 模糊數值直接標示，不猜；官方數據優先；截圖同外部數據不同先查時段、延遲、復權、日期。
- 派發日：先列定義（`dist_days()`：下跌日或升幅≤0.2%，量＞前日且＞當日滾動 50 日均量，近 25 日）；窗口 V1.0 未定義→只作示範計數、唔作超標／達標判定。**10/21 報告 SPY 8／QQQ 6 同呢個定義逐日重算（SPY 5／QQQ 4）唔一致，以行情重算為準**，唔好承襲舊報告日數。
- 板塊：只描述價格強弱同輪動，冇可核實資金流就唔用「資金淨流入／流出」。VIX 下跌唔單獨證明轉強。
- 情境 A／B／C：價格／量能／廣度觀察條件、觸發、失效、影響；不提供勝率／機率；不自行改門檻；市況標籤唔等於買賣許可。
- 過去 5 日催化劑同未來一星期日程：要聯網（搜尋／Longbridge `macrodata`、`finance_calendar category="report"`）核實，附來源同日期；核實唔到就標「未核實」，**唔補造**。`next_week` 用美東日期＋`HH:MM`，香港時間由 `et_hk()` 換算。
- 報告註明：框架名、實際 AI／模式（模型識別碼取自 session 配置，唔猜）、分析日期（香港）。

## 5. QA 重算（build 前必做，build 亦會擋）
work 檔 `qa()` 要用 `chk(名, 報告值, 獨立重算值, 容差)`／`chk_true(名, 條件)` 登記，build 要求 **≥20 項全過**。範圍：
- **所有寫死喺 texts 入面嘅數字、計數、日期序列、「連續 N 日」「最大／最小」「領漲前三」斷言**（價位狀態字串例如「差 4.21 蚊」最易錯：10/22 初稿曾寫錯成 0.21，靠 QA 攔到）。
- 廣度「前值＋升跌＝讀數」、VIX／SOX 前收＋升跌＝收、黃金／息率算術、`et_hk()` 時差換算。
- 自動項（build 內置，唔使寫）：14 個 ETF 圖面收市／前收／MA10–200 對行情（≤0.0051）；PDF 出完後 `market/qa.py` 用獨立最小計算由原始 JSON 重算 SPY／QQQ／IWM 收市、升跌、MA、量比、CLV、成交量同 11 板塊當日／相對／5 日／20 日%，逐個確認出現喺 PDF 文字入面（10/22 演練：88 項）。
- 容差要細過最後一位；圖面量同行情量差距由第二節「數據分歧」表自動並列，唔平均。

## 6. 出 PDF、檢查、上載
```
python3 market/build.py <DATE> work/market_<DATE>.py      # → out/<DATE>_美股大盤分析_JW框架_Claude核實版.pdf；頁數 ≤16（超出 exit 1）
pdftoppm -r 60 -png out/<檔名>.pdf /tmp/pg && 用 Read 睇幾頁（版面、有冇溢出）
python3 drive.py upload out/<DATE>_美股大盤分析_JW框架_Claude核實版.pdf     # cat 自動歸 market；replace=1 會自動將同資料夾同名舊檔放入垃圾桶（可還原）
python3 drive.py market                                   # 確認最新一份＝今日
```
- 檔名固定 `YYYY-MM-DD_美股大盤分析_JW框架_Claude核實版.pdf`。**唔好用 `drive.py trash`**（排程 session 會 401；replace=1 已處理同名舊檔）。
- 驗證／試跑用 `--out /tmp/xxx`，**唔好上載取代現有檔**。
- 參考版面：`drive.py market` 列最近三份、`drive.py pdf <id> out.pdf` 下載。10/21 版 14 頁；10/22 演練版 10 頁（敘述較精簡）。

## 7. 回報（最後一行，JSON）
`{"date","status":"done|incomplete|failed","pages","qa_work","qa_pdf","classification":"…","notes":"缺項／未核實／廣度停滯與否"}`

## 實測補充（10/22 演練回饋）
- 圖面 MA 標籤同行情 SMA 一致到兩位小數（14 個 ETF，112 項 QA 全過）；圖面成交量同 Yahoo 差 0.5–4%（Cboe One vs 綜合量），以 Yahoo 為分子分母。
- `/api/ohlcv` 對 XLRE 等 ETF 正常；VIXY／UUP 可取但唔等於 VIX／DXY，唔好當替代。
- 工作目錄：build 會 chdir 到 `tools/stockreport/`，work 檔放 `work/`（已被 .gitignore）。

## J Law 觀點（選填，用戶有提供 J Law Update PDF／影片先做）
- `texts()` 加 `jlaw_html`：放喺「重點摘要」之後，標題「J Law 觀點對照及逐項核實」。先列用咗邊幾份 J Law 材料（日期／時間；只用分析交易日收市**之前或當日**發布嘅，之後發布嘅只可列作「後續參考」唔可用嚟支持結論）、J Law 當時嘅風險胃納（Risk-On／Neutral／Risk-Off）同幾份之間點變。
- 逐項表：J Law 講法（短引述，註明日期）｜對當日數據核實（用 `CHART`／`CALC`／`EXT` 標籤，數字由 `m`／`S` f-string 取）｜結果（✅ 一致／❌ 唔一致／⚠ 未能核實／觀點：無法用數據核實）。J Law 嘅觀點同本報告自己嘅判斷分開寫，唔好將佢嘅觀點當成已核實事實；佢提到嘅歷史例子（例如 2025 年 1–4 月）有日線先核，冇就標未核實。
- 有 J Law 材料時，`action_rows`（條件式行動清單）同第七節歷史比較可以引用佢提出嘅觀察重點，但門檻價位仍然要由圖表／行情得出。
- 頁數上限加 4 頁（有 `jlaw_html` 時 ≤20）。J Law 材料係用戶私人提供，**唔好提交入 repo**，PDF 放 scratchpad。

## Longbridge（有 `mcp__Longbridge__*` 用 MCP；排程 session 用 `lbcheck.py live-*` 直連，見 WORKER.md「Longbridge 核實」；直連失敗就照舊 Yahoo＋截圖並喺收尾警告）
- **排程每日必做（直連）**：`pip install -q longport 2>&1 | tail -1; python3 lbcheck.py check SPY.US`；`OK` → 對 SPY、QQQ、IWM 各跑 `python3 lbcheck.py live-verify <T> <D>`（讀 `market/data/<T>.json`；exit 0 一致、1 不一致→並列第二節、2／3 冇核實），結果寫入第二節資料來源一句（例：「SPY／QQQ／IWM 收市同 Longbridge 一致」）；exit 2 就照舊 Yahoo＋截圖，收尾警告「⚠ 今次冇 Longbridge 核實」。金鑰只喺環境變數，唔好印出或寫入。
- SPY／QQQ／IWM 同 11 板塊收市：`history_candlesticks_by_offset(symbol="SPY.US", count=3, trade_sessions="intraday")` 同 Yahoo 對一次，唔一致並列；Yahoo 未有 D 嗰根就用佢經 `--extra` 補。
- 未來一星期事件：`finance_calendar(category="macrodata", market="US", start, end, _jq=…)` 同 `category="report"`（一定要傳 market＋_jq 過濾，避免截斷），同 WebSearch 結果互相核對。
