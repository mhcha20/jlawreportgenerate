# WORKER.md — 單隻股票 V2.0 報告流程（排程子 session／子代理用）

輸入：`TICKER`、`DATE`（交易日 YYYY-MM-DD，＝截圖日期資料夾 `DD mon YYYY`）、個股資料夾 id、日期資料夾 id、`MODE`（full＝三份；card＝只出行動卡）。輸出：上載到 Drive（經網站 `/api/upload`）＋回報一行 JSON。

## 0. 環境（每個新 session 做一次）
```
cd <repo>/tools/stockreport && npm ci --silent        # 字體 @fontsource/noto-sans-tc
cd <repo> && npm ci --silent                          # signals.js 用 pdfjs-dist（測行動卡解析）
```
Playwright／Chromium 已預裝（`/opt/node22/lib/node_modules/playwright`，唔好 `playwright install`）。

> 環境：生成器支援 Python 3.11 或以上（`python3` 直接用，唔使轉 3.12）；`prep.py images` 喺 PIL 用唔到時會自動改用 ImageMagick（`convert`），裁出嚟嘅圖一樣。

> 美國冬令時間（11 月第一個星期日至 3 月第二個星期日）收市係香港 **05:00**（夏令 04:00）；頁首「資料截止」由 `gen.market_defaults()` 按 DATE 自動寫 EDT／EST。睇圖時核對右下角 UTC 鐘：冬令要 ≥ 21:00 UTC（夏令 ≥ 20:00 UTC）先係收市後截圖，早過就當截圖未齊（待下一輪）。

## 1. 取截圖（要齊 17 張，缺就停，回報 `incomplete`）
排程 session **冇 Drive 連接器**，一律用 `drive.py`（經網站 API；有連接器都照用呢套，結果一樣）：
```
python3 drive.py tickerfolder <TICKER>                      # 個股資料夾 id（重點股 id 已喺任務俾咗）
python3 drive.py datefolder <個股資料夾id> "22 oct 2026"      # 日期資料夾 id（月份三個小寫字母）
python3 drive.py shots <日期資料夾id> /tmp/<TICKER>           # 01–17 齊先下載；唔齊印 INCOMPLETE＋缺邊啲
```
截圖喺日期資料夾（任務會俾「個股資料夾 id」同「日期資料夾 id」兩個，唔好混）。**唔好用 Drive 嘅文字辨識（部分圖回傳空白或讀錯），要用 Read 工具直接睇圖。** 圖面右下角 UTC 鐘係截圖時間，唔係 K 線時間；盤後價只記錄唔用。

### 亞洲個股版面（港股、日股、韓股，代號全數字；日股 ETF 見下）
用 `drive.py shots <id> [outDir] --asia`：只要求 01–14；**15 內部人**（亞洲冇）、**16 預測評級**、**17 估值 P/S** 可能缺（例如 000660 缺 15、17；其餘多數缺 15）→ 對應欄位如實標「缺項（該市場冇此頁）」，唔當負面證據；覆蓋率按實際格數列出。價格幣別 HKD／JPY／KRW，日股成交量單位係股（100 股一手）；`S['asof']` 用該市場收市時間（港 16:00 HKT、日 15:00 JST＝14:00 HKT、韓 15:30 KST＝14:30 HKT）；無本地大盤報告就 `S['mkt_ref']`＝『無（只用圖面指數）』，唔好引用美股大盤報告當本地大市。

