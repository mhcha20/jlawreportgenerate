"""stock.py — 個股 V2.0 報告 job（行動卡＋本體報告＋核對附錄），做法同大盤一樣：
Drive 截圖 → 行情（gen/prep.py）→ 上一份報告＋當日大盤報告 → Claude／Grok 睇圖、上網核實、寫 work 檔 → gen/build.py（QA＋signals.js＋格式擋位）→ 三份 PDF。
流程規則照 docs/WORKER.md（排程 Claude session 用嘅版本）。"""
import datetime as dt, glob, json, os, subprocess, sys
from zoneinfo import ZoneInfo
import agent, jlaw, longbridge as lb
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
- 評等要同分數對應（每 20 分一級，build 會擋）：★ 避免交易 <30｜★★ 不建議 30–49｜★★★ 觀察 50–69｜★★★★ 值得買入 70–89｜★★★★★ 強烈買入 ≥90（分數＝九構面星數÷45×100），rating 寫「★★★ 觀察」咁、stars 同星數一致；唔好用「買入」單獨做評等。今日動作照 WORKER.md 寫法（已持倉唔好寫減倉／離場，除非已跌穿）。
- 第 6 格要有固定句「回踩區入場（主目標 x.xxR）」。唔好提「群組」「執行規則」。
- 評分、價位、形態判斷要參考 J Law 方法筆記（VCP、拉回買入、S&R、趨勢線、均線、見頂見底訊號）。
- **承襲價位規則**（用戶 2026-11-06 決定，三個引擎都係）：減倉線、離場線、止損、回踩入場區、順勢觸發——**未失效**就照用上一份嘅數字，唔准改；**已失效**（以收市價計：跌穿止損／減倉／離場線、回踩區已喺現價上面、順勢觸發已被升穿等，條線已經冇用）就一定要重訂一條**有理據**嘅新位（前浪低／高、S&R 區間、均線、趨勢線、ATR、底部形態，寫出計法），唔好死守失效舊價，亦唔好冇理據咁「機械下移」。正文原位寫明「舊 X（YYYY-MM-DD 收市已跌穿，失效）→ 新 Y（理據：…）」，行動卡價位用新值，附錄承襲對照表逐項列舊值、今日實際、新值同理由。冇上一份（首份）先全部自己訂。
- **跌穿當日嘅今日動作照舊價計**：承襲離場線今日收市跌穿＝已持倉「今日離場」；承襲減倉線跌穿＝「減倉」；就算同日重訂咗新價，今日動作都唔可以因為新價而改做續抱。重訂嘅新價由下一個交易日起先用（行動卡寫明「新價 x 由下一交易日起生效」）。
- **價位次序**（build 會擋）：回踩區下限 ≥ 減倉線 ≥ 離場線 ≥ 回踩止損（減倉線唔可以喺回踩區入面）。重訂時照呢個次序；如果係未失效承襲價本身唔夾，照用承襲值，喺 S['level_note'] 寫明（≥20 字）。
- S['ai_line'] 寫「AI：<模型識別碼>，直接閱讀截圖圖像。」

=== WORKER.md（流程；drive.py／prep.py／build.py／上載嘅步驟網站已經代你做，Longbridge 核實（收市核對、補 bar、下次業績日）網站已經代你做，結果喺 user 訊息「Longbridge 核實」一段；嗰段話冇就 notes 寫「冇 Longbridge 核實」）===
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

=== gen/sqa.py（qa() 用嘅 chk／chk_true，簽名照呢度，唔使試）===
{_read('gen/sqa.py')}

