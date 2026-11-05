# JLaw 報告生成器（jlawreportgenerate）

給日後對話嘅項目背景。用戶用廣東話溝通，回覆請用廣東話（繁體）。

**接手先讀：** `README.md`（點用、部署）、`docs/ARCHITECTURE.md`（檔案、流程、API、擋位、同 Jlaw-report 要同步嘅地方）、`docs/TODO.md`（未驗證、未做、已知坑）。有新進展要更新 `docs/TODO.md`。

## 呢個項目係咩
- **主要用途：出報告。** 用戶要求（2026-11-05）：網站攞返 Google Drive 嘅截圖，撳一個掣就 generate **大盤報告**，同之前 Claude Code 排程 session 寫嘅報告一樣，只係改喺網站自己生成。另有每日定時排程。
- **個股報告**（用戶 2026-11-05 要求「所有個股做法同大盤一樣」）：三份齊出（行動卡＋本體報告＋核對附錄）；網頁「個股報告」分頁揀代號先出（唔自動做晒 115 隻，成本約 US$2–4／隻）。`app/stock.py` StockJob：jlaw-report `/api/shots` 列股票 → Drive 個股截圖（`SROOT` 1xkPBlGhK0SEn2dGIzAINQNIFL33m0hG_，美股 01–17、ETF 01–12、亞洲 01–14；`ADR_TICKERS`（默認 SCHN,NESN,MC,ATD，用戶 2026-11-05 指出係 ADR／外國股，冇內部人申報）第 15 張可缺，網頁照揀得）→ `gen/prep.py images`（裁 Futubull 圖）＋`data` → 上一份報告（行動卡＋本體）→ 美股承襲當日大盤報告（Claude核實版優先）→ 同一個 analyze（Claude，冇就 Grok）→ `gen/build.py`（網站版：`STOCK_STRICT=1` 要 `qa()` ≥20 項（`gen/sqa.py`）、行動卡用 `gen/sig/signals.js`（由 Jlaw-report 原封不動複製，網站改解析規則要同步）解析日期／評等／分數／三條價位／3 警報／未持倉已持倉、`format_stock.py` 格式擋位；**評等同分數要對應**（用戶 2026-11-05 決定每 20 分一級：★ 避免交易 <30｜★★ 不建議 30–49｜★★★ 觀察 50–69｜★★★★ 值得買入 70–89｜★★★★★ 強烈買入 ≥90），唔夾就 build 失敗）。`WORKERS`（默認 2）個 job 同時做；大盤 job 有 MARKET_LOCK 一次一份。**個股格式範本＝2026-10-30 ESTC**（用戶 2026-11-05 指定，「所有格式都照跟」）：`FORMAT_REF_STOCK` 默認 `2026-10-30_ESTC_`，由 Drive 攞三份全文放入 system prompt；`gen/format_stock.py` 按範本篇幅（約六至七成）擋：本體 ≥9 頁、附錄 ≥3 頁、行動卡每格字數、九構面理由 ≥30 字、各部分行數同字數、朗讀稿 ≥550／1800 字等。
- 流程（`app/agent.py`）：經 jlaw-report 網站 API 攞 19 張大盤截圖（`/api/drive/ls`＋Drive 下載）→ `gen/market/prep.py` 攞行情（`/api/ohlcv`）→ 讀上一份大盤報告（`/api/sync`＋`/pdf/<id>`）→ call Claude API（`claude-opus-5-5`，adaptive thinking，effort high，server-side fallback `"default"`，web_search 核實催化劑／日程）→ Claude 寫 work 檔，經自訂工具 `build_report` 跑 `gen/market/build.py`（QA 擋位：≥20 項重算、PDF 文字回查、頁數上限），失敗就將錯誤交返 Claude 改，最多 `MAX_BUILDS` 次 → 成功後俾 Claude 睇每頁縮圖檢查版面 → PDF。
- **後備 Grok**（用戶 2026-11-05 要求）：Claude API 出錯（`anthropic.APIError`，重試後仍失敗）或拒絕（refusal）時，如有 `XAI_API_KEY` 就由頭改用 xAI Grok（`app/grok.py`，xAI **Responses API** `https://api.x.ai/v1/responses`，`store:false`、每輪重送、**串流（SSE）**：每步進度記入 job log，`XAI_IDLE_TIMEOUT`（默認 300 秒）冇資料就當斷線重試；伺服器端 `web_search` 上網核實＋function `build_report`；模型 `XAI_MODEL` 默認 `grok-4.7`，$2／$6 每百萬 token）做同一流程。Claude 已經出到過 QA 嘅 PDF 就唔會轉。冇 `ANTHROPIC_API_KEY` 就直接用 Grok。job 記錄 `engine`（claude／grok），網頁標「後備 Grok」。Grok 用量按 `XAI_PRICE_IN／OUT` 估。
- **格式硬性跟 10/30 範本**（用戶 2026-11-05 要求）：每次由 Drive 攞 `FORMAT_REF`（默認 `2026-10-30_美股大盤分析_JW框架_Claude核實版`）全文放入 system prompt 做格式範本；`gen/market/format_check.py`（`FORMAT_STRICT=1`，網站默認開）喺 build 擋：頁數（≥9，有 J Law ≥10）、每節篇幅、行數（past_events ≥5、next_week ≥4、next_rows ≥5、verify_rows ≥4、action_rows ≥3、group_summary ≥150 字等），唔夠就失敗交返 AI 補。改門檻改呢個檔。
- **J Law 觀點對照**：有 `JLAW_ADMIN_PASSWORD` 時經 jlaw-report `/api/upload?op=jlaw-list／jlaw-get` 讀私人資料夾發布日 ≤ 分析日、10 日內最新 3 份，放入 user 訊息；有材料就要求 `jlaw_html`（`JLAW_REQUIRED=1`）。J Law 材料唔好入 repo。
- `gen/`（個股）：由 `Jlaw-report/tools/stockreport/` 搬過嚟 `lib.py`、`gen.py`、`gen2.py`、`template_work.py`、`template_card.py`、`prep.py`；`build.py` 改咗（Python 渲染、`--out`、QA／signals.js／格式擋位）。流程文件 `docs/WORKER.md`、`WORKER_CARD.md`、`STOCKREPORT_README.md`。
- `gen/market/`：由 `Jlaw-report/tools/stockreport/` 搬過嚟嘅大盤框架（`market/mlib.py`、`report.py`、`qa.py`、`template_work.py`、`prep.py`、`build.py`、`style.css`）。唯一改動：`build.py` 改用 `gen/render.py`（Python Playwright）出 PDF，唔使 node。兩邊改框架要同步。
- **網頁**（用戶 2026-11-05 要求）：PDF 喺同一版閱讀窗睇（`/api/jobs/<id>/page?i=&p=` 用 pdftoppm 轉 110dpi PNG，快取 `view_<i>_<p>.png`；另有下載／新分頁）；個股清單按代號排（字母 A–Z 先、數字由細到大）或按行業分組，可按市場（截圖齊／美股／ETF／亞洲／外國股／截圖未齊或未有）同行業篩選。**每日清單**（用戶 2026-11-06 要求）：「⭐ 每日清單」一撳就剔晒（截圖未齊／未有嘅唔剔，列出嚟），剔完可改；「將而家剔咗嘅存做每日清單」存去 `DATA_DIR/watchlist.json`（`GET/POST /api/watchlist`，所有裝置共用），未存過默認 CAT FPS AAPL ESTC BE XLV PLTR NVDA MCD SPCX WM COPX。個股日期選單＝美股大盤日期＋最近 10 個工作日（`jlaw.stock_dates()`，用戶 2026-11-05 反映亞洲股 11/05 截圖已出但揀唔到），默認＝最近一個港股已收市工作日（香港 16:30 前用上一個）。行業＝股票清單 Google Sheet A 欄 Focus Theme（`jlaw.themes()` 經 jlaw-report `/api/sheet`，要 `JLAW_ADMIN_PASSWORD`、報告中心已連 Google；「(續)」併入原組；冇喺 Sheet 嘅＝未分類）。
- `app/server.py`：純標準庫 HTTP 伺服器。網頁 `app/static/index.html`（全部 API 要 `x-password`＝`GEN_PASSWORD`）。`WORKERS`（默認 2）條 thread；大盤 job 用 `MARKET_LOCK` 一次一份（`gen/market/data` 共用）。job 紀錄、PDF 存 `DATA_DIR/jobs/<id>/`（Railway volume 掛 `/data`）。重新部署時未完成嘅 job 標失敗，唔會自動重跑（避免重複收費）。
- 排程：`AUTO_MARKET=1` 時每 15 分鐘查一次，香港時間 `AUTO_START`–`AUTO_END`（默認 06:30–11:30）內，最近美股交易日截圖齊而 Drive 未有報告就自動出一次（失敗唔重試）；`AUTO_UPLOAD=1` 自動上載。
- 部署：Railway，`Dockerfile`（Playwright Python 映像＋poppler＋Noto 字體），`railway.json` healthcheck `/health`。環境變數：`ANTHROPIC_API_KEY`、`XAI_API_KEY`（後備）、`GEN_PASSWORD`、`JLAW_ADMIN_PASSWORD`（＝jlaw-report 嘅 `ADMIN_PASSWORD`，上載用）、選填 `JLAW_SITE`、`DATA_DIR`、`CLAUDE_MODEL`、`CLAUDE_EFFORT`、`MAX_BUILDS`、`AUTO_*`。
- 本地測試：`CHROMIUM_PATH=/opt/pw-browsers/chromium`；cloud session 網絡有時連唔到 jlaw-report／Drive／api.x.ai（視乎環境設定），連唔到就用假行情同模擬 AI 伺服器測（見 `docs/ARCHITECTURE.md` 第 7 節）。
- 姊妹項目 `mhcha20/Jlaw-report`（報告中心網站，`jlaw-report-a74806.up.railway.app`）：列報告、買賣訊號、回測。佢入面嘅 `tools/stockreport/` 暫時保留，新服務穩定之前舊排程照用。

