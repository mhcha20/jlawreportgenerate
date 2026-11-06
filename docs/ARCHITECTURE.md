# 網站結構同流程（俾之後接手嘅 AI／開發者）

最後更新：2026-11-06。項目背景、用戶決定同規則見 `CLAUDE.md`；未做嘅嘢見 `docs/TODO.md`。

## 1. 整體

```
用戶（手機／電腦）
   │  密碼 GEN_PASSWORD（header x-password）
   ▼
jlawreportgenerate（本 repo，Railway）── app/server.py：網頁＋API＋排隊＋排程
   │  每個 job：app/agent.py（大盤）／app/stock.py（個股）
   │
   ├─ jlaw-report 網站 API（姊妹 repo mhcha20/Jlaw-report）
   │     /api/drive/ls（列 Drive 資料夾）、/api/shots（截圖齊唔齊）、/api/ohlcv（日線，Yahoo）、
   │     /api/sync（Drive 報告清單）、/pdf/<id>（下載報告）、/api/upload（上載；op=jlaw-list／jlaw-get 讀 J Law 材料）、
   │     /api/sheet（股票清單 Google Sheet）── 後三個要 JLAW_ADMIN_PASSWORD
   ├─ Google Drive 直接下載截圖（drive.google.com/uc?export=download&id=…，資料夾係連結分享）
   ├─ Claude API（claude-opus-5-5）── 主力
   └─ xAI Grok（Responses API，grok-4.7）── 後備
```

本 repo 冇 Google 金鑰：Drive 嘅讀寫全部經 jlaw-report 網站代做。

## 2. 檔案

| 路徑 | 做咩 |
|---|---|
| `app/server.py` | 標準庫 HTTP 伺服器。網頁、API、job 排隊（`WORKERS` 條 thread，默認 2；大盤 job 用 `MARKET_LOCK` 一次一份）、每日排程、每日清單。job 紀錄同 PDF 存 `DATA_DIR/jobs/<id>/`（Railway volume `/data`）。重新啟動時未完成嘅 job 標失敗，唔自動重跑（避免重複收費）。 |
| `app/static/index.html` | 單檔前端（大盤／個股兩個分頁、報告紀錄、PDF 閱讀窗）。手機 390px 闊度要測。 |
| `app/jlaw.py` | 所有對 jlaw-report 網站嘅 call：截圖、報告、上載、J Law 材料、股票清單 Sheet（行業）、日期計算。 |
| `app/agent.py` | `Job`（大盤報告）：準備材料 → `analyze()`（Claude，出錯轉 Grok）→ 工具 `build_report` 跑 build → PDF。`StockJob` 繼承佢。 |
| `app/stock.py` | `StockJob`（個股報告）：個股截圖、行情、上一份報告、當日大盤報告、ESTC 格式範本 → 同一個 `analyze()` → `gen/build.py`。 |
| `app/grok.py` | Grok 後備：xAI Responses API（`/v1/responses`，`store:false`，每輪重送全部對話，SSE 串流），伺服器端 `web_search`＋function `build_report`。 |
| `gen/market/` | 大盤報告框架（由 Jlaw-report `tools/stockreport/market/` 搬過嚟）：`prep.py` 攞行情、`mlib.py` 計算／QA 登記、`report.py` 版面、`qa.py` PDF 文字回查、`build.py` 出 PDF＋擋位、`format_check.py` 格式擋位（網站版先有）、`template_work.py` work 檔範本。 |
| `app/asia.py`／`gen/amarket/` | 香港／日本／韓國大盤報告（2026-11-06）：`AsiaJob`；框架由 `gen/market/` 改，市場設定喺 `profiles.py`，`AMARKET` 環境變數揀市場，資料喺 `gen/amarket/data/<mkt>/`。 |
| `gen/` | 個股報告框架（由 Jlaw-report `tools/stockreport/` 搬過嚟）：`lib.py` 指標／圖表、`gen.py` 計劃數字＋行動卡、`gen2.py` 本體報告＋附錄、`prep.py` 行情＋裁圖、`build.py`（網站版，改過）、`format_stock.py` 格式擋位、`sqa.py` QA 登記、`render.py` HTML→PDF（Python Playwright）、`style.css`。 |
| `gen/sig/` | `signals.js`（由 Jlaw-report **原封不動**複製）＋`sigcheck.js`：用報告中心同一套規則解析行動卡，確保入到買賣訊號／回測。要 Node ≥20（Dockerfile 由 `node:22-slim` 複製 node）。 |
| `docs/` | AI 分析用嘅指令同筆記：`jw-market-analysis-prompt.md`（大盤指令）、`jlaw-myt-stock-prompt-v2.md`（個股指令 V2.0）、`jlaw-method-notes.md`＋`MYT-jlaw-notes-260923.pdf`（J Law 方法）、`WORKER*.md`（流程，原本俾 Claude Code 排程用）、`STOCKREPORT_README.md`（生成器欄位說明）。 |
| `Dockerfile`／`railway.json` | Playwright Python 映像＋poppler＋Noto 字體＋ImageMagick＋Node 22；healthcheck `/health`。 |