### ETF 版面（例如 XLV、XLK、QQQ、SOXX…）
ETF 資料夾只有 **12 張**：01 Daily／02 Weekly／03 4H／04 2H（TradingView）＋05 Futubull_Chart_Daily ＋06 Fund_Holdings、07 Fund_Portfolio、08 Fund_AUM、09 Fund_Description、10 Fund_Basic_Info、11 Fund_Dividends、12 Fund_Stock_Splits。`drive.py shots` 見到 `OK (ETF 12 張版面)` 就算齊。處理方式：
- 九構面仍然全部評分：**基本面**按 ETF 持倉集中度／板塊權重／費用率／AUM 變化判斷（唔係公司財報）；**機構支持**冇 13F／Form 4／分析員評級頁 → 標「N/A（ETF 無此頁）」，該構面用持倉 AUM 資金流向或標 3 星並寫明「缺資料，按中性計」（覆蓋率要如實列出少於 100%）；Minervini／CANSLIM 只做可量度嘅價格趨勢項，C／A／N／S／I 標 N/A。
- `fund_rows` 改為 ETF 項目（前十大持倉權重、板塊／行業分佈、AUM、費用率、派息、拆股歷史），`smart` 放 AUM／持倉變化；唔好硬套公司財報用語。
- `prep.py images` 只會裁 Futubull 圖；ETF 圖直接睇原圖或 `_c.png`。

## 2. 數據
```
python3 prep.py data <TICKER> <DATE>          # （網站 /api/ohlcv 曾回 502，重試一次先算失敗；data 同 images 分開跑，唔好用 && 串）網站 /api/ohlcv（Yahoo 日線）→ data/<TICKER>.json；最後一根要＝DATE
python3 prep.py images <TICKER> /tmp/<TICKER>  # 裁切 Futubull 圖：*_c.png（主畫面）、06–09 另有 *_t.png（標籤欄＋最近 6 季，字夠大）
```
**如果 `prep.py data` 話最後一根 K 線唔係 DATE（Yahoo 過咗 UTC 午夜有時會唔再回傳前一日 bar；網站由 2026-10-23 起會保存已見過嘅日線）**：用 Longbridge MCP `history_candlesticks_by_offset`（period=day, count=5, forward_adjust=false, trade_sessions=intraday）攞最近幾日，再用 `--extra '[{"d":"YYYY-MM-DD","o":..,"h":..,"l":..,"c":..,"v":股數}]'` 補入，並喺附錄第三節註明該日 OHLCV 來源係 Longbridge。

Yahoo 成交量同 Longbridge／TradingView 有時唔同（例：NVDA 2026-09-21 Yahoo 109.8M vs Longbridge 161.3M）；**多來源並列，唔平均**。圖面 MA（TradingView）同重算 SMA 要一致到兩位小數，否則先查（復權、時段）。

> 注意：任務俾你嘅有「個股資料夾 id」同「日期資料夾 id」兩個，**截圖喺日期資料夾**。`_t.png` 拼接圖只啱 NVDA／PFE 嗰種版面（06–09 欄位位置固定）；其他股票先睇 `_c.png`，唔清楚再自己用 PIL 裁左 45%＋右 30%。新上市未滿 200 日嘅股票：`prep.py data` 會因日線 <260 根而失敗——手動放寬 assert、MA200／52 週高低標「N/A（上市未滿 N 日）」並喺 `spec`／`texts` 內避開 MA200 相關欄位。

## 3. 睇圖（每張都要睇；睇唔清嘅數字寫「無法辨識」，唔好估）
01–04 TradingView 日／週／4H／2H：價、MA、RSI、成交量。05 Futubull 日線；06 關鍵指標、07 損益、08 資產負債、09 現金流（用 `_t.png`）；10 營運效率、11 收入拆分、12 全部持有人、13 股東活動、14 機構、15 內部人、16 預測評級、17 估值 P/S（用 `_c.png`）。ETF／非公司（如 XLV）冇財報頁就如實標「缺項」，基本面構面按 ETF 持倉／估值頁判斷或標 N/A，唔好湊分。

