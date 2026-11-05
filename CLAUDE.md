# JLaw 報告生成器（jlawreportgenerate）

給日後對話嘅項目背景。用戶用廣東話溝通，回覆請用廣東話（繁體）。

## 呢個項目係咩
- **主要用途：出報告。** 一個網站（Railway 部署），輸入股票代號＋日期就出 JLaw × MYT V2.0 報告（第一版先做一頁行動卡），亦有每日定時排程。
- 流程：經 jlaw-report 網站 API 攞截圖（Drive）同日線 → call Claude API（睇截圖寫九構面評分／價位／文字，結構化 JSON）→ 用 V2.0 生成器框架（由 `mhcha20/Jlaw-report` 嘅 `tools/stockreport/` 搬過嚟）計數同出 PDF → 下載或上載 Drive。
- 姊妹項目 `mhcha20/Jlaw-report`（報告中心網站，`jlaw-report-a74806.up.railway.app`）：列報告、買賣訊號、回測。佢入面嘅 `tools/stockreport/` 暫時保留，新服務穩定之前舊排程照用。

## 參考資料（分析時一定要用）
- `docs/jlaw-method-notes.md`：**J Law 技術分析／交易方法筆記**，由用戶上傳嘅 51 頁 MYT 文件（`MYT_____compressed_260923_101201.pdf`，J Law「超績投資客」課程筆記）整理：基礎框架、ETF、Swing trade、VCP、拉回買入、勝率與報酬風險比、動能與趨勢、S&R、趨勢線／通道（Overshoot、假突破）、移動平均線、見頂四訊號、K 線形態、見底八訊號、套牢處理。**用戶 2026-11-05 要求呢個網站要記住呢份文件**：生成器 call Claude 嘅 system prompt 要包含呢份筆記，評分同價位要按呢套方法。
- 原始 PDF 屬課程材料，**唔好提交入 repo**（repo 係公開嘅），只放整理筆記。
- `docs/jlaw-myt-stock-prompt-v2.md`：**JLaw × MYT 股票分析終極指令 V2.0**（行動卡七格、分析紀律十條、R1–R4）。

## 約定
- **唔好提交任何密碼、金鑰、token。** repo 係公開嘅。