## 3. 出報告流程

### 3.1 大盤（`agent.Job.run`）
1. `jlaw.market_shots(date)`：Drive 大盤截圖根 `1M8hNhlePL5MHD-_SvGZlQ02srBHFq_rl`／`DD mon YYYY`，要齊 19 張 `NN_TICKER_Daily.png`。
2. `gen/market/prep.py DATE`：經 `/api/ohlcv` 攞 SPY QQQ IWM、11 板塊、SMH，存 `gen/market/data/`（共用，所以一次一份）。
3. 上一份大盤報告、格式範本（`FORMAT_REF`，默認 `2026-10-30_美股大盤分析_JW框架_Claude核實版`）、J Law 材料（10 日內最新 3 份）。
4. `analyze()`：system prompt＝WORKER_MARKET＋大盤指令＋J Law 方法＋mlib／report／template 源碼＋格式範本全文；user＝19 張圖＋重算數字＋上一份報告＋J Law 材料。
5. AI 寫 work 檔（Python：`spec`／`texts`／`qa`），經 `build_report` 提交 → `gen/market/build.py`：
   - 冇 TODO、19 張都睇過、`qa()` ≥20 項全過、PDF 文字回查（qa.py）、頁數 ≤16（有 J Law ≤20）
   - `FORMAT_STRICT=1`：`format_check.py` 對 10/30 範本篇幅（頁數 ≥9／有 J Law ≥10、每節字數、行數…）
   - 失敗 → 錯誤交返 AI 改，最多 `MAX_BUILDS`（默認 10）次；連續 3 輪唔交就停
6. 成功 → 每頁縮圖俾 AI 檢查版面 → 收尾。檔名 `<DATE>_美股大盤分析_JW框架_{Claude|Grok}核實版.pdf`。

### 3.2 個股（`stock.StockJob.run`）
1. `jlaw.stock_shots(ticker, date)`：個股根 `1xkPBlGhK0SEn2dGIzAINQNIFL33m0hG_`／代號／`DD mon YYYY`。美股 01–17、ETF（檔名有 `Fund_`）01–12、亞洲（全數字）01–14、外國股／ADR（`ADR_TICKERS`）15 可缺。
2. `gen/prep.py images`（裁 Futubull 圖，06–09 拼表）＋`gen/prep.py data`（存 `gen/data/<T>_<DATE>.json`）。
3. 上一份行動卡＋本體報告；美股承襲當日大盤報告（Claude核實版優先，冇就最近一份）；亞洲股冇大盤報告。
4. 格式範本 `FORMAT_REF_STOCK`（默認 `2026-10-30_ESTC_`：行動卡／股票分析終極報告／核對附錄三份）。
5. 同一個 `analyze()`；`gen/build.py`（`STOCK_STRICT=1`）擋：
   - 冇 TODO、今日動作 ≤40 字、朗讀稿字數、`qa()` ≥20 項全過
   - **評等同分數對應**：★ <30｜★★ 30–49｜★★★ 50–69｜★★★★ 70–89｜★★★★★ ≥90
   - 行動卡 1 頁、本體 ≤10 頁；`signals.js` 解析到日期、V2.0 標記、評等、分數、三條價位、3 個警報、未持倉／已持倉
   - `format_stock.py`：本體 ≥9 頁、附錄 ≥3 頁、每格字數／行數（約範本六至七成）
6. 輸出 `<DATE>_<T>_行動卡.pdf`、`_股票分析終極報告.pdf`、`_核對附錄.pdf`。

### 3.3 Claude／Grok
- `ANTHROPIC_API_KEY` 有 → Claude（`claude-opus-5-5`，adaptive thinking，effort `high`，`fallbacks:"default"`，`web_search_20260209`，prompt caching，串流）。`anthropic.APIError` 重試後仍失敗或 refusal → 有 `XAI_API_KEY` 就由頭用 Grok；已經有過 QA 嘅 PDF 就用嗰份。
- 冇 Claude key → 直接 Grok。job 記 `engine`。用量估算：Claude 按 $4／$20（快取讀 $0.2、寫 $5）每百萬 token；Grok 按 `XAI_PRICE_IN`／`OUT`（默認 2／6），**上網搜尋費未計**。