## 4. 寫分析（`work/<TICKER>_<DATE>.py`）
複製 `template_work.py` 做 `work/<TICKER>_<DATE>.py`，將所有 `TODO`／`0` 填成當日內容（`spec(m)` 同 `texts(m, S)`；範本只有欄位結構，冇分析內容）。**數字全部由當日截圖／行情重新得出。** 必守：
- 九構面＝趨勢、成交量、圖形、Momentum、基本面、市場配合、機構支持、Pullback、Breakout，星 1–5，分數＝星數÷45×100。
- 回踩路徑（機械式入場區）＋順勢路徑；R1–R4；止損％÷入場價、距離％÷現價；R4 四項測試（大市／第二階段／RRR≥2／雜訊被掃率＜30%，被掃率由 `plan_numbers` 按群組定義計）。
- 紀律十條（`docs/jlaw-myt-stock-prompt-v2.md`）：收市價為準、同一事實只計一次、多來源並列不調和、承襲門檻不自行改、Form 4 唔直接當看淡、突破成功率冇樣本一律 N/A。
- 大盤／板塊背景：美股引用最近一份我哋嘅大盤報告（`python3 drive.py market` 列出，`drive.py pdf` 下載）；港股、日股冇大盤報告就只用圖面指數同當日板塊，並註明。群組大盤執行規則（半倉上限等）未提供就唔套用。
- 上一份：Drive 同股票最近一份行動卡／報告（用 `read_file_content` 或下載 PDF 再 `pdftotext`）；對比價位前先核對佢嘅日期同收市價係咪真係屬於該交易日（曾發現 10/20 卡其實用 10/19 收市）。
- **今日動作（≤40 字）**要寫成「未持倉：…。已持倉：續抱，按警報價處理。」——已持倉**唔好出現「減倉／離場／清倉」字眼**（`signals.js` 會機械歸類成賣出訊號）；`signals.js` 對 flat 嘅歸類字眼：「零新倉／零倉／不買／觀望／保持觀望／唔入場」→零新倉；「低吸／吸納／分批／建倉／買入／入場／開倉／加碼」→條件式建倉（會變買入訊號！）；其他（例如只寫「等」）→觀望。價位只放第 3、5 格（`買入觸發 227.00 ▲2.27%`、`減倉 212.77 ▼4.14%`、`離場 203.00 ▼8.55%`、`227.00 要升 2.27% …`）。
- 朗讀稿：3 分鐘 ≤950 字、完整 ≤3,500 字；口語廣東話；數字寫成適合朗讀（`from lib import zh, zhint`）。
- 唔好用 `+`／`-` 表示升跌，用 `▲`／`▼`（build 會後處理 `+x%`／`-x%`）。

- **第 6 格「唔做嘅代價」必須包含固定句「回踩區入場（主目標 x.xxR）」**（每日跨股總表 `daily.py` 靠呢句抽「回踩入場 R」；寫成「回踩路徑主目標」「支持區入場」「參考價入場（aR／bR）」會抽唔到或抽錯，顯示「缺項」）。

## 4b. 篇幅（本體 ≤10 頁，好易爆）
`fund_rows` 最多 8 行、`risk` 每項 ≤1 行、`pattern_notes` ≤2 條、`smart` 放附錄（唔放本體）。`S['prior']` 字串入面如有括號，第一段（括號前）係評等分數，其餘放最後。`prior` 讀唔到 PDF 時用 `/api/signals` 嘅 rows／history 欄位，並喺附錄第三節註明。

## 4c. 其他提醒（來自試跑）
- 朗讀稿用 `from lib import zh, zhint`（`zh(221.97)`→「二百二十一點九七」）。
- 下次財報日：有 Longbridge 工具就用 `finance_calendar`（見下面「Longbridge 核實」）；排程 session 用 `lbcheck.py live-earnings`（要金鑰，見「Longbridge 核實」），查唔到就標「未公布」（唔好估）。
- 4H／2H 截圖含盤後 bar：圖面 RSI 同價只作參考，日線 RSI 先係正式讀數。
- 若 50 日均量被單日異常大量（>2.5×中位數）拉高，要喺 `caliber`／`vol_rows` 並列中位數或剔除後數值，並註明。
- 朗讀稿內嘅倍數、取整、百分比最易錯，要由 spec／計算值產生或逐個入 QA。

