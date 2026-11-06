"""asia.py — 香港／日本／韓國大盤報告 job（用戶 2026-11-06 要求三個市場各出一份）。
同美股大盤 job（agent.Job）一樣：Drive 截圖（大盤根資料夾 HK／JP／KR 子資料夾）→ gen/amarket/prep.py 行情 → 上一份同市場報告 →
同一個 analyze（Claude，冇就 Grok；可揀 Gemini）→ gen/amarket/build.py（QA＋格式擋位）→ PDF。港股 ETF 收市同 Longbridge 核對。"""
import datetime as dt, json, os, subprocess, sys
from zoneinfo import ZoneInfo
import agent, jlaw
import longbridge as lb
from agent import GEN, _read, img_block

sys.path.insert(0, os.path.join(GEN, 'amarket'))
from profiles import PROFILES

ADIR = os.path.join(GEN, 'amarket')
FORMAT_REF = os.environ.get('FORMAT_REF', '2026-10-30_美股大盤分析_JW框架_Claude核實版')


def data_summary(mkt, date):
    code = ("import json, os, sys; sys.path.insert(0, %r); from alib import *\nm = Market(%r)\n"
            "out = {'market': %r, 'date': m.date, 'prev_date': m.pdate, 'missing': m.missing, 'tickers': {}, 'index': {}}\n"
            "for t, s in m.sym.items():\n"
            "    st, mi = s.dist_days()\n"
            "    out['tickers'][t] = dict(name=m.name(t), shot=SHOT_OF[t], o=s.o, h=s.h, l=s.l, c=s.c, pc=s.pc, chgp=round(s.chgp, 4), v=s.v, v50=round(s.v50()), vr=round(s.vr(), 2),"
            " ma={k: round(s.ma(k), 4) for k in (10, 20, 50, 200)}, h52=s.h52, l52=s.l52, ret5=round(s.ret5, 4), ret20=round(s.ret20, 4), dist_strict=st, dist_micro=mi)\n"
            "for k, s in m.idx.items(): out['index'][k] = dict(c=s.c, pc=s.pc, chgp=round(s.chgp, 4), h=s.h, l=s.l, ma50=round(s.ma(50), 2), ma200=round(s.ma(200), 2), ret5=round(s.ret5, 4), ret20=round(s.ret20, 4))\n"
            "print(json.dumps(out, ensure_ascii=False))") % (ADIR, date, mkt)
    p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=120, env={**os.environ, 'AMARKET': mkt}, cwd=GEN)
    if p.returncode != 0: raise RuntimeError('行情摘要失敗：' + p.stderr[-800:])
    return json.loads(p.stdout.strip().splitlines()[-1])