## 4. API（要登入：Google cookie `jlgen_session`，或者密碼登入未關時 header `x-password`；`/`、`/health`、`/api/me`、`/auth/*` 唔使）

登入：`GET /auth/google` → Google → `GET /auth/callback`（驗 state cookie、換 token、驗 aud／iss／email_verified、email 要喺 `ALLOWED_EMAILS`）→ 發 cookie；`GET /auth/logout` 清 cookie；`GET /api/me` 回 `{user, google, password}`。邏輯喺 `app/auth.py`。


| 方法 路徑 | 做咩 |
|---|---|
| GET `/api/jobs` | 最近 30 個 job（冇 log） |
| GET `/api/jobs/<id>` | 一個 job（有 log） |
| GET `/api/jobs/<id>/pdf?i=` | 第 i 份 PDF |
| GET `/api/jobs/<id>/page?i=&p=`（`&count=1` 回頁數） | 第 i 份 PDF 第 p 頁 PNG（網頁閱讀窗用） |
| POST `/api/jobs/<id>/upload` | 上載全部 PDF 去報告中心 Drive（同名舊檔放垃圾桶） |
| POST `/api/generate` | `{date, upload}` 大盤；`{kind:"stock", date, tickers:[…], upload}` 個股 |
| POST `/api/generate`（亞洲） | `{kind:"amarket", date, markets:["hk","jp","kr"], upload, engine}` |
| GET `/api/market_ready?date=&tickers=` | 出個股前：邊啲市場當日大盤報告未上載 Drive（網頁先問） |
| GET `/api/asia_shots?date=` | 三個市場截圖狀態＋本站／Drive 做過未 |
| GET `/api/dates` | 大盤日期＋個股日期（`stock_dates`＝大盤日期＋最近 10 個工作日） |
| GET `/api/shots?date=` | 大盤 19 張截圖狀態 |
| GET `/api/stocks?date=` | 個股清單（狀態、版面、行業 theme、名） |
| GET／POST `/api/watchlist` | 每日清單（`DATA_DIR/watchlist.json`） |
| POST `/api/auth` | 試密碼 |

## 5. 排程
`AUTO_MARKET=1`：每 15 分鐘，香港 `AUTO_START`–`AUTO_END`（默認 06:30–11:30），最近美股交易日截圖齊、Drive 未有報告、今日排程未試過 → 出一次大盤報告（失敗唔重試）；`AUTO_UPLOAD=1` 自動上載。**個股冇自動排程**（用戶揀咗手動，成本考慮）。亞洲大盤（2026-11-06）：`AUTO_ASIA`（默認跟 `AUTO_MARKET`），香港 17:30–21:30 平日，香港／日本／韓國截圖齊、Drive 未有就自動出，引擎默認 Gemini。

## 6. 同 Jlaw-report 嘅關係（要同步嘅地方）
- `gen/`、`gen/market/` 係由 Jlaw-report `tools/stockreport/` 搬過嚟，**兩邊改框架要同步**（Jlaw-report 舊排程仲用緊佢嗰份）。
- `gen/sig/signals.js` 要同 Jlaw-report 根目錄 `signals.js` 一樣（佢改解析規則、升 `VERSION` 時抄過嚟）。
- 截圖規則（美股 17／ETF 12／亞洲 14／外國股 15 可缺）同 Jlaw-report `server.js` `classifyShots`、`drive.py shots` 一致；外國股清單＝Jlaw-report `prices.js` 嘅 `OVERRIDE`＝本 repo `ADR_TICKERS`。
- 評等同分數對應規則兩邊都有（Jlaw-report `tools/stockreport/build.py`）。
- Jlaw-report 部署 branch `claude/drive-reports-whatsapp-share-6m44wo` 有保護，AI session 唔可以直接 push：開新 branch → PR → 用戶 merge。改 `tools/`、`docs/` 唔會觸發佢重新部署。

## 7. 本地測試
- `pip install -r requirements.txt`；字體：`npm` tarball `@fontsource/noto-sans-tc@5.3.1` 解壓去 `gen/node_modules/@fontsource/noto-sans-tc`；`cd gen/sig && npm install`。
- `CHROMIUM_PATH=/opt/pw-browsers/chromium`（cloud session 預裝 Chromium）。
- 出 PDF：用假行情寫 `gen/market/data/*.json`（大盤）或 `gen/data/<T>_<DATE>.json`（個股），配一個填好嘅 work 檔跑 `build.py`。AI 部分可以用模擬 SSE 伺服器（`XAI_BASE=http://127.0.0.1:…/v1`）測。
- 網頁：`GEN_PASSWORD=test DATA_DIR=<tmp> PORT=… WORKERS=0 python3 app/server.py`，再用 Playwright 390px 截圖。
