# 未做／已知問題／要留意（2026-11-06）

有新進展就更新呢份。做完嘅項目刪走或者移去「已完成」。

## 未驗證
- [ ] **Claude 實際出報告**：`ANTHROPIC_API_KEY` 2026-11-06 先加，未用 Claude 出過一份完整報告。要睇：質素、每份實際用量（估計 US$3–8）、prompt caching 有冇生效（`cache_read_input_tokens`）、server-side fallback 參數有冇被接受。
- [ ] **行業分類喺正式網站**：`jlaw.themes()` 經 jlaw-report `/api/sheet` 讀 Sheet，要報告中心已經「連接 Google」。如果網頁全部顯示「未分類」＝讀唔到。亞洲股（000660、2640、8136、7832、7202、7974、00077、03690、06811）多數唔喺 Sheet，會係「未分類」，要喺 Sheet 補 Focus Theme。
- [ ] **xAI 上網搜尋費**：用量估算未計 Grok `web_search` 每次搜尋嘅收費，要喺 xAI console 對賬。

- [ ] **MYT 筆記擴充版**（2026-11-06）：`docs/jlaw-method-notes.md` 按原文逐頁重整（約 2 萬 → 4.4 萬 bytes，加原文頁數、圖例、第 15 節報告應用對照）。睇下一批報告有冇更多引用 J Law 規則（出貨日、VCP 收縮數、拉回八點、止損 8%）；Grok 每輪重送 system prompt，每份約多 US$0.1–0.2。

- [ ] **Longbridge 直連**（2026-11-06 加）：睇部署 log 有冇 `longbridge OK:`；之後出一份美股＋一份港股報告，睇收市核實、業績日有冇寫入附錄。Access Token 有期限，過期要喺 Longbridge 開發者後台續期再改 Railway Variables（報告中心嗰組都要改）。2026-11-06 部署 log `longbridge OK`；大盤報告亦已接（15 隻 ETF 收市核實＋補 bar），睇下一份大盤報告第二節有冇寫。

- [ ] **慳費用改動**（2026-11-06）：Grok 第一次提交 work 檔之後唔再重送截圖、舊版 work 檔、舊 build 結果、舊縮圖（`grok._compact`）；build 失敗時將 QA 失敗／擋位行放最頂、寫入 job log；QA 失敗講清楚重算值 vs 寫死值同容差；個股 prompt 補 5 個漏咗嘅最低字數（setup 等）；大盤 prompt 加 format_check 最低要求。之前：FPS 9 次 build US$7.9、ESTC US$5.3、大盤 US$3.8（全部 Grok，Anthropic 額度未增值）。下一批量吓每次重試幾錢；job log 而家會印「今輪輸入 N token（快取 M）」，睇 xAI 有冇自動快取。xAI 上網搜尋費（大盤一份 24 次）未計入估算。

- [ ] **Gemini 比較**（2026-11-06 加）：睇部署 log 有冇 `gemini OK`（原生 API＋Google 搜尋喺 cloud session 測唔到，要喺 Railway 驗證）；之後同一隻股票／同一日用 Gemini 同 Grok 各出一份，比較 QA／擋位重試次數、數字準唔準同用量，再決定日常用邊個。Gemini 價錢係估計（`GEMINI_PRICE_*`），要喺 Google AI Studio／Cloud Billing 對賬；網上資料話 gemini-4-argon 2026-11-30 後加價（$4／$20）。

## 用戶提過、可以做
- [ ] **報告中心「📸 截圖檢查」日期**：只加香港「當日」，過咗午夜就睇唔到上一個亞洲交易日（例如 11/06 凌晨睇唔到 11/05）。改法同本站 `jlaw.stock_dates()`（加最近幾個工作日）。要喺 Jlaw-report 開 PR 俾用戶 merge。
- [ ] **XLV 2026-11-04 要重出**：Grok 出咗 76 分 ★★★ 觀察，按新評等規則應該係 ★★★★ 值得買入。
- [ ] **舊卡評等標準唔同**：2026-11-05 之前嘅卡（292 張 V2.0）冇跟「每 20 分一級」，買賣訊號／回測會新舊混住，直至每隻出咗新卡。

## 可以考慮
- [ ] 個股自動排程（例如每日清單收市後自動出）。用戶暫時揀手動（成本：每隻約 US$2–8）。
- [ ] 「只出行動卡」模式（平啲、快啲）：Jlaw-report 有 `build.py --card`／`template_card.py`／`WORKER_CARD.md`，本站未開放。
- [ ] 每日跨股總表（Jlaw-report `tools/stockreport/daily.py`）未搬過嚟。
- [ ] 個股報告加 J Law 觀點（而家只有大盤報告用 J Law 材料）。
- [ ] 部署時嘅 502：Railway 切換新 container 嗰幾秒前端會 502；可以喺前端遇到 502 自動等幾秒重試，或者顯示「伺服器重新啟動中」。
- [ ] 格式擋位門檻（`gen/market/format_check.py`、`gen/format_stock.py`）按實際出咗嘅報告再調；太嚴會令 AI 試好多次（每次都收費）。

## 2026-11-06 第一批 Claude 個股（10 隻亞洲股）觀察
- Claude 每隻約 US$5.6–6.8（Grok 約 US$2.5＋搜尋費）。
- 已改：朗讀稿等最低字數預先寫入 prompt（之前幾乎每隻第一次都因 scriptfull <1,800 字被攔，每補一次約 US$0.5–0.7）；加 `inspect_data` 工具（之前 Claude 用 build_report 嚟 probe 資料，浪費 build 次數）；prompt 附 `gen/sqa.py`。改完要再量一批睇用量有冇跌。
- 已改：`gen/lib.py` 量比除數係 0（極少成交股，例 00077）當 NaN／N/A，唔再 division by zero。

## 2026-11-06 Anthropic 額度用完
- 20:37（UTC）起 Claude 回「credit balance is too low」，自動轉 Grok。要喺 console.anthropic.com Plans & Billing 增值先再用 Claude。
- Grok 每份去到 US$7–10：Grok（store:false）每輪重送成段對話連截圖，`inspect_data` 用 12 次就貴好多。已改：Grok 最多 3 次（`INSPECT_MAX_GROK`）。之後量一份睇返用量。

## 要記住嘅坑
- 部署（push 或者改 Railway Variables）會中斷做緊嘅 job；出緊報告就唔好部署。
- `gen/market/data` 係共用目錄，大盤 job 一定要一次一份（`MARKET_LOCK`）。
- Grok 嘅 Responses API 喺有圖嘅情況要 `store:false`，所以每輪重送全部對話（19 張圖），輸入 token 會多。
- Jlaw-report repo 名大細楷：remote 要用 `https://github.com/mhcha20/Jlaw-report.git`；部署 branch 唔准 AI session 直接 push。
- repo 係公開嘅：唔好提交密碼、金鑰、token、J Law 私人材料、每隻股票嘅分析內容（work 檔）。`docs/MYT-jlaw-notes-260923.pdf` 係用戶要求放入嘅。

## 已完成（摘要）
- 2026-11-05：大盤報告網站、Grok 後備（Responses API＋上網）、10/30 大盤格式範本＋擋位、J Law 對照、個股三份報告（ESTC 範本＋擋位、signals.js 解析）、ADR 外國股截圖規則（兩邊）、評等同分數對應（兩邊）、PDF 同一版閱讀、個股排序／篩選／行業分組、亞洲股日期、每日清單。
