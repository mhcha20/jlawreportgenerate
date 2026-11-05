# 未做／已知問題／要留意（2026-11-06）

有新進展就更新呢份。做完嘅項目刪走或者移去「已完成」。

## 未驗證
- [ ] **Claude 實際出報告**：`ANTHROPIC_API_KEY` 2026-11-06 先加，未用 Claude 出過一份完整報告。要睇：質素、每份實際用量（估計 US$3–8）、prompt caching 有冇生效（`cache_read_input_tokens`）、server-side fallback 參數有冇被接受。
- [ ] **行業分類喺正式網站**：`jlaw.themes()` 經 jlaw-report `/api/sheet` 讀 Sheet，要報告中心已經「連接 Google」。如果網頁全部顯示「未分類」＝讀唔到。亞洲股（000660、2640、8136、7832、7202、7974、00077、03690、06811）多數唔喺 Sheet，會係「未分類」，要喺 Sheet 補 Focus Theme。
- [ ] **xAI 上網搜尋費**：用量估算未計 Grok `web_search` 每次搜尋嘅收費，要喺 xAI console 對賬。

## 用戶提過、可以做
- [ ] **報告中心「📸 截圖檢查」日期**：只加香港「當日」，過咗午夜就睇唔到上一個亞洲交易日（例如 11/06 凌晨睇唔到 11/05）。改法同本站 `jlaw.stock_dates()`（加最近幾個工作日）。要喺 Jlaw-report 開 PR 俾用戶 merge。
- [ ] **XLV 2026-11-04 要重出**：Grok 出咗 76 分 ★★★ 觀察，按新評等規則應該係 ★★★★ 值得買入。
- [ ] **舊卡評等標準唔同**：2026-11-05 之前嘅卡（292 張 V2.0）冇跟「每 20 分一級」，買賣訊號／回測會新舊混住，直至每隻出咗新卡。

## 可以考慮
- [ ] 個股自動排程（例如每日清單收市後自動出）。用戶暫時揀手動（成本：每隻約 US$2–8）。
- [ ] 「只出行動卡」模式（平啲、快啲）：Jlaw-report 有 `build.py --card`／`template_card.py`／`WORKER_CARD.md`，本站未開放。
- [ ] 每日跨股總表（Jlaw-report `tools/stockreport/daily.py`）未搬過嚟。
- [ ] 個股報告加 J Law 觀點（而家只有大盤報告用 J Law 材料）。
- [ ] Longbridge 收市核實／財報日（Jlaw-report `lbcheck.py`）本站冇；而家財報日靠 AI 上網搜尋。
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