=== 格式擋位最低要求（gen/format_stock.py，第一次交就要達到，唔好等 build 攔低先補；每補一次都收費）===
- 朗讀稿：script3 寫 700–900 字（≥550、≤950）；scriptfull 寫 2,200–3,000 字（≥1,800、≤3,500）。寫完自己用 len() 數一次。
- 行動卡：S['sub'] ≥35 字；biggest ≥150；cost_tail ≥80，要有「回踩區入場（主目標 x.xxR）」；corr ≥40；foot ≥60。九構面每格理由 ≥30 字。
- 本體：oneliner ≥120；p1a／p1b／p1c 表現 ≥45、判斷 ≥10；stage_txt ≥120；hhhl ≥80；mom ≥50；vol_rows 6 行每行 ≥40；pattern ≥40；pattern_notes 2 條各 ≥30；
  sr_rows ≥5 行；pb／bo 各 3 點各 ≥35；canslim 7 行；fund_rows ≥6 行（每行 ≥3 格有內容）；risk 5 項各 ≥15；analyst_line／smart_line／sector_line ≥40；canslim_line ≥30；
  rrr_note ≥40、f1_note ≥30、f2_interp ≥40、plan_line ≥60、next3_line ≥40、vsprior ≥60、stage_test ≥30、earn_line ≥20；flat ≥50、held ≥30；next3 3 項；keep／noup 各 ≥4 項；q1–q4 各 ≥25；open ≥2 項各 ≥30；setup ≥15、swing_only ≥15、r3_note ≥20、zone_hi_def／zone_lo_def 各 ≥10（都要寫具體數字同理由）。
