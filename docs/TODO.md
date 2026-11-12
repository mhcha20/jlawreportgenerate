# 未做／已知問題／要留意（2026-11-12 更新）

有新進展就更新呢份。做完嘅項目刪走或者移去「已完成」。

## 未驗證
- [ ] **Claude 實際出報告**：`ANTHROPIC_API_KEY` 2026-11-06 先加，未用 Claude 出過一份完整報告。要睇：質素、每份實際用量（估計 US$3–8）、prompt caching 有冇生效（`cache_read_input_tokens`）、server-side fallback 參數有冇被接受。
- [ ] **行業分類喺正式網站**：`jlaw.themes()` 經 jlaw-report `/api/sheet` 讀 Sheet，要報告中心已經「連接 Google」。如果網頁全部顯示「未分類」＝讀唔到。亞洲股（000660、2640、8136、7832、7202、7974、00077、03690、06811）多數唔喺 Sheet，會係「未分類」，要喺 Sheet 補 Focus Theme。
- [ ] **xAI 上網搜尋費**：用量估算未計 Grok `web_search` 每次搜尋嘅收費，要喺 xAI console 對賬。

- [ ] **MYT 筆記擴充版**（2026-11-06）：`docs/jlaw-method-notes.md` 按原文逐頁重整（約 2 萬 → 4.4 萬 bytes，加原文頁數、圖例、第 15 節報告應用對照）。睇下一批報告有冇更多引用 J Law 規則（出貨日、VCP 收縮數、拉回八點、止損 8%）；Grok 每輪重送 system prompt，每份約多 US$0.1–0.2。

- [ ] **Longbridge 直連**（2026-11-06 加）：睇部署 log 有冇 `longbridge OK:`；之後出一份美股＋一份港股報告，睇收市核實、業績日有冇寫入附錄。Access Token 有期限，過期要喺 Longbridge 開發者後台續期再改 Railway Variables（報告中心嗰組都要改）。2026-11-06 部署 log `longbridge OK`；大盤報告亦已接（15 隻 ETF 收市核實＋補 bar），睇下一份大盤報告第二節有冇寫。

- [ ] **慳費用改動**（2026-11-06）：Grok 第一次提交 work 檔之後唔再重送截圖、舊版 work 檔、舊 build 結果、舊縮圖（`grok._compact`）；build 失敗時將 QA 失敗／擋位行放最頂、寫入 job log；QA 失敗講清楚重算值 vs 寫死值同容差；個股 prompt 補 5 個漏咗嘅最低字數（setup 等）；大盤 prompt 加 format_check 最低要求。之前：FPS 9 次 build US$7.9、ESTC US$5.3、大盤 US$3.8（全部 Grok，Anthropic 額度未增值）。下一批量吓每次重試幾錢；job log 而家會印「今輪輸入 N token（快取 M）」，睇 xAI 有冇自動快取。xAI 上網搜尋費（大盤一份 24 次）未計入估算。

- [ ] **Gemini 比較**（2026-11-06 加）：睇部署 log 有冇 `gemini OK`（原生 API＋Google 搜尋喺 cloud session 測唔到，要喺 Railway 驗證）；之後同一隻股票／同一日用 Gemini 同 Grok 各出一份，比較 QA／擋位重試次數、數字準唔準同用量，再決定日常用邊個。Gemini 價錢係估計（`GEMINI_PRICE_*`），要喺 Google AI Studio／Cloud Billing 對賬；網上資料話 gemini-4-argon 2026-11-30 後加價（$4／$20）。

- [ ] **Gemini 第一批結果**（2026-11-06，全部 11/05、gemini-4-argon）：FPS 3 次 build 約 US$1.35（Grok 9 次 US$7.93，結論相同）；XLV 3 次約 US$1.10；SPCX 11 次約 US$4.71（第 2–8 次本體 11 頁刪唔夠，第 9 次過咗仲交多兩次）。快取有效（後期每輪 >85% 快取）。之後加咗：超頁數時話 AI 刪幾多字＋最長欄位、Gemini 篇幅提醒、過咗 QA 最多再改 1 次（`POST_SUCCESS_BUILDS`）。下一批睇 build 次數有冇跌。

- [ ] **推介**（2026-11-06 加）：11/05 試計頭幾名 2640、7832（升穿觸發＋放量新高）、GRID、PANW、AIPO（跌穿離場／減倉）。用一兩星期睇推介準唔準、權重要唔要調（`app/suggest.py` `_score`）；業績日只喺 Railway 有 Longbridge 時先計。