## 參考資料（分析時一定要用）
- `docs/jlaw-method-notes.md`：**J Law 技術分析／交易方法筆記**，由用戶上傳嘅 51 頁 MYT 文件（`MYT_____compressed_260923_101201.pdf`，J Law「超績投資客」課程筆記）整理：基礎框架、ETF、Swing trade、VCP、拉回買入、勝率與報酬風險比、動能與趨勢、S&R、趨勢線／通道（Overshoot、假突破）、移動平均線、見頂四訊號、K 線形態、見底八訊號、套牢處理。**用戶 2026-11-05 要求呢個網站要記住呢份文件**：生成器 call Claude 嘅 system prompt 要包含呢份筆記，評分同價位要按呢套方法。
- 原始 PDF：`docs/MYT-jlaw-notes-260923.pdf`（用戶 2026-11-05 要求放入 repo）。筆記有疑問時以原文為準。
- `docs/jw-market-analysis-prompt.md`：**JW 大盤分析指令｜群組共用補充版 V1.0**（每日大盤＋板塊：資料核實規則、SPY／QQQ／IWM、成交量、廣度／VIX、板塊輪動、催化劑、情境、報告格式）。截圖喺 Drive `1M8hNhlePL5MHD-_SvGZlQ02srBHFq_rl`（日期資料夾 `DD mon YYYY`，19 張 `NN_TICKER_Daily.png`）。美股個股報告要先有當日大盤報告。大盤生成程式已搬到 `gen/market/`（原本喺 `Jlaw-report/tools/stockreport/market/`，流程 `docs/WORKER_MARKET.md`）。
- `docs/jlaw-myt-stock-prompt-v2.md`：**JLaw × MYT 股票分析終極指令 V2.0**（行動卡七格、分析紀律十條、R1–R4）。

## 約定
- **唔好提交任何密碼、金鑰、token。** repo 係公開嘅。