## 5. 覆核（必做）
**凡係 `texts` 內寫死嘅數字、計數、日期序列，同「從未／最大／最小／連續」類斷言，全部要入 QA 檢查**（ESTC、FPS 兩次試做，初稿分別有 5、8 項錯誤，多數係憑印象寫嘅派發日數、升跌％、「從未觸發」）。
把報告內所有寫死嘅數字（價、量比、距離、R 值、基本面算術、日期序列）用原始數據獨立重算一次（自己寫 `work/qa_<TICKER>.py`：由 `data/<T>.json` 原始數據重算，容差要細過最後一位，計完寫 NQ），失敗就改文字；更正項數寫入行動卡第 7 格同附錄第四節（`corr`、`corr_html`）；`NQ`（覆核數字個數）要等於 QA 檔實際檢查數，「另有 N 項對照差異」要等於附錄第三節實際並列數，唔好照抄範例。

## 6. 出 PDF、測試、上載
```
python3 build.py <TICKER> <DATE> work/<TICKER>_<DATE>.py     # → out/<DATE>_<TICKER>_行動卡／股票分析終極報告／核對附錄.pdf（行動卡 1 頁、本體 ≤10 頁，超出會 assert）
node sigtest.js out/<DATE>_<TICKER>_行動卡.pdf                # 要見到 date、ticker、評等、score、levels(buy/trim/stop)、alerts 3 條、flat/held 分類
```
上載（`ADMIN_PASSWORD` 由環境 proxy 自動帶 header，唔使寫密碼）：
```
python3 drive.py upload out/<檔名>.pdf        # 檔名＝YYYY-MM-DD_TICKER_行動卡.pdf／…_股票分析終極報告.pdf／…_核對附錄.pdf，cat=auto
python3 drive.py reports <TICKER> <DATE>      # 上載前後都查：同 ticker 同日同類型已有舊檔嘅 id
# 上載已帶 replace=1：伺服器會自動將同資料夾同名舊檔放入垃圾桶（用戶已授權；可還原）。`drive.py trash` 喺排程 session 會 401（管理員 header 只喺上載路徑注入），唔好用；上載回應 `replaced` 列出被放入垃圾桶嘅舊檔 id。
```

## 7. 回報（最後一行，JSON）
`{"ticker","date","mode","status":"done|incomplete|failed","rating","score","tier","pages":{…},"corrections":N,"notes":"…"}`

## 實測補充（10/21 演練回饋）
- **新上市股（日線 <260 根）**：`prep.py data` 會因 assert 失敗；改用 `/api/ohlcv` 自行寫 `data/<T>.json`，MA200 標 N/A，52 週高低改用上市以來高低，Minervini／第二階段涉及 MA200 嘅項目標 N/A。
- Longbridge `finance_calendar` 冇 symbol 篩選：一定要傳 `market` 同 `_jq` 過濾（見下面「Longbridge 核實」），否則回傳幾百 KB 會被截斷。
- **ETF**：`gen2.build_report` 內「覆蓋率 100%」「最近一季」字眼唔啱 ETF，要喺 work 檔替換；機構支持標 N/A 按中性 3 星並列為未決問題。ETF 派息多，Futubull 圖面疑為前復權，長週期均線／52 週高低同不復權價有差，並列唔採用。
- QA 容差要細過最後一位；顯示捨入邊界（x.xx5）要跟 TradingView 圖面。
- Futubull 圖偶有孤立 K 線／4H RSI 同日線一樣，視為顯示異常，只並列唔採用。
- `from lib import *` 會覆蓋 `HERE`，QA 檔自己嘅路徑另起名。

