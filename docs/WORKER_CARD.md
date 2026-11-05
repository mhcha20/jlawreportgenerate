# WORKER_CARD.md — 單隻股票「只出一頁行動卡」流程（MODE=card；非重點股每日用）

同 `WORKER.md` 一套規則，但**唔出本體報告／核對附錄**，所以唔使寫朗讀稿、`fund_rows`、`sr_rows` 等；目的係用較少 token 令每隻股票每日都有一張 V2.0 卡（網站買賣訊號／回測只認 V2.0 卡）。先讀 `WORKER.md`（第 0、1、2、4、5、6 節同「實測補充」「亞洲」「ETF」「評等字眼」「已持倉價位被跌穿」「唔好提群組執行規則」），再按下面做。

## 流程
1. **截圖**：`drive.py shots <日期資料夾id> /tmp/<TICKER>`（亞洲 `--asia`；ETF 見 `OK (ETF 12 張版面)`）。唔齊 → `status=incomplete`，唔好估。
2. **數據**：`python3 prep.py data <TICKER> <DATE>`（最後一根要＝DATE；失敗按 WORKER.md 第 2 節處理）。`prep.py images` 可省（Futubull 財報頁直接睇原圖）。
3. **睇圖（用 Read 睇圖像，唔用文字辨識）**：行動卡九構面要全部評分，所以至少睇 **01 日線、02 週線、05 Futubull 日線、06 關鍵指標、07 損益、12 全部持有人、14 機構、16 預測評級、17 估值**；03／04（4H／2H）、08–11、13、15 需要先睇。ETF／亞洲缺頁按 WORKER.md 標「缺項」。
4. **大盤**：美股用 `drive.py market` 當日 `<D>_美股大盤分析_JW框架_Claude核實版`（`drive.py pdf` 下載，`pdftotext` 讀市況分類同板塊），`S['mkt_state']`／`S['mkt_ref']` 照佢；冇 D 版就用最新一份並喺 `foot` 註明承襲。亞洲股：`mkt_ref`＝『無（只用圖面指數）』。
5. **上一份**：`drive.py reports <TICKER> <上一個交易日>` → 有我哋嘅 V2.0 卡就 `S['prior_same']=True`，`S['prior']` 寫『YYYY-MM-DD 評等 分數／100』；只有 Gemini 舊卡／群友卡 → `prior_same=False`，照寫評等分數並標來源；冇 → 『無』。`biggest` 要同上一份比（評等／分數／價位／收市）。
6. **寫 work 檔**：複製 `template_card.py` → `work/<TICKER>_<DATE>.py`，填晒 spec（九構面每格一句理由、A／B 路徑價位、減倉／離場、`action` ≤40 字）同 texts 四欄。價位規則同 WORKER.md 第 4 節（止損％÷入場價、距離％÷現價；減倉／離場價只放第 3、5 格；已持倉未跌穿線就寫「續抱，按警報價處理」）。
7. **QA**：寫 `work/qa_<TICKER>.py` 由 `data/<TICKER>_<DATE>.json` 重算你喺 spec／texts 寫死嘅每個數字（52 週高低、均線、ATR、量比、各價位距離％、R 值、`biggest` 入面嘅升跌％）；錯就改，更正項數寫入 `corr`。
8. **出卡＋測試**：
   ```
   python3 build.py <TICKER> <DATE> work/<TICKER>_<DATE>.py --card    # → out/<DATE>_<TICKER>_行動卡.pdf（1 頁）
   node sigtest.js out/<DATE>_<TICKER>_行動卡.pdf                      # 要見到 date、評等、score、levels(buy/trim/stop)、alerts 3 條、flat/held 分類啱
   ```
   `sigtest` 嘅 flat／held 分類要同你 `action` 嘅意思一致（例如寫「觀望」就要係「零新倉／觀望」、寫「吸納」就係「條件式建倉」）；唔啱就改字眼再出。
9. **上載**：`python3 drive.py upload out/<DATE>_<TICKER>_行動卡.pdf`（replace=1 自動取代同名舊檔；唔好用 `drive.py trash`）。
10. **回報**一行 JSON：`{"ticker","date","mode":"card","status":"done|incomplete|failed","rating","score","tier","corrections":N,"notes":"…"}`。

## 唔好做
- 唔好 commit／push、唔好改通用檔（`gen.py`／`lib.py`／`template_*.py`）。
- 唔好編造查唔到嘅數字（財報日、機構持股）；寫「未公布」「缺項」。
- 唔好出現「群組」「執行規則」「檔案①②③」字眼；評等只用六個固定字眼。