- [ ] **亞洲大盤報告**（2026-11-06 加，未出過真報告）：要等 Mac `bash mac/update.sh` 之後 17:15 排程（或手動 `capture_market_charts.py --market hk`）上載 `HK`／`JP`／`KR` 截圖。第一份出咗要睇：AI 有冇照美股範本結構寫、篇幅門檻（`gen/amarket/format_check.py`）要唔要調、build 次數同用量、廣度／資金流有冇上網核實到。2026-11-06 三份都出咗並上載（全部 Gemini）：香港 1 次 build US$0.72；韓國 US$0.87；日本兩次中途卡住（Gemini 搜尋 120 秒超時、寫 work 檔前 >5 分鐘冇資料 → 改 300 秒搜尋限時、900 秒串流限時、思考中都撳得停），之後發現 Yahoo 1321／1306 價格比例錯誤再重做，最終 14 頁、均線同量比正確。三份都 14–15 頁，篇幅標準等用戶睇完再定。同日加咗：自動排程（17:30–21:30）、亞洲股個股承襲同市場大盤報告、J Law 觀點（選填）。下一個交易日睇排程有冇自動出三份、用量、J Law 一節寫成點。

- [ ] **升跌符號同顏色**（2026-11-06）：美股＋亞洲大盤報告改 ▲ 綠／▼ 紅（`mlib`／`alib` 嘅 `P／N／AR`）。Jlaw-report `tools/stockreport/market/mlib.py` 未同步（舊排程仲用 ＋）；個股報告（`gen/lib.py` 等）未改，用戶未要求。下一份睇 AI 自己寫嘅文字有冇跟 ▲／▼。
- [x] **J Law 報告上載**（2026-11-06 加）：網頁卡 →`/api/jlaw_upload`。用戶 11/06 上載咗 JLawStock 5 Nov 2026（Drive 檔名 `2026-11-05_JLaw_Stock_5Nov2026_readable.pdf`，只限擁有者，冇公開分享）；11/06 日本／韓國大盤報告 log 已讀到 3 份 J Law 材料並寫咗 J Law 一節。個股報告暫時唔用 J Law 材料。
- [ ] **自動上載**（2026-11-06）：Railway 已開 `AUTO_UPLOAD=1`（重新部署 23:58 生效）。第一次排程（11/07 星期六朝早美股 11/06 大盤）要睇報告紀錄有冇「已上載 Drive：檔名」。
- [ ] **出個股前檢查大盤報告**（2026-11-06）：`/api/market_ready` ＋ confirm。本機用真 Drive 資料試過（11/06 美股未有 → 彈；港股有 → 唔彈），正式網站未見用戶撳過。
- [x] **📸 網頁遙控 Mac 截圖**（2026-11-07 加；用戶已安裝，網頁顯示「🟢 Mac 在線」，11/09–11/12 用過檢查、截股票、更新、加股票）：網站分頁＋`app/capture.py`＋screencapture `bin/remote_agent.py`。雲端用模擬 Mac 試過：排隊、執行、log、一隻失敗其餘照做、停止、壞代號／錯 token 被拒；正式網站錯 token 回 401。**未喺真 Mac 試**：要用戶行 `bash mac/remote-setup.sh`、將 token 貼入 Railway `CAPTURE_TOKEN`，網頁見到「🟢 Mac 在線」先算通。要留意：Mac Python 有冇 CA 證書（冇就自動改用 curl）、`update` 動作完之後 launchd 有冇重開 agent。
- [ ] **網頁報告紀錄**（2026-11-07）：每次顯示 10 份＋「顯示多 10 份」、錯誤兩行、J Law 卡收埋、分頁掣固定頂部；「重做全部失敗」只喺失敗篩選出現，要再輸入份數先做（用戶怕撳錯）。

