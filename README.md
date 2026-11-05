# JLaw 報告生成網站（jlawreportgenerate）

由 Google Drive 嘅截圖，撳一個掣就出 **美股大盤報告** 同 **個股報告**（行動卡＋本體報告＋核對附錄）。AI（Claude，出錯就轉 Grok）睇圖、上網核實、寫報告，QA 同格式擋位全過先出 PDF，出完可以一撳上載去報告中心。

- 網站：https://jlawreportgenerate-production.up.railway.app （撳「用 Google 登入」，只有 `ALLOWED_EMAILS` 入面嘅 Gmail 入得）
- 姊妹網站（報告中心）：https://jlaw-report-a74806.up.railway.app （repo `mhcha20/Jlaw-report`）

> **之後搵 AI 接手：** 叫佢先讀 `CLAUDE.md`（項目背景同規則）、`docs/ARCHITECTURE.md`（結構同流程）、`docs/TODO.md`（未做／已知問題）。

## 點用

### 大盤報告
1. 「大盤報告」分頁揀美國交易日，網站會即時檢查 Drive 嗰 19 張截圖齊唔齊。
2. 撳「出報告」。網頁可以閂，伺服器照做；大約 10–20 分鐘。
3. 「報告紀錄」入面撳掣喺同一版睇 PDF，滿意就撳「上載 Drive」。
- 有 J Law 觀點材料（私人資料夾，分析日前 10 日內）就會自動加「J Law 觀點對照」一節。
- 每朝香港 06:30–11:30 截圖齊就會自動出（`AUTO_MARKET=1`）。

### 個股報告
1. 「個股報告」分頁揀交易日（亞洲股收市後已經揀得，唔使等美股）。
2. 揀股票：
   - **⭐ 每日清單**：一撳剔晒每日睇嘅股票；剔完可以改，撳「將而家剔咗嘅存做每日清單」更新。
   - 可以搜尋代號／名稱、按代號排或按行業分組、按市場（美股／ETF／亞洲／外國股）篩選、「揀晒呢組」。
3. 撳「出報告」。同一時間做 2 隻，其餘排隊；每隻約 15–25 分鐘、約 US$2–8。
4. 每隻有「行動卡／本體報告／核對附錄」三個掣，同一版睇；「上載 Drive」三份一齊上載。
- 美股要先有當日大盤報告（個股「市場配合」會承襲）。

## 部署（Railway）

Project `loving-renewal` → service `jlawreportgenerate`，跟 GitHub `main` 自動部署（`Dockerfile`）。Volume 掛 `/data`。

| 變數 | 用途 |
|---|---|
| `GOOGLE_CLIENT_ID`／`GOOGLE_CLIENT_SECRET` | 用 Google 登入（可以同報告中心共用同一個 OAuth 用戶端；Google Cloud Console 要加重新導向 URI `https://jlawreportgenerate-production.up.railway.app/auth/callback`） |
| `ALLOWED_EMAILS` | 准登入嘅 Gmail（逗號分隔；默認 etchan112@gmail.com,manhey@gmail.com） |
| `GEN_PASSWORD` | 舊密碼登入：只喺未設定 Google 時用（設好 Google 就自動關；`PASSWORD_LOGIN=1` 可以保留） |
| `ANTHROPIC_API_KEY` | Claude API（主力） |
| `XAI_API_KEY` | xAI Grok（Claude 出錯時後備；冇 Claude key 就直接用） |
| `JLAW_ADMIN_PASSWORD` | 報告中心嘅 `ADMIN_PASSWORD`：上載 Drive、讀 J Law 材料、讀股票清單 Sheet（行業分類） |
| `AUTO_MARKET`／`AUTO_UPLOAD` | `1`＝每朝自動出大盤報告／出完自動上載 |
| 選填 | `CLAUDE_MODEL`、`CLAUDE_EFFORT`、`XAI_MODEL`、`MAX_BUILDS`、`WORKERS`、`ADR_TICKERS`、`FORMAT_REF`、`FORMAT_REF_STOCK`、`AUTO_START`／`AUTO_END` 等（見 `docs/ARCHITECTURE.md`） |

改 Variables 或者 push 都會重新部署（約 1–2 分鐘）：**部署期間撳掣會出 502，做緊嘅報告會中斷**（標失敗，要再撳）。

**唔好將任何密碼、金鑰、token 提交入 repo**（repo 係公開嘅）。
