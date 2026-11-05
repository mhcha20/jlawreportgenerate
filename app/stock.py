"""stock.py — 個股 V2.0 報告 job（行動卡＋本體報告＋核對附錄），做法同大盤一樣：
Drive 截圖 → 行情（gen/prep.py）→ 上一份報告＋當日大盤報告 → Claude／Grok 睇圖、上網核實、寫 work 檔 → gen/build.py（QA＋signals.js＋格式擋位）→ 三份 PDF。
流程規則照 docs/WORKER.md（排程 Claude session 用嘅版本）。"""
import datetime as dt, glob, json, os, subprocess, sys
from zoneinfo import ZoneInfo
import agent, jlaw
from agent import GEN, _read, img_block

FORMAT_REF_STOCK = os.environ.get('FORMAT_REF_STOCK', '2026-10-30_ESTC_')   # 個股格式範本（用戶 2026-11-05 指定）：Drive 檔名前綴，攞行動卡／股票分析終極報告／核對附錄三份


def stock_system(ref):
    return f"""你係 JLaw 報告中心嘅個股分析員，任務係出一隻股票嘅 V2.0 報告（三份 PDF：一頁行動卡、本體報告 9–10 頁、核對附錄），做法同 Claude Code 排程 session 完全一樣（WORKER.md），只係今次經 API 做：
你會收到當日截圖（圖像）、由行情重算嘅數字、上一份報告、當日大盤報告。你要逐張睇圖、用 web_search 核實下次財報日、近期新聞／催化劑、分析員評級（附來源同日期），然後寫一個完整嘅 work 檔（Python），用 build_report 工具提交。
build 會擋：work 檔冇 TODO、今日動作 ≤40 字、朗讀稿字數、行動卡 1 頁、本體 ≤10 頁、qa() ≥20 項重算全過、行動卡經 signals.js 解析（日期、評等、分數、三條價位、3 個警報、未持倉／已持倉）、格式擋位。失敗就照錯誤改好再提交。

規則重點：
- 用廣東話（繁體），語氣同之前報告一致。數字一律用 f-string 由 m／S 取值；寫死嘅數字要喺 qa(m, S, T) 用 `from sqa import chk, chk_true` 重算登記（≥20 項）。
- work 檔＝template_work.py 嘅結構（spec／texts）＋ qa()；只可以 import lib／gen（`from lib import *`）、sqa 同 Python 標準庫；唔好讀寫檔案、上網、subprocess。
- 圖面讀數睇唔清就寫「無法辨識」，唔好估；查唔到嘅（財報日、機構持股）寫「未公布」「缺項」，唔好編造。
- 評等只用六個固定字眼（強烈買入／值得買入／買入／觀察／不建議／避免交易），連星。今日動作照 WORKER.md 寫法（已持倉唔好寫減倉／離場，除非已跌穿）。
- 第 6 格要有固定句「回踩區入場（主目標 x.xxR）」。唔好提「群組」「執行規則」。
- 評分、價位、形態判斷要參考 J Law 方法筆記（VCP、拉回買入、S&R、趨勢線、均線、見頂見底訊號）。
- S['ai_line'] 寫「AI：<模型識別碼>，直接閱讀截圖圖像。」

=== WORKER.md（流程；drive.py／prep.py／build.py／上載嘅步驟網站已經代你做，Longbridge 核實今次冇，notes 寫「冇 Longbridge 核實」）===
{_read('docs/WORKER.md')}

=== JLaw × MYT 股票分析終極指令 V2.0 ===
{_read('docs/jlaw-myt-stock-prompt-v2.md')}

=== J Law 技術分析／交易方法筆記（MYT 文件整理）===
{_read('docs/jlaw-method-notes.md')}

=== 生成器說明（README）===
{_read('docs/STOCKREPORT_README.md')}

=== gen/lib.py（m＝metrics(t)，可用函數）===
{_read('gen/lib.py')}

=== gen/gen.py（plan_numbers、行動卡版面）===
{_read('gen/gen.py')}

=== gen/gen2.py（本體報告／核對附錄版面：每個 T 欄位點樣出現）===
{_read('gen/gen2.py')}

=== gen/template_work.py（work 檔範本：所有 TODO／0 都要換成當日內容；另加 qa(m, S, T)）===
{_read('gen/template_work.py')}
{ref}"""