def system_prompt(pr, ref_name='', ref_txt=''):
    ref = (f"""

=== 結構範本（美股大盤報告 {ref_name}）===
亞洲報告冇自己嘅範本（第一份出咗用戶先定標準），結構、章節次序、表格、每節寫法參照呢份美股報告；內容同數字一律換成{pr['name']}市場（唔好照抄美股讀數或美股專用講法，例如 SPY、S5FI、VIX、11 個 SPDR 板塊）。
{ref_txt[:30000]}
""" if ref_txt else '')
    core = '、'.join(f"{x['shot']}（{x['name']}，對應{x['idx_name']}）" for x in pr['core'])
    sect = '、'.join(f"{x['shot']} {x['name']}" for x in pr['sectors'])
    return f"""你係 JLaw 報告中心嘅大盤分析員，任務係出「每日{pr['title']}」PDF（{pr['name']}股市，JW 大盤分析指令 V1.0 應用到{pr['name']}市場），經 API 做：
你會收到當日 {len(pr['shots'])} 張 TradingView 截圖（圖像，完整圖表頁：冇均線、冇 RSI）、由行情重算嘅數字、上一份同市場報告文字（第一份就冇）。
你要逐張睇圖、用 web_search 核實過去 5 個交易日{pr['name']}市場催化劑同未來一星期日程（本地經濟數據、央行、重要業績、影響本市場嘅美國／中國數據），
然後寫一個完整嘅 work 檔（Python），用 build_report 工具提交。build 會跑 QA 擋位（≥20 項重算、PDF 文字回查、頁數上限、格式）；失敗就睇錯誤訊息改好再提交，直至成功。

{pr['name']}市場設定（gen/amarket/profiles.py）：
- 主指數 ETF（等同美股 SPY／QQQ／IWM，量價、均線、派發日用佢計）：{core}。
- 板塊／權重股（等同美股板塊 ETF，睇相對強弱）：{sect}。
- 只有截圖讀數（Yahoo 冇）：{'、'.join(pr['chart_only'])}。{pr['breadth_note']}
- 時區 {pr['tz']}（{pr['tzname']}），收市 {pr['close']} 當地時間；價錢單位 {pr['unit']}。

規則重點：
- 用廣東話（繁體）寫報告內容。升跌一律用符號：升 ▲、跌 ▼（例：▲0.86%、▼1.36%）；唔好用「＋／+／-」表示升跌（用戶 2026-11-06 要求）。自己寫嘅數字用 P()／N() 就會自動加符號同紅綠色。
- 數字一律用 f-string 由 m／S 取值（價錢用 F()、指數 FI()、百分比 P()）；寫死嘅數字要喺 qa() 用 chk()／chk_true() 重算。
- 圖面讀數睇唔清就寫 None，唔好估。S['viewed'] 只列你真係睇過嘅截圖；S['meta']['ocr_used']=False。
- 廣度、資金流、波動指數：上網核實到先寫數字並附來源，搵唔到就標缺，唔好補造。
- 催化劑／日程：核實唔到就標「未核實」，唔好補造；附來源同日期。
- S['meta']['ai'] 寫實際模型識別碼（下面會俾你），mode 寫「網站 API 自動生成」。
- 市況判斷、關鍵價位要參考 J Law 方法筆記（均線、S&R、趨勢線／通道、見頂見底訊號）。
- work 檔只可以 import alib（`from alib import *`）同 Python 標準庫；唔好讀寫檔案、唔好上網、唔好 subprocess。
- 唔好出現「群組執行規則」相關句子。
- 格式擋位最低要求（gen/amarket/format_check.py，第一次交就要達到）：頁數 ≥6；inherit_note ≥60 字；sum_boxes ≥2 段各 ≥80；sum_rows 6 行（處置指示 ≥20，其餘各 ≥35）；gaps ≥3；
  breadth_qa／sector_qa 每答 ≥30；sync_box／ma_box／vol_box／dist_box／breadth_box／sector_box／catalysts_box 各 ≥30；vix_para ≥40；breadth_limits ≥25；levels_box ≥25；regime_box ≥60；history_html ≥40；next_week_foot ≥15；
  past_events ≥5 行（逐日）；next_week ≥3；next_rows ≥4；verify_rows ≥3；action_rows ≥{len(pr['core'])}（每隻主指數 ETF 一項）；group_summary ≥120；regime_rows／scenario_rows／scenario_detail 各 3 行、每格 ≥8 字。

=== JW 大盤分析指令 V1.0（原文針對美股；應用到{pr['name']}時，SPY／QQQ／IWM 換成上面嘅主指數 ETF，VIX 換成波動指數（冇就標缺），板塊換成上面嘅板塊／權重股）===
{_read('docs/jw-market-analysis-prompt.md')}

=== J Law 技術分析／交易方法筆記（MYT 文件整理）===
{_read('docs/jlaw-method-notes.md')}

=== gen/amarket/profiles.py ===
{_read('gen/amarket/profiles.py')}

=== gen/amarket/alib.py（work 檔可用嘅函數，`m` 係 Market）===
{_read('gen/amarket/alib.py')}

=== gen/amarket/report.py（報告版面）===
{_read('gen/amarket/report.py')}

=== gen/amarket/template_work.py（work 檔範本：所有 TODO／0 都要換成當日內容）===
{_read('gen/amarket/template_work.py')}
{ref}"""