## 亞洲／日股 ETF 補充（2640 演練回饋）
- TSE 收市 15:30 JST（＝14:30 HKT），唔係 15:00。
- Futubull ETF 截圖 09–12 檔名同內容可能對唔上（09 係 Stock Splits、10–12 全係派息頁）；費用率／追蹤指數／成立日缺項時基本面按中性 3 星並列。
- `prep.py data` 成交量存整數千股，細流動性標的（日量幾 K 股）會失真；要用 `/api/ohlcv` 自寫 data 並存「股」。
- 通用檔寫死 USD／$／美東 16:00／13F／Longbridge 字眼，非美股要喺 work 檔 `page()` 後處理替換（JPY、¥、Yahoo）。
- `signals.js` titleTicker 只認字母代號，數字代號靠檔名；`S['zh']` 用短名避免標題換行。
- Futubull／TradingView 圖面為前復權，高息 ETF 長週期均線（MA120／250）同不復權價有差，並列唔採用。
- `plan_numbers` 固定 t1（大市上升）=False，亞洲冇本地大盤報告時要自行處理並註明。
- 趨勢轉折標的先跑 `mv_table`（Minervini 第 2、3 項：MA150>MA200、MA200 向上一個月）再判斷階段。
- `drive.py latest` 唔會顯示同日舊檔，要用 `drive.py reports`。

## 非美股本地化（已內建，唔使再後處理）
`gen.MARKETS` 按代號自動判斷市場（字母＝US、5 位數字＝HK、6 位＝KR、4 位＝JP），默認設好收市時間、幣別（HKD／JPY／KRW；`HK$`／`¥`／`₩`）、資料源字眼（Yahoo）、機構資料字眼、覆蓋率字眼、冇本地大盤報告嘅 `mkt_ref`；`lib.localize()` 喺 `page()` 內自動將 `USD`／`$12.3`／範本句「成交量用 Longbridge」／`13F／Form 4`／`覆蓋率 100%`／TradingView 均線對照句換成對應市場版本。work 檔只需要喺 `spec()` 入面覆蓋 `S['ccy']`、`S['cur']`、`S['asof']` 等個別欄位（例如 ETF 或港仙列示）；**唔好再自己包 `lib.page`**。價位小數仍固定兩位（警報價行要保留 `.00` 先解析到）。

## 每日跨股總表（自動化，`daily.py`）
```
python3 daily.py 2026-10-21 [--market US|ASIA|ALL] [--out DIR] [--upload] [--strict]
```
- 輸出 `out/<DATE>_每日跨股總表.pdf`（A4 直向、同 `gen2.build_daily` 一致、硬上限 3 頁，超出會 assert）。`--market US`＝美股場次、`ASIA`＝港日韓場次、`ALL`（默認）＝當日全部；後一場次跑 `ALL` 就自然包含前一場次已出嘅股票。`--out` 指定輸出資料夾（試跑用 /tmp，唔會碰 Drive）。`--upload` 先 `drive.py upload`（檔名含「每日跨股總表」自動歸類，replace=1 取代同名舊檔；唔好用 `drive.py trash`）。**未獲指示唔好 `--upload`**。`--strict`：QA 有不一致就非零退出。
- 資料來源（全部公開唯讀，唔寫 server）：`/api/sync` 決定當日有邊啲「股票分析終極報告」＋行動卡／本體報告 id；`/api/signals` 嘅 rows（當日）或 history（rows 已係較新日子時）提供評等、分數、今日動作分類、收市、買入觸發／止損；其餘用 `pdftotext` 讀行動卡 PDF（減倉價、各價位距離％、第 6 格「唔做嘅代價」）同本體報告 PDF（R4 第四項雜訊被掃率）。環境要有 `pdftotext`／`pdfinfo`（poppler）、`node render.js`、字體 `npm ci`。
- 納入規則：當日有終極報告 **同** 行動卡有三條價位＋「唔做嘅代價」（V2.0 七格）先納入；舊版（冇行動卡，或冇三條價位）列喺口徑聲明尾「未納入」；有行動卡但 `/api/signals` 未解析（`running`）就列「暫未有解析結果」。價位前標幣別（US＝USD、5 位數字＝HKD、6 位＝KRW、4 位＝JPY）；按美股、港股、日股、韓股分組，組內按距離％由近至遠。
- 欄位：分數只喺行動卡冇聲明「計法不同」時先標自身箭嘴，否則寫「新起算｜上一份 N」；最近觸發位＝買入觸發／減倉／離場三條入面離現價最近；**R 值直接取自行動卡第 6 格原文**（回踩入場 R＝「回踩／回測區入場（xR）」；今日入場 R＝到主目標），唔係近似推算——卡內冇價就標「缺項」，唔編造；被掃率抽唔到亦標缺項。
- 限制：①R 值各股主目標定義唔同（見各行動卡），只作排序參考；②依賴行動卡／本體報告嘅中文句式（`唔做嘅代價`、`回踩區入場（x.xxR）`、`雜訊被掃率 < 30% ✔（回踩 n／60＝x%`），行動卡版面變咗要同步改 `daily.py` 嘅 `parse_card_text`／`parse_sweep`，缺項會顯示「缺項」而唔係靜默出錯；③未有股票名稱欄（行動卡標題版面唔穩定）；④Drive 同日同代號多次上載取最新一份行動卡，並同 `/api/signals` 嘅 id 對照，唔同會喺口徑聲明列「核對提示」；⑤QA 不一致會印 `QA …` 於 notes（亦列入 PDF 尾）。

