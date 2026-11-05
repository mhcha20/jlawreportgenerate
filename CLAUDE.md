# JLaw 報告生成器（jlawreportgenerate）

給日後對話嘅項目背景。用戶用廣東話溝通，回覆請用廣東話（繁體）。

## 呢個項目係咩
- **主要用途：出報告。** 用戶要求（2026-11-05）：網站攞返 Google Drive 嘅截圖，撳一個掣就 generate **大盤報告**，同之前 Claude Code 排程 session 寫嘅報告一樣，只係改喺網站自己生成。另有每日定時排程。個股報告（行動卡）之後再加。
- 流程（`app/agent.py`）：經 jlaw-report 網站 API 攞 19 張大盤截圖（`/api/drive/ls`＋Drive 下載）→ `gen/market/prep.py` 攞行情（`/api/ohlcv`）→ 讀上一份大盤報告（`/api/sync`＋`/pdf/<id>`）→ call Claude API（`claude-opus-5-5`，adaptive thinking，effort high，server-side fallback `"default"`，web_search 核實催化劑／日程）→ Claude 寫 work 檔，經自訂工具 `build_report` 跑 `gen/market/build.py`（QA 擋位：≥20 項重算、PDF 文字回查、頁數上限），失敗就將錯誤交返 Claude 改，最多 `MAX_BUILDS` 次 → 成功後俾 Claude 睇每頁縮圖檢查版面 → PDF。
- **後備 Grok**（用戶 2026-11-05 要求）：Claude API 出錯（`anthropic.APIError`，重試後仍失敗）或拒絕（refusal）時，如有 `XAI_API_KEY` 就由頭改用 xAI Grok（`app/grok.py`，xAI **Responses API** `https://api.x.ai/v1/responses`，`store:false`、每輪重送；伺服器端 `web_search` 上網核實＋function `build_report`；模型 `XAI_MODEL` 默認 `grok-4.7`，$2／$6 每百萬 token）做同一流程。Claude 已經出到過 QA 嘅 PDF 就唔會轉。冇 `ANTHROPIC_API_KEY` 就直接用 Grok。job 記錄 `engine`（claude／grok），網頁標「後備 Grok」。Grok 用量按 `XAI_PRICE_IN／OUT` 估。
- **格式硬性跟 10/30 範本**（用戶 2026-11-05 要求）：每次由 Drive 攞 `FORMAT_REF`（默認 `2026-10-30_美股大盤分析_JW框架_Claude核實版`）全文放入 system prompt 做格式範本；`gen/market/format_check.py`（`FORMAT_STRICT=1`，網站默認開）喺 build 擋：頁數（≥9，有 J Law ≥10）、每節篇幅、行數（past_events ≥5、next_week ≥4、next_rows ≥5、verify_rows ≥4、action_rows ≥3、group_summary ≥150 字等），唔夠就失敗交返 AI 補。改門檻改呢個檔。
- **J Law 觀點對照**：有 `JLAW_ADMIN_PASSWORD` 時經 jlaw-report `/api/upload?op=jlaw-list／jlaw-get` 讀私人資料夾發布日 ≤ 分析日、10 日內最新 3 份，放入 user 訊息；有材料就要求 `jlaw_html`（`JLAW_REQUIRED=1`）。J Law 材料唔好入 repo。
- `gen/`：由 `Jlaw-report/tools/stockreport/` 搬過嚟嘅大盤框架（`market/mlib.py`、`report.py`、`qa.py`、`template_work.py`、`prep.py`、`build.py`、`style.css`）。唯一改動：`build.py` 改用 `gen/render.py`（Python Playwright）出 PDF，唔使 node。兩邊改框架要同步。
- `app/server.py`：純標準庫 HTTP 伺服器。網頁 `app/static/index.html`（全部 API 要 `x-password`＝`GEN_PASSWORD`）。一次只跑一個 job（`gen/market/data` 共用）。job 紀錄、PDF 存 `DATA_DIR/jobs/<id>/`（Railway volume 掛 `/data`）。重新部署時未完成嘅 job 標失敗，唔會自動重跑（避免重複收費）。
- 排程：`AUTO_MARKET=1` 時每 15 分鐘查一次，香港時間 `AUTO_START`–`AUTO_END`（默認 06:30–11:30）內，最近美股交易日截圖齊而 Drive 未有報告就自動出一次（失敗唔重試）；`AUTO_UPLOAD=1` 自動上載。
- 部署：Railway，`Dockerfile`（Playwright Python 映像＋poppler＋Noto 字體），`railway.json` healthcheck `/health`。環境變數：`ANTHROPIC_API_KEY`、`XAI_API_KEY`（後備）、`GEN_PASSWORD`、`JLAW_ADMIN_PASSWORD`（＝jlaw-report 嘅 `ADMIN_PASSWORD`，上載用）、選填 `JLAW_SITE`、`DATA_DIR`、`CLAUDE_MODEL`、`CLAUDE_EFFORT`、`MAX_BUILDS`、`AUTO_*`。
- 本地測試：`CHROMIUM_PATH=/opt/pw-browsers/chromium`；cloud session 嘅網絡連唔到 jlaw-report 網站同 Drive，只可以用假行情測 build／版面。
- 姊妹項目 `mhcha20/Jlaw-report`（報告中心網站，`jlaw-report-a74806.up.railway.app`）：列報告、買賣訊號、回測。佢入面嘅 `tools/stockreport/` 暫時保留，新服務穩定之前舊排程照用。

## 參考資料（分析時一定要用）
- `docs/jlaw-method-notes.md`：**J Law 技術分析／交易方法筆記**，由用戶上傳嘅 51 頁 MYT 文件（`MYT_____compressed_260923_101201.pdf`，J Law「超績投資客」課程筆記）整理：基礎框架、ETF、Swing trade、VCP、拉回買入、勝率與報酬風險比、動能與趨勢、S&R、趨勢線／通道（Overshoot、假突破）、移動平均線、見頂四訊號、K 線形態、見底八訊號、套牢處理。**用戶 2026-11-05 要求呢個網站要記住呢份文件**：生成器 call Claude 嘅 system prompt 要包含呢份筆記，評分同價位要按呢套方法。
- 原始 PDF：`docs/MYT-jlaw-notes-260923.pdf`（用戶 2026-11-05 要求放入 repo）。筆記有疑問時以原文為準。
- `docs/jw-market-analysis-prompt.md`：**JW 大盤分析指令｜群組共用補充版 V1.0**（每日大盤＋板塊：資料核實規則、SPY／QQQ／IWM、成交量、廣度／VIX、板塊輪動、催化劑、情境、報告格式）。截圖喺 Drive `1M8hNhlePL5MHD-_SvGZlQ02srBHFq_rl`（日期資料夾 `DD mon YYYY`，19 張 `NN_TICKER_Daily.png`）。美股個股報告要先有當日大盤報告。大盤生成程式喺 `Jlaw-report/tools/stockreport/market/`（`WORKER_MARKET.md`），之後搬過嚟。
- `docs/jlaw-myt-stock-prompt-v2.md`：**JLaw × MYT 股票分析終極指令 V2.0**（行動卡七格、分析紀律十條、R1–R4）。

## 約定
- **唔好提交任何密碼、金鑰、token。** repo 係公開嘅。