- 附錄：thr ≥5 行、caliber ≥4 項各 ≥25、conflicts ≥4、sources ≥4 項各 ≥15、smart ≥4 項各 ≥20、corr_html ≥120。頁數：本體 9–10 頁、附錄 ≥3 頁。

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
        s.log(f'已下載 {len(sh["files"])} 張截圖（{sh["kind"]} 版面）'); s.check_cancel()
        subprocess.run([sys.executable, os.path.join(GEN, 'prep.py'), 'images', t, sd], capture_output=True, text=True, timeout=300)
        lbs, lbmsg = None, ''
        if not lb.symbol(t): lbmsg = '今次冇 Longbridge 核實（日股／韓股 Longbridge 直連未驗證，照舊用 Yahoo＋截圖）'
        elif not lb.enabled(): lbmsg = '今次冇 Longbridge 核實（網站未設定 Longbridge 金鑰）'
        else:
            try: lbs = lb.daily_bars(t, 5); s.log('Longbridge 日線：' + '、'.join(sorted(lbs)))
            except lb.LBError as e: lbmsg = f'今次冇 Longbridge 核實（連唔到：{e}）'; s.log('⚠ ' + lbmsg)
        s.log('攞行情（jlaw-report /api/ohlcv）…')
        def prep_data(*extra):
            return subprocess.run([sys.executable, os.path.join(GEN, 'prep.py'), 'data', t, date, *extra], capture_output=True, text=True, timeout=300,
                                  cwd=GEN, env={**os.environ, 'JLAW_SITE': jlaw.SITE})
        p, lb_filled = prep_data(), False
        if p.returncode != 0 and '≠ 報告日' in (p.stderr + p.stdout) and lbs and date in lbs:   # Yahoo 缺當日 bar（例如亞洲股收市價 null）→ 用 Longbridge 補
            s.log(f'Yahoo 未有 {date} 收市 bar，用 Longbridge 補')
            p, lb_filled = prep_data('--extra', json.dumps([lbs[date]])), True
        if p.returncode != 0: raise RuntimeError('行情準備失敗：' + (p.stderr or p.stdout)[-1200:])
        s.log('行情齊：' + p.stdout.strip().splitlines()[-1][:200]); s.check_cancel()
        lbtxt = s.lb_verify(t, date, lbs, lbmsg, lb_filled)
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
        content.append({'type': 'text', 'text': f"""TICKER = {t}；分析交易日 DATE = {date}；版面 {sh['kind']}（{len(sh['files'])} 張）{'：外國股／ADR，冇美國內部人申報（第 15 張內部人' + ('有提供' if any(f['name'].startswith('15_') for f in sh['files']) else '冇') + '），機構支持構面嘅內部人一項標「缺項（ADR 冇內部人申報）」，唔當負面證據、覆蓋率如實列' if sh['kind'] == 'ADR' else ''}；香港分析時間 {hk:%Y-%m-%d %H:%M}；模型識別碼 {{MODEL_ID}}。
行情已準備好（data/{t}_{date}.json），以下係 metrics(t) 重算摘要（work 檔用 m 取值，唔好照抄寫死）：
{json.dumps(summary, ensure_ascii=False)}

Longbridge 核實（網站直連 Longbridge OpenAPI 代做，寫入附錄第三節同 notes）：
{lbtxt}

上一份報告（用嚟寫 prior／biggest／vsprior；先核對佢嘅日期同收市價）：{ptxt or '（冇，首份）'}

當日大盤報告（市場配合構面、R4 第一項、mkt_state／mkt_ref）：{mname or '（冇' + ('，亞洲股只用圖面指數' if sh['kind'] == 'ASIA' else '') + '）'}
{mtxt[:30000]}

請：①逐張睇晒截圖抄讀數；②下次財報日：上面 Longbridge 有就用佢（註明來源 Longbridge 財經日曆，以公司公告為準），冇先用 web_search 核實；用 web_search 核實近期新聞／催化劑、分析員評級（附來源同日期）；③九構面逐格評分寫理由、A／B 路徑價位、減倉／離場、今日動作；④寫完整 work 檔（spec／texts／qa），用 build_report 提交，失敗就改好再提交。成功後檢查縮圖版面，冇問題就用一兩句總結（評等、分數、今日動作）收尾。"""})
        return s.analyze(stock_system(ref), content)

    def lb_verify(s, t, date, lbs, lbmsg, lb_filled):
        """Longbridge 收市核實＋下次業績日 → 俾 AI 嘅一段文字（失敗唔會令報告失敗）"""
        if lbs is None: return lbmsg + '。notes 要寫「冇 Longbridge 核實」。'
        lines = []
        if lb_filled: lines.append(f'{date} OHLCV 來源係 Longbridge（Yahoo 未有當日收市 bar），附錄第三節要註明。')
        elif date not in lbs: lines.append(f'收市核實：Longbridge 未有 {date} 嗰根（有：{"、".join(sorted(lbs))}），今次未能核實收市。')
        else:
            try:
                b = json.load(open(os.path.join(GEN, 'data', f'{t}_{date}.json')))['bars'][-1]   # [MM-DD,o,h,l,c,v千股]
                ok, txt = lb.compare(lbs[date], dict(o=b[1], h=b[2], l=b[3], c=b[4], v=b[5] * 1000))
                lines.append(('收市核實：一致。' if ok else '收市核實：⚠ 不一致，附錄第三節要並列兩邊數字並查日期／復權。') + txt)
                s.log('Longbridge 收市核實：' + ('一致' if ok else '⚠ 不一致'))
            except Exception as e: lines.append(f'收市核實：比對失敗（{e}）。')
        try:
            er = lb.next_earnings(t, date)
            lines.append(f'下次業績日：{er[0]}（{er[1]}；來源 Longbridge 財經日曆，以公司公告為準）' if er else '下次業績日：Longbridge 財經日曆 45 日內查唔到（可以用 web_search 核實，查唔到先標「未公布」）')
            s.log('Longbridge 業績日：' + (er[0] if er else '45 日內冇'))
        except lb.LBError as e: lines.append(f'下次業績日：Longbridge 查詢失敗（{e}），用 web_search 核實'); s.log(f'⚠ Longbridge 業績日查詢失敗：{e}')
        return '\n'.join(lines)

    def inspect_prelude(s):
        return (GEN, f"import sys, os; sys.path.insert(0, {GEN!r}); os.chdir({GEN!r}); os.environ['JL_DATE'] = {s.date!r}\nfrom lib import *\nfrom gen import *\nm = metrics({s.ticker!r})")

    def build_cmd(s, wp):
        return ([sys.executable, os.path.join(GEN, 'build.py'), s.ticker, s.date, wp, '--out', s.dir],
                {'STOCK_STRICT': os.environ.get('STOCK_STRICT', '1'), 'JL_DATE': s.date})

    def on_success(s, info):
        s.pdfs = info['pdfs']; s.pdf = s.pdfs[0]; s.pages = sum(info['pages'].values()); s.info = info
        sg = info.get('signals') or {}
        s.log(f'build 成功：{info["rating"]} {info["score"]}／100｜{info["action"]}｜頁數 {info["pages"]}｜QA {info["qa_work"]} 項｜訊號 未持倉={sg.get("flat")} 已持倉={sg.get("held")}')
