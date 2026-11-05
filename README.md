# jlawreportgenerate

JLaw 報告生成網站：由 Google Drive 截圖，撳一個掣出「美股大盤分析（JW 框架）」PDF 報告（Claude API 睇圖分析、QA 全過先出），可上載到報告中心 Drive，亦可每日定時自動出。詳見 `CLAUDE.md`。

## Railway 部署
1. New Project → Deploy from GitHub repo → `mhcha20/jlawreportgenerate`（用 `Dockerfile`）。
2. Variables：`ANTHROPIC_API_KEY`、`GEN_PASSWORD`（網站登入密碼）、`JLAW_ADMIN_PASSWORD`（報告中心嘅 ADMIN_PASSWORD，上載用）；要每日自動出就加 `AUTO_MARKET=1`（同 `AUTO_UPLOAD=1`）。
3. 加 Volume，掛載路徑 `/data`（保存報告紀錄同 PDF）。
4. Settings → Networking → Generate Domain。