## 數據檔按日期分開
`prep.py data` 同時寫 `data/<T>.json` 同 `data/<T>_<DATE>.json`，`build.py` 會優先用後者（`JL_DATE`），所以同一隻股票兩個日期同時做唔會互相覆寫。**自己手寫數據檔（新上市股、亞洲低流動股）要寫到 `data/<T>_<DATE>.json`**，否則舊嘅同名日期檔會蓋住你手寫嘅 `data/<T>.json`。

## 上一份係我哋自己嘅報告（`S['prior_same']`）
上一份如果係本生成器出嘅同一套九構面計法（例如連續兩日），喺 `spec()` 設 `S['prior_same'] = True`，`lib.localize` 會將「計法不同，唔作升降」「評分表未提供」「本份係首份」等字眼改為「同一九構面計法，可直接比較升降」，分數升降用 `S['prior']` 內嘅上一份分數自行寫明。唔需要自己後處理字串。

## 已持倉價位被跌穿（統一寫法）
收市價已跌穿上一份卡嘅減倉線／離場線時，今日動作「已持倉」欄必須如實寫「減倉」或「離場」（`signals.js` 會歸類為賣出訊號）；未跌穿就唔好寫減倉/離場字眼，用「續抱，按警報價處理」。唔好用「按新警報價處理」迴避已跌穿嘅線。**離場要寫「今日離場」、減倉要寫「減倉」（signals.js 只認呢兩個字眼歸類為賣出訊號；「離場線已破，離場」認唔到）。**

## 評等字眼（固定）
強烈買入、值得買入、買入、觀察、不建議、避免交易（1 星）。唔好自創「轉弱／暫避」「強烈避免」等，`signals.js` 識別唔到會誤歸類。

## 唔好提「群組執行規則」
群組嘅大盤／倉位執行規則有新版會由用戶貼出，**報告內任何位置（頁首、第一部分大市表、承襲說明、未決問題、附錄）都唔好寫「群組執行規則未收到／未提供／唔套用倉位上限／有冇港股大盤執行規則」呢類句子**。大市只寫市況分類同數字；R4 第一項（大市）照常按市況判斷。`lib.localize` 會自動移除頁首標準句，其餘位置由你寫文字時避免。