## 2026-11-07 至 11-12 加嘅功能（用戶要求）同驗證情況
- [x] **自訂股票清單**（11-07）：可以改名、加多幾個清單；之後用戶覺得一粒粒彩色掣分唔清「揀咗」定「剔咗」，改成下拉揀清單＋「剔晒呢個清單」掣（已剔晒變灰「✓」）。
- [x] **📸 截圖分頁揀股票唔使打字**（11-07）：清單掣、「揀截圖未齊／未有」、逐隻撳；日期掣顯示實際日期；iPhone 日期格同掣疊埋（11-08 改成兩行）。
- [x] **推介顏色**（11-07）：🟡「兩樣都有」改 ⚖️「夾喺兩線之間」，每行加字標，列表頂加顏色說明。
- [x] **只出行動卡**（11-08）：「出咩：三份齊／只出行動卡」。**實數**（11-08 第一批 8 隻，全部 Gemini）：每隻約 US$0.27–0.34、3–6 分鐘（之前估 US$1–2），有兩隻第一次今日動作超 40 字被擋、自己改短再過。
- [x] **上一張卡之後已跌穿**（11-08）：`stock.level_breach()`＋`post_build_check()`。CAT 11/03 卡離場線 600、11/04 收市 591.3 跌穿 → 用戶重出 11/06 只出卡，log 預先提示，結果「已持倉：今日離場」。限制：減倉線只喺報告中心最新嗰張就係上一張時先查到（`/api/signals` history 冇存減倉線）。
- [x] **Mac 閒置／忙碌**（11-10）：📸 分頁顯示 ⚪ 閒置／🟠 排程或截圖忙緊（中文）／🔵 做緊網頁動作＋開始時間。
- [x] **加／移除截圖股票**（11-12）：📸 分頁「➕ 加／移除截圖股票」→ Yahoo 核對正式名 → 用戶確認 → Mac `stock_registry.py`。11-12 用戶加 00700，Mac 開咗 Drive 資料夾，試截 14／14 張齊、富途公司名核對過。**未試過**：移除（搬去「停止截圖」）、日股／韓股經網站加、美國 ETF 經網站加。
- [x] **報告中心共用清單**（11-12，Jlaw-report PR #10 已 merge）：報告中心「⭐ 清單」選單＝呢度嘅清單。第一次正式網站顯示「唔接受」：原因係我要求密碼 ≥8 字，已改成兩邊一樣就得。**要用戶再試一次確認讀到**。
- [x] **Key Study List 11/10**（11-11）：15 隻美股加入截圖（screencapture），11/11 全部 17／17 張齊。用戶規定：加股票前一定要核對公司名俾佢確認（VSXY 教訓：Victoria's Secret 由 VSCO 改咗代號，我一度誤當打錯）。

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
- **Yahoo 價格比例錯誤**（2026-11-06 日本報告 AI 發現）：1321 10/05–06 收 7.28／7.35（正常約 710，量大 100 倍）、1306 03/30–31 收 37.6（細 10 倍）；`/api/ohlcv`（報告中心）原樣傳出。`gen/amarket/prep.py fix_scale()` 同前後 5 根中位數比、接近 10 嘅次方就還原並寫 warn。掃過 115 隻個股同美股／港韓大盤數據冇其他（BMNR 2025-06 係真實急升）。報告中心 `prices.js`／`mergeOhlcv` 已經喺 Jlaw-report PR #9（2026-11-06 用戶 merge）加 `fixScale()` 根治，`/api/ohlcv` 而家 1321 10/05 收 727.90。
- **Yahoo 指數收市後 close＝null**（2026-11-06 ^N225）：`gen/amarket/prep.py yahoo_index` 用 `regularMarketPrice` 補（`regularMarketTime` ≥ 開市 6.4 小時後），同報告中心 `fillMissingClose` 一樣。
- 部署（push 或者改 Railway Variables）會中斷做緊嘅 job；出緊報告就唔好部署。
- `gen/market/data` 係共用目錄，大盤 job 一定要一次一份（`MARKET_LOCK`）。
- Grok 嘅 Responses API 喺有圖嘅情況要 `store:false`，所以每輪重送全部對話（19 張圖），輸入 token 會多。
- Jlaw-report repo 名大細楷：remote 要用 `https://github.com/mhcha20/Jlaw-report.git`；部署 branch 唔准 AI session 直接 push。
- repo 係公開嘅：唔好提交密碼、金鑰、token、J Law 私人材料、每隻股票嘅分析內容（work 檔）。`docs/MYT-jlaw-notes-260923.pdf` 係用戶要求放入嘅。

## 已完成（摘要）
- 2026-11-08 至 11-12：只出行動卡、跌穿檢查、Mac 閒置／忙碌、網站加／移除截圖股票（美股＋港日韓）、報告中心共用清單、Key Study List 15 隻（詳情見上面「2026-11-07 至 11-12」）。
- 2026-11-07：自訂股票清單（多個、改名、下拉＋剔晒掣）、截圖分頁揀股票唔使打字、推介顏色說明。
- 2026-11-07：網頁短咗（報告紀錄分頁顯示、J Law 卡收埋、重做全部雙重確認）；📸 網頁遙控 Mac 截圖（待 Mac 設定）。
- 2026-11-06：Longbridge 直連（個股＋大盤）、Gemini 引擎、承襲價位規則（失效重訂、跌穿當日照舊、價位次序）、推介、Grok 慳費用、亞洲大盤報告（香港／日本／韓國框架、網頁分頁、自動排程、J Law 一節、亞洲個股承襲）、升跌 ▲ 綠／▼ 紅、J Law 上載、出個股前檢查大盤報告、AUTO_UPLOAD、Yahoo 價格比例錯誤還原（亞洲 prep＋報告中心 PR #9 已 merge）、Gemini 超時／停止修正。
- 2026-11-05：大盤報告網站、Grok 後備（Responses API＋上網）、10/30 大盤格式範本＋擋位、J Law 對照、個股三份報告（ESTC 範本＋擋位、signals.js 解析）、ADR 外國股截圖規則（兩邊）、評等同分數對應（兩邊）、PDF 同一版閱讀、個股排序／篩選／行業分組、亞洲股日期、每日清單。