class AsiaJob(agent.Job):
    def __init__(s, jid, date, mkt, folder, log):
        super().__init__(jid, date, folder, log)
        s.mkt = mkt; s.pr = PROFILES[mkt]

    def run(s):
        date, pr = s.date, s.pr
        s.log(f'檢查 Google Drive {pr["name"]}大盤截圖…')
        sh = jlaw.asia_shots(s.mkt, date)
        if not sh['folder']: raise RuntimeError(f'Drive 未有「{sh["name"]}」截圖資料夾（截圖未上載？Mac 要跑 capture_market_charts.py --market {s.mkt}）')
        if sh['missing']: raise RuntimeError(f'截圖未齊，缺 {len(sh["missing"])} 張：{"、".join(sh["missing"])}')
        imgs = [(t, sh['files'][t], jlaw.download(sh['files'][t]['id'])) for t in pr['shots']]
        s.log(f'已下載 {len(imgs)} 張截圖（{sh["name"]}）'); s.check_cancel()
        s.log('攞行情（/api/ohlcv＋Yahoo 指數）…')
        p = subprocess.run([sys.executable, os.path.join(ADIR, 'prep.py'), date], capture_output=True, text=True, timeout=600,
                           env={**os.environ, 'JLAW_SITE': jlaw.SITE, 'AMARKET': s.mkt})
        if p.returncode != 0: raise RuntimeError('行情準備失敗：' + (p.stderr or p.stdout)[-1500:])
        s.log('行情齊：' + p.stdout.strip().splitlines()[-1][:200])
        summary = data_summary(s.mkt, date)
        lbtxt = s.lb_verify_asia(date)
        s.check_cancel()
        try: pname, ptxt = jlaw.prev_asia_report(pr['title'], date)
        except Exception as e: pname, ptxt = None, ''; s.log(f'⚠ 讀唔到上一份報告：{e}')
        s.log(f'上一份{pr["title"]}：{pname or "無（第一份）"}')
        try: s.ref_name, s.ref_txt = jlaw.report_by_name(FORMAT_REF)
        except Exception as e: s.ref_name, s.ref_txt = None, ''; s.log(f'⚠ 讀唔到結構範本：{e}')
        hk = dt.datetime.now(ZoneInfo('Asia/Hong_Kong'))
        content = []
        for t, f, data in imgs:
            content.append({'type': 'text', 'text': f'截圖 {f["name"]}（Drive 建立時間 UTC {f.get("createdTime", "?")}）'})
            content.append(img_block(data))
        content.append({'type': 'text', 'text': f"""市場 = {pr['name']}（AMARKET={s.mkt}）；分析交易日 DATE = {date}；香港分析時間 {hk:%Y-%m-%d %H:%M}；模型識別碼 {{MODEL_ID}}。
行情已準備好（amarket/data/{s.mkt}），以下係重算數字摘要（work 檔用 m 取值，唔好照抄寫死）：
{json.dumps(summary, ensure_ascii=False)}

上一份{pr['title']}：{pname or '無'}
{ptxt[:30000] if ptxt else '（冇上一份，呢份係第一份：inherit_note 寫明冇承接）'}

Longbridge 核實（網站代做；結果寫入第二節資料來源）：
{lbtxt}

請：①逐張睇晒 {len(imgs)} 張圖抄讀數（收市、前收如睇到、圖面量）；②同上一份報告比較（冇就略過）；③用 web_search 核實過去 5 個交易日{pr['name']}市場催化劑、未來一星期日程，同廣度（升跌家數等）如搵到；④結構參照系統提示入面嘅美股範本；⑤寫完整 work 檔，用 build_report 提交，失敗就改好再提交。成功後檢查縮圖版面，冇問題就用一兩句總結今日市況分類收尾。"""})
        return s.analyze(system_prompt(pr, s.ref_name, s.ref_txt), content)

    def lb_verify_asia(s, date):
        if not s.pr.get('lb'): return f'今次冇 Longbridge 核實（Longbridge 直連只支援美股同港股，{s.pr["name"]}市場未驗證）。第二節照寫 Yahoo＋截圖。'
        if not lb.enabled(): s.log('⚠ 冇 Longbridge 金鑰'); return '今次冇 Longbridge 核實（網站未設定 Longbridge 金鑰）'
        ddir = os.path.join(ADIR, 'data', s.mkt)
        ok_list, bad, skip = [], [], []
        for t in json.load(open(os.path.join(ddir, '_meta.json')))['have']:
            try:
                b = lb.daily_bars(t, 5)
                if not b or date not in b: skip.append(t); continue
                r = json.load(open(os.path.join(ddir, f'{t}.json')))['rows'][-1]
                ok, txt = lb.compare(b[date], r)
                (ok_list if ok else bad).append(t if ok else f'{t}：{txt}')
            except lb.LBError as e: s.log(f'⚠ Longbridge 核實中斷：{e}'); skip.append(f'{t} 及之後（{e}）'); break
            except Exception as e: skip.append(f'{t}（{e}）')
        s.log(f'Longbridge 核實：一致 {len(ok_list)}、不一致 {len(bad)}、未比對 {len(skip)}')
        lines = []
        if ok_list: lines.append(f'收市同 Longbridge 一致（開高低收差 ≤0.02 或 ≤0.05%）：{"、".join(ok_list)}。')
        if bad: lines.append('⚠ 同 Longbridge 不一致（第二節並列兩邊數字）：' + '；'.join(bad))
        if skip: lines.append(f'未能比對：{"、".join(skip)}。')
        return '\n'.join(lines) or '今次冇 Longbridge 核實'

    def research_q(s):   # Gemini 上網核實步驟用
        n = s.pr['name']
        return (f'{n}股市大盤，分析交易日 {s.date}（收市後）。請用 Google 搜尋核實並逐項列出，每項附來源網站名稱同日期：'
                f'①{s.date} 同之前 4 個交易日（共 5 日）每日{n}股市主要消息／催化劑（本地經濟數據、央行、政策、重要業績、美股／中國影響），寫埋當日主要指數大約升跌；'
                f'②{s.date} 當日{n}股市升跌家數、新高新低、資金流（如港股通南向資金、外資買賣）；'
                f'③{s.date} 之後一星期{n}經濟數據、央行會議、重要公司業績日程（當地時間）。搵唔到嘅就寫「搵唔到」，唔好估。用繁體中文。')

    def inspect_prelude(s):
        return (GEN, f"import sys, os; os.environ['AMARKET'] = {s.mkt!r}; sys.path.insert(0, {ADIR!r}); os.chdir({GEN!r})\nfrom alib import *\nm = Market({s.date!r})")

    def build_cmd(s, wp):
        return ([sys.executable, os.path.join(ADIR, 'build.py'), s.mkt, s.date, wp, '--out', s.dir],
                {'MARKET_SUFFIX': {'grok': 'Grok核實版', 'gemini': 'Gemini核實版'}.get(s.engine, 'Claude核實版'),
                 'FORMAT_STRICT': os.environ.get('FORMAT_STRICT', '1'), 'AMARKET': s.mkt})