import threading
_MLOCK = threading.Lock()


def metrics_summary(t, date):
    with _MLOCK:   # 兩個 worker 同時做個股：lib.load 讀環境變數 JL_DATE，要鎖住
        if GEN not in sys.path: sys.path.insert(0, GEN)
        import lib
        os.environ['JL_DATE'] = date
        m = lib.metrics(t)
    keys = ['close', 'prev', 'open', 'high', 'low', 'chg', 'chgp', 'gapp', 'clv', 'vol', 'v50', 'v20', 'volr50', 'volr20', 'ma10', 'ma20', 'ma50', 'ma200',
            'd10', 'd20', 'd50', 'd200', 'ma50_10', 'hi52', 'atr14', 'atrp', 'atr14w', 'ret5', 'ret20', 'dist', 'above50_30', 'n']
    out = {k: (round(m[k], 4) if isinstance(m[k], float) else m[k]) for k in keys if k in m}
    out['last_bars'] = m['bars'][-10:]
    out['closes_252_hi'] = max(m['closes'][-252:]); out['closes_252_lo'] = min(m['closes'][-252:])
    return out


class StockJob(agent.Job):
    def __init__(s, jid, date, ticker, folder, log):
        super().__init__(jid, date, folder, log); s.ticker = ticker

    def run(s):
        t, date = s.ticker, s.date
        s.log(f'檢查 Google Drive {t} 截圖…')
        sh = jlaw.stock_shots(t, date)
        if not sh['ok']: raise RuntimeError(sh['why'])
        sd = os.path.join(s.dir, 'shots'); os.makedirs(sd, exist_ok=True)
        for f in sh['files']: open(os.path.join(sd, f['name']), 'wb').write(jlaw.download(f['id']))
        s.log(f'已下載 {len(sh["files"])} 張截圖（{sh["kind"]} 版面）')
        subprocess.run([sys.executable, os.path.join(GEN, 'prep.py'), 'images', t, sd], capture_output=True, text=True, timeout=300)
        s.log('攞行情（jlaw-report /api/ohlcv）…')
        p = subprocess.run([sys.executable, os.path.join(GEN, 'prep.py'), 'data', t, date], capture_output=True, text=True, timeout=300,
                           cwd=GEN, env={**os.environ, 'JLAW_SITE': jlaw.SITE})
        if p.returncode != 0: raise RuntimeError('行情準備失敗：' + (p.stderr or p.stdout)[-1200:])
        s.log('行情齊：' + p.stdout.strip().splitlines()[-1][:200])
        summary = metrics_summary(t, date)
        try: prior = jlaw.prior_stock(t, date)
        except Exception as e: prior = {}; s.log(f'⚠ 讀唔到上一份報告：{e}')
        s.log('上一份：' + ('、'.join(v[0] for v in prior.values()) or '無'))
        mname, mtxt, same = (None, '', False)
        if sh['kind'] != 'ASIA':
            try: mname, mtxt, same = jlaw.market_report_for(date)
            except Exception as e: s.log(f'⚠ 讀唔到大盤報告：{e}')
            s.log(f'大盤報告：{mname or "無"}' + ('' if same or not mname else '（唔係當日，承襲最近一份，要喺 foot 註明）'))
        ref = ''
        if FORMAT_REF_STOCK:
            try:
                parts = [jlaw.report_by_name(FORMAT_REF_STOCK + k) for k in ('行動卡', '股票分析終極報告', '核對附錄')]
                ref = ('\n\n=== 格式範本（硬性跟足）===\n用戶要求每份個股報告嘅格式、每一格嘅寫法同篇幅都要同下面 ESTC 範本一樣（數字當然用當日嘅）：'
                       '行動卡七格每格都有具體數字同理由；本體報告每部分（大市三問、生命週期、趨勢表、VPA 六行、形態、S/R 五行、Pullback／Breakout 各三點、'
                       '機構、基本面八行、風險五類、交易計劃、三個強制欄位、九構面逐格理由、保留／不升級原因、與上一份逐項比較、最後四問、未決問題）都要寫到範本咁詳細；'
                       '核對附錄寫足口徑、對照差異、更正清單、資料來源。build 有格式擋位（format_stock.py），任何一格少過範本水平都會失敗，要補返先過。'
                       + ''.join(f'\n--- {n} ---\n{x[:40000]}' for n, x in parts if n))
                s.log('格式範本：' + ('、'.join(n for n, _ in parts if n) or '⚠ 搵唔到 ' + FORMAT_REF_STOCK))
            except Exception as e: s.log(f'⚠ 讀唔到格式範本：{e}')
        hk = dt.datetime.now(ZoneInfo('Asia/Hong_Kong'))
        content = []
        for f in sh['files']:
            fn = os.path.join(sd, f['name']); base = fn[:-4]
            use = base + '_t.png' if os.path.exists(base + '_t.png') else base + '_c.png' if os.path.exists(base + '_c.png') else fn
            content.append({'type': 'text', 'text': f'截圖 {f["name"]}（Drive 建立時間 UTC {f.get("createdTime", "?")}）' + ('（已裁切／拼接）' if use != fn else '')})
            content.append(img_block(open(use, 'rb').read()))
        ptxt = ''.join(f'\n--- {v[0]} ---\n{v[1][:30000]}' for v in prior.values())
        content.append({'type': 'text', 'text': f"""TICKER = {t}；分析交易日 DATE = {date}；版面 {sh['kind']}（{len(sh['files'])} 張）；香港分析時間 {hk:%Y-%m-%d %H:%M}；模型識別碼 {{MODEL_ID}}。
行情已準備好（data/{t}_{date}.json），以下係 metrics(t) 重算摘要（work 檔用 m 取值，唔好照抄寫死）：
{json.dumps(summary, ensure_ascii=False)}

上一份報告（用嚟寫 prior／biggest／vsprior；先核對佢嘅日期同收市價）：{ptxt or '（冇，首份）'}

當日大盤報告（市場配合構面、R4 第一項、mkt_state／mkt_ref）：{mname or '（冇' + ('，亞洲股只用圖面指數' if sh['kind'] == 'ASIA' else '') + '）'}
{mtxt[:30000]}

請：①逐張睇晒截圖抄讀數；②用 web_search 核實下次財報日、近期新聞／催化劑、分析員評級（附來源同日期）；③九構面逐格評分寫理由、A／B 路徑價位、減倉／離場、今日動作；④寫完整 work 檔（spec／texts／qa），用 build_report 提交，失敗就改好再提交。成功後檢查縮圖版面，冇問題就用一兩句總結（評等、分數、今日動作）收尾。"""})
        return s.analyze(stock_system(ref), content)

    def build_cmd(s, wp):
        return ([sys.executable, os.path.join(GEN, 'build.py'), s.ticker, s.date, wp, '--out', s.dir],
                {'STOCK_STRICT': os.environ.get('STOCK_STRICT', '1'), 'JL_DATE': s.date})

    def on_success(s, info):
        s.pdfs = info['pdfs']; s.pdf = s.pdfs[0]; s.pages = sum(info['pages'].values()); s.info = info
        sg = info.get('signals') or {}
        s.log(f'build 成功：{info["rating"]} {info["score"]}／100｜{info["action"]}｜頁數 {info["pages"]}｜QA {info["qa_work"]} 項｜訊號 未持倉={sg.get("flat")} 已持倉={sg.get("held")}')