## 先大盤、後個股（美股）
美股個股報告一定要喺當日大盤報告（`drive.py market` 有 `<D>_美股大盤分析_JW框架_Claude核實版`）上載之後先做，市場配合同 R4 大市測試要按當日大盤評，頁首寫「承襲 <D> 大盤報告」。大盤未出就唔好做個股（等下一輪）；只有最後一輪仍未有，先用最新一份並註明承襲。亞洲股用本地圖面指數，唔受此限。

## Longbridge 核實
**排程 worker 每隻美股／港股必做**（日韓跳過）：①`python3 lbcheck.py live-verify <T> <D>` 收市核實；②`python3 lbcheck.py live-earnings <T> <D>` 攞下次業績日寫入報告（取代「未公布」）；③Yahoo 缺 D 嗰根先用 `live-extra` 補。全部 exit 2＝冇金鑰／連唔到，照舊用 Yahoo＋截圖，**收尾 JSON 嘅 notes 要寫「冇 Longbridge 核實」**，唔好停工。
**兩條路**：①session 有 `mcp__Longbridge__*` 工具 → 照下面 1–3 用 MCP；②冇 MCP（排程 session）→ 用 `lbcheck.py` 直連模式（3 個金鑰喺環境變數 `LONGBRIDGE_APP_KEY／APP_SECRET／ACCESS_TOKEN`，要 `pip install -q longport`）：
- 開頭先 `python3 lbcheck.py check NVDA.US`：`OK` 先用下面指令；exit 2（缺金鑰／網絡／權限）＝今次冇 Longbridge 核實，**照舊用 Yahoo＋截圖，喺收尾警告一句，唔好停工、唔好當數據不一致**。
- 收市核實 `python3 lbcheck.py live-verify <T> <DATE>`（exit 0 一致、1 不一致→附錄第三節並列、2 直連失敗、3 市場未支援＝日韓）；補 bar `live-extra <T> <DATE>`；下次業績日 `live-earnings <T> <DATE>`（一句，可直接寫入報告；「查唔到」就標「未公布」）。港股代號會自動轉（00066→66.HK）。
- 金鑰 **永遠唔好** 寫入檔案、commit、截圖、貼入報告或回報文字。
MCP 做法（有 `mcp__Longbridge__*` 時）：
工具名 `mcp__Longbridge__*`（未載入就先 ToolSearch `select:mcp__Longbridge__history_candlesticks_by_offset,mcp__Longbridge__finance_calendar`）。代號格式：美股 `AAPL.US`、港股 `700.HK`／`3690.HK`（**唔好補前導零**，`00700.HK` 會回空）、其他市場 Longbridge 未必有，冇就照舊用 Yahoo＋截圖。
1. **收市核實（每隻都做，1 次呼叫）**：`history_candlesticks_by_offset(symbol, count=3, trade_sessions="intraday", forward_adjust=false)`，同 `data/<T>_<DATE>.json` 最後一根比：收市差 ≤0.02 或 ≤0.05% 當一致；唔一致就查日期／復權，喺附錄第三節並列。成交量 Longbridge 同 Yahoo 口徑可能唔同，並列唔平均。
2. **Yahoo 未有 DATE 嗰根**：用上面結果經 `prep.py data … --extra` 補入（優先過截圖讀數），附錄註明「DATE OHLCV 來源 Longbridge」。
3. **下次業績日**：`finance_calendar(category="report", market="US", start=DATE, end=DATE+45 日, _jq='[.list[].infos[] | select(.symbol=="AAPL.US") | {symbol,date,date_type}]')`；港股 market="HK"。查到就寫日期＋盤前／盤後（來源 Longbridge 財經日曆，以公司公告為準），查唔到先標「未公布」。
5. 輔助腳本 `lbcheck.py`：`verify`／`extra`／`calendar` 處理 MCP 存低嘅 JSON；`live-*` 直連（見上）。用法見檔頭。
4. 唔好用 Longbridge 做交易、改自選股或任何寫入動作（工具本身亦唔會落單）。
