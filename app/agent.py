"""agent.py — 一個大盤報告 job：攞截圖 → 行情 → Claude（睇圖、上網核實催化劑、寫 work 檔）→ build（QA 擋位）→ PDF。
同之前 Claude Code 排程 session 做嘅流程一樣（WORKER_MARKET.md），只係改由網站 call Claude API。"""
import base64, datetime as dt, io, json, os, re, subprocess, sys, time
from zoneinfo import ZoneInfo
import anthropic
from PIL import Image
import jlaw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, 'gen')
MODEL = os.environ.get('CLAUDE_MODEL', 'claude-opus-5-5')
EFFORT = os.environ.get('CLAUDE_EFFORT', 'high')
MAX_BUILDS = int(os.environ.get('MAX_BUILDS', '10'))
MAX_TURNS = 40
# 美元 / 百萬 token（Opus 5.5）：輸入、輸出、讀快取、寫快取
PRICE = dict(inp=4.0, out=20.0, cread=0.20, cwrite=5.0)


def _read(p): return open(os.path.join(ROOT, p), encoding='utf-8').read()


FORMAT_REF = os.environ.get('FORMAT_REF', '2026-10-30_美股大盤分析_JW框架_Claude核實版')


def system_prompt(ref_name='', ref_txt=''):
    ref = (f"""

=== 格式範本（硬性跟足）：{ref_name} ===
用戶要求每份報告嘅格式、章節、表格、每節篇幅同寫法都要同呢份一樣（數字當然用當日嘅）。逐節對照：
重點摘要兩段長 box（具體數字）＋六行表（每行分短線／中期／長期或列數字）；資料截止時間；核實動作；缺項逐項申報；數據分歧表；
三指數比較表＋均線表＋關鍵價位表；成交量／派發日／VIX／廣度；板塊表同五條問答；催化劑（過去 5 個交易日逐日一行）同未來一星期事件表；
歷史比較；短中長期判斷表＋三情境表＋情境細節表；下一交易日追蹤（≥5 項）、需要核實、條件式行動清單（≥3 項）、可直接轉貼摘要。
有 J Law 材料就要有「J Law 觀點對照及逐項核實」一節（jlaw_html），寫法照範本（材料清單、風險胃納變化、並列判斷、逐項表）。
build 有格式擋位（format_check）：任何一節少過範本水平都會失敗，要補返先過。
{ref_txt[:60000]}
""" if ref_txt else '')
    return f"""你係 JLaw 報告中心嘅大盤分析員，任務係出「每日美股大盤報告」PDF，做法同 Claude Code 排程 session 完全一樣，只係今次經 API 做：
你會收到當日 19 張 TradingView 截圖（圖像）、由行情重算嘅數字、上一份大盤報告文字。你要逐張睇圖、用 web_search 核實過去 5 日催化劑同未來一星期日程，然後寫一個完整嘅 work 檔（Python），用 build_report 工具提交。build 會跑 QA 擋位（≥20 項重算、PDF 文字回查、頁數上限）；失敗就睇錯誤訊息改好再提交，直至成功。

規則重點：
- 用廣東話（繁體）寫報告內容，語氣同之前報告一致。
- 數字一律用 f-string 由 m／S 取值；寫死嘅數字要喺 qa() 用 chk()／chk_true() 重算。
- 圖面讀數睇唔清就寫「無法辨識」或 None，唔好估。S['viewed'] 只列你真係睇過嘅截圖；S['meta']['ocr_used']=False。
- 催化劑／日程：核實唔到就標「未核實」，唔好補造；附來源同日期。
- S['meta']['ai'] 寫實際模型識別碼（下面會俾你），mode 寫「網站 API 自動生成（Claude API）」。
- 評分、市況判斷、關鍵價位要參考 J Law 方法筆記（均線、S&R、趨勢線／通道、見頂見底訊號）。
- work 檔只可以 import mlib（`from mlib import *`）同 Python 標準庫；唔好讀寫檔案、唔好上網、唔好 subprocess。
- 唔好出現「群組執行規則」相關句子。

=== WORKER_MARKET.md（流程，照做；入面講 drive.py／prep.py／build.py 嘅步驟網站已經代你做咗）===
{_read('docs/WORKER_MARKET.md')}

=== JW 大盤分析指令 V1.0 ===
{_read('docs/jw-market-analysis-prompt.md')}

=== J Law 技術分析／交易方法筆記（MYT 文件整理）===
{_read('docs/jlaw-method-notes.md')}

=== gen/market/mlib.py（work 檔可用嘅函數，`m` 係 Market）===
{_read('gen/market/mlib.py')}

=== gen/market/report.py（報告版面：每個欄位點樣出現喺 PDF）===
{_read('gen/market/report.py')}

=== gen/market/template_work.py（work 檔範本：所有 TODO／0 都要換成當日內容）===
{_read('gen/market/template_work.py')}
{ref}"""


BUILD_TOOL = {
    'name': 'build_report',
    'description': '提交完整 work 檔（Python 源碼，要有 BASIS、spec(m)、texts(m, S)、qa(m, S, T)），網站會寫入檔案並跑 build（大盤 market/build.py；個股 build.py）。'
                   '回傳 build 結果：成功就有頁數、QA 數同每頁縮圖；失敗就有錯誤訊息（照住改，再提交完整 work 檔）。',
    'input_schema': {'type': 'object', 'properties': {'work_py': {'type': 'string', 'description': '完整 work 檔源碼'}},
                     'required': ['work_py'], 'additionalProperties': False},
    'eager_input_streaming': True,
}
INSPECT_TOOL = {
    'name': 'inspect_data',
    'description': '睇資料用（唔計 build 次數）：喺同 build 一樣嘅環境跑一段短 Python，`m` 已經準備好（大盤＝mlib.Market(DATE)；個股＝lib.metrics(TICKER)），'
                   'print() 嘅結果會回傳（最多 6000 字）。用嚟查行情原始數據、計某個數、試函數點用。唔好用 build_report 嚟 probe／dump 資料。',
    'input_schema': {'type': 'object', 'properties': {'code': {'type': 'string', 'description': 'Python 源碼，用 print() 輸出'}},
                     'required': ['code'], 'additionalProperties': False},
    'eager_input_streaming': True,
}
WEB_SEARCH = {'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 12}


def img_block(data):
    im = Image.open(io.BytesIO(data)).convert('RGB')
    im.thumbnail((2000, 2000))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=88)
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(b.getvalue()).decode()}}


def data_summary(date):
    sys.path.insert(0, os.path.join(GEN, 'market'))
    import importlib, mlib; importlib.reload(mlib)
    m = mlib.Market(date)
    out = {'date': m.date, 'prev_date': m.pdate, 'missing_yahoo': m.missing, 'tickers': {}}
    for t, s in m.sym.items():
        st, mi = s.dist_days()
        out['tickers'][t] = dict(o=s.o, h=s.h, l=s.l, c=s.c, pc=s.pc, chgp=round(s.chgp, 4), v=s.v, v50=round(s.v50()), vr=round(s.vr(), 2),
                                 ma={k: round(s.ma(k), 4) for k in (10, 20, 50, 200)}, h52=s.h52, l52=s.l52, ret5=round(s.ret5, 4), ret20=round(s.ret20, 4),
                                 candle={k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.candle().items()}, dist_strict=st, dist_micro=mi)
    return out


class ClaudeRefused(Exception): pass


def with_model(content, model):
    return [dict(b, text=b['text'].replace('{MODEL_ID}', model)) if b['type'] == 'text' else b for b in content]


class Job:
    def __init__(s, jid, date, folder, log):
        s.id, s.date, s.dir, s.log = jid, date, folder, log
        s.usage = dict(inp=0, out=0, cread=0, cwrite=0); s.pdf = None; s.builds = 0; s.pages = None; s.engine = None; s.extra_cost = 0.0; s.jlaw_required = False; s.ref_name = None; s.ref_txt = ''; s.pdfs = []

    def cost(s): return round(sum(s.usage[k] * PRICE[k] for k in PRICE) / 1e6 + s.extra_cost, 2)

    def run(s):
        date = s.date
        # 1. 截圖
        s.log('檢查 Google Drive 大盤截圖…')
        sh = jlaw.market_shots(date)
        if not sh['folder']: raise RuntimeError(f'Drive 未有「{sh["name"]}」截圖資料夾（截圖未上載？）')
        if sh['missing']: raise RuntimeError(f'截圖未齊，缺 {len(sh["missing"])} 張：{"、".join(sh["missing"])}')
        imgs = []
        for t in jlaw.MSHOTS:
            f = sh['files'][t]
            imgs.append((t, f, jlaw.download(f['id'])))
        s.log(f'已下載 19 張截圖（{sh["name"]}）')
        # 2. 行情
        s.log('攞行情（jlaw-report /api/ohlcv）…')
        p = subprocess.run([sys.executable, os.path.join(GEN, 'market', 'prep.py'), date], capture_output=True, text=True, timeout=600,
                           env={**os.environ, 'JLAW_SITE': jlaw.SITE})
        if p.returncode != 0: raise RuntimeError('行情準備失敗：' + (p.stderr or p.stdout)[-1500:])
        summary = data_summary(date)
        s.log('行情齊：' + p.stdout.strip().splitlines()[-1][:200])
        # 3. 上一份報告
        try:
            pname, ptxt = jlaw.prev_market_report(date)
        except Exception as e:
            pname, ptxt = None, ''; s.log(f'⚠ 讀唔到上一份報告：{e}')
        s.log(f'上一份大盤報告：{pname or "無"}')
        try:
            s.ref_name, s.ref_txt = jlaw.report_by_name(FORMAT_REF)
        except Exception as e:
            s.ref_name, s.ref_txt = None, ''; s.log(f'⚠ 讀唔到格式範本：{e}')
        s.log(f'格式範本：{s.ref_name or "⚠ 搵唔到 " + FORMAT_REF}')
        try:
            jl = jlaw.jlaw_materials(date)
        except Exception as e:
            jl = []; s.log(f'⚠ 讀唔到 J Law 觀點材料：{e}')
        if jl is None: s.log('⚠ 未設定 JLAW_ADMIN_PASSWORD：讀唔到 J Law 觀點材料，報告冇 J Law 對照一節'); jl = []
        else: s.log(f'J Law 觀點材料：{"、".join(n for n, _ in jl) or "分析日前 10 日內冇"}')
        s.jlaw_required = bool(jl)
        jtxt = ''.join(f'\n--- {n} ---\n{t[:25000]}' for n, t in jl)
        # 4. Claude
        hk = dt.datetime.now(ZoneInfo('Asia/Hong_Kong'))
        content = []
        for t, f, data in imgs:
            content.append({'type': 'text', 'text': f'截圖 {f["name"]}（Drive 建立時間 UTC {f.get("createdTime", "?")}）'})
            content.append(img_block(data))
        content.append({'type': 'text', 'text': f"""分析交易日 DATE = {date}；香港分析時間 {hk:%Y-%m-%d %H:%M}；模型識別碼 {{MODEL_ID}}。
行情已準備好（market/data），以下係重算數字摘要（work 檔用 m 取值，唔好照抄寫死）：
{json.dumps(summary, ensure_ascii=False)}

上一份大盤報告：{pname or '無'}
{ptxt[:40000] if ptxt else '（冇上一份，第一份）'}

J Law 觀點材料（私人，只可用嚟寫 jlaw_html 一節；檔名日期＝發布日期，只用 ≤ 分析交易日嘅）：{jtxt or '（冇）'}

請：①逐張睇晒 19 張圖抄讀數；②同上一份報告比較（包括廣度線係咪停滯）；③用 web_search 核實過去 5 個交易日催化劑同未來一星期美國經濟數據／重要業績日程；④格式要硬性跟足系統提示入面嘅格式範本（每節篇幅同範本一樣詳細）；有 J Law 材料就寫 jlaw_html；⑤寫完整 work 檔，用 build_report 提交，失敗就改好再提交。成功後檢查縮圖版面，冇問題就用一兩句總結今日市況分類收尾。"""})
        return s.analyze(system_prompt(s.ref_name, s.ref_txt), content)

    def analyze(s, system, content):
        if os.environ.get('ANTHROPIC_API_KEY'):
            try:
                return s.run_claude(system, content)
            except (anthropic.APIError, ClaudeRefused) as e:
                if s.pdf:   # 已經有一版過咗 QA 嘅 PDF，用住佢，唔使重做
                    s.log(f'⚠ Claude 最後一步出錯（{type(e).__name__}），用已經過 QA 嘅 PDF'); return
                if not os.environ.get('XAI_API_KEY'): raise RuntimeError(f'Claude API 出錯：{e}')
                s.builds = 0
                s.log(f'⚠ Claude 用唔到（{type(e).__name__}：{str(e)[:200]}），改用 Grok 由頭再做')
        elif not os.environ.get('XAI_API_KEY'):
            raise RuntimeError('未設定 ANTHROPIC_API_KEY 或 XAI_API_KEY')
        else:
            s.log('⚠ 未設定 ANTHROPIC_API_KEY，直接用 Grok')
        import grok
        s.engine = 'grok'
        return grok.run(s, system, content)

    def run_claude(s, system, content):
        s.engine = 'claude'
        msgs = [{'role': 'user', 'content': with_model(content, MODEL)}]
        client = anthropic.Anthropic(); idle = 0
        for turn in range(MAX_TURNS):
            resp = s.call(client, system, msgs)
            msgs.append({'role': 'assistant', 'content': resp.content})
            if resp.stop_reason == 'refusal':
                raise ClaudeRefused(str(getattr(resp, 'stop_details', None)))
            if resp.stop_reason == 'pause_turn': continue
            uses = [b for b in resp.content if b.type == 'tool_use']
            if resp.stop_reason == 'tool_use' and uses:
                results = [s.tool(b) for b in uses]
                msgs.append({'role': 'user', 'content': results})
                if s.builds >= MAX_BUILDS and not s.pdf: raise RuntimeError(f'build 試咗 {s.builds} 次都未過 QA，停止')
                continue
            if resp.stop_reason == 'max_tokens':
                msgs.append({'role': 'user', 'content': '回覆被截斷。請重新用 build_report 提交完整 work 檔（精簡敘述）。'}); continue
            if s.pdf:
                txt = ''.join(b.text for b in resp.content if b.type == 'text').strip()
                s.log('完成：' + txt[:400]); return
            idle += 1
            if idle >= 3: raise RuntimeError('Claude 連續 3 次冇提交 work 檔，停止')
            msgs.append({'role': 'user', 'content': '未有成功嘅 PDF。請用 build_report 提交完整 work 檔。'})
        raise RuntimeError('對話輪數用晒都未出到 PDF')

    def call(s, client, system, msgs):
        s.log('Claude 分析中…')
        kw = dict(model=MODEL, max_tokens=64000, system=system, messages=msgs, tools=[WEB_SEARCH, BUILD_TOOL, INSPECT_TOOL],
                  thinking={'type': 'adaptive'}, output_config={'effort': EFFORT}, cache_control={'type': 'ephemeral'},
                  betas=['server-side-fallback-2026-07-01'], fallbacks='default')
        for attempt in range(4):
            try:
                with client.beta.messages.stream(**kw) as st:
                    resp = st.get_final_message()
                break
            except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
                if attempt == 3: raise
                s.log(f'⚠ Claude API 暫時出錯（{type(e).__name__}），{20 * (attempt + 1)} 秒後重試'); time.sleep(20 * (attempt + 1))
        u = resp.usage
        s.usage['inp'] += u.input_tokens or 0; s.usage['out'] += u.output_tokens or 0
        s.usage['cread'] += getattr(u, 'cache_read_input_tokens', 0) or 0; s.usage['cwrite'] += getattr(u, 'cache_creation_input_tokens', 0) or 0
        n_search = sum(1 for b in resp.content if b.type == 'server_tool_use')
        s.log(f'Claude 回覆（{resp.stop_reason}；累計約 US${s.cost()}' + (f'；上網搜尋 {n_search} 次' if n_search else '') + '）')
        return resp

    def tool(s, b):
        if b.name == 'inspect_data': return s.inspect(b)
        if b.name != 'build_report' or not isinstance(b.input, dict) or not isinstance(b.input.get('work_py'), str) or 'def spec' not in b.input['work_py']:
            return {'type': 'tool_result', 'tool_use_id': b.id, 'is_error': True, 'content': 'INVALID_INPUT：要用 build_report，work_py 係完整 Python 源碼（有 spec／texts／qa）'}
        s.builds += 1
        wp = os.path.join(s.dir, f'work_{s.builds}.py'); open(wp, 'w', encoding='utf-8').write(b.input['work_py'])
        s.log(f'第 {s.builds} 次 build…')
        try:
            cmd, env = s.build_cmd(wp)
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=GEN, env={**os.environ, **env})
        except subprocess.TimeoutExpired:
            return {'type': 'tool_result', 'tool_use_id': b.id, 'is_error': True, 'content': 'build 超時（>10 分鐘）'}
        out = (p.stdout + '\n' + p.stderr).strip()
        if p.returncode != 0:
            s.log(f'build 未過：{out.splitlines()[-1][:200] if out else "?"}')
            return {'type': 'tool_result', 'tool_use_id': b.id, 'is_error': True, 'content': 'build 失敗：\n' + out[-6000:]}
        info = json.loads([l for l in p.stdout.splitlines() if l.startswith('{')][-1])
        s.on_success(info)
        res = [{'type': 'text', 'text': 'build 成功：' + json.dumps(info, ensure_ascii=False) + '\n以下係每頁縮圖，檢查版面（溢出、空白、表格斷開）。冇問題就收尾；要改就再提交完整 work 檔。'}]
        for pdf in s.pdfs:
            pre = os.path.join(s.dir, 'pg')
            subprocess.run(['pdftoppm', '-r', '45', '-png', pdf, pre], capture_output=True)
            for f in sorted(x for x in os.listdir(s.dir) if x.startswith('pg') and x.endswith('.png')):
                res.append(img_block(open(os.path.join(s.dir, f), 'rb').read())); os.remove(os.path.join(s.dir, f))
        return {'type': 'tool_result', 'tool_use_id': b.id, 'content': res}

    def inspect(s, b):
        code = b.input.get('code') if isinstance(b.input, dict) else None
        if not isinstance(code, str) or not code.strip():
            return {'type': 'tool_result', 'tool_use_id': b.id, 'is_error': True, 'content': 'INVALID_INPUT：inspect_data 要有 code（Python 源碼）'}
        s.inspects = getattr(s, 'inspects', 0) + 1
        if s.inspects > 25: return {'type': 'tool_result', 'tool_use_id': b.id, 'is_error': True, 'content': 'inspect_data 用咗 25 次，夠資料就交 build_report'}
        cwd, pre = s.inspect_prelude()
        fp = os.path.join(s.dir, f'inspect_{s.inspects}.py'); open(fp, 'w', encoding='utf-8').write(pre + '\n' + code)
        s.log(f'睇資料（第 {s.inspects} 次）')
        try:
            p = subprocess.run([sys.executable, fp], capture_output=True, text=True, timeout=120, cwd=cwd, env={**os.environ, 'JL_DATE': s.date})
            out = (p.stdout + ('\n[stderr]\n' + p.stderr if p.stderr.strip() else '')).strip() or '（冇輸出，記得 print）'
        except subprocess.TimeoutExpired: out = '超時（>120 秒）'
        return {'type': 'tool_result', 'tool_use_id': b.id, 'content': out[-6000:]}

    def inspect_prelude(s):
        return (GEN, f"import sys, os; sys.path.insert(0, {os.path.join(GEN, 'market')!r}); os.chdir({GEN!r})\nfrom mlib import *\nm = Market({s.date!r})")

    # ---- 大盤報告專用（StockJob 覆寫）
    def build_cmd(s, wp):
        return ([sys.executable, os.path.join(GEN, 'market', 'build.py'), s.date, wp, '--out', s.dir],
                {'MARKET_SUFFIX': 'Grok核實版' if s.engine == 'grok' else 'Claude核實版',
                 'FORMAT_STRICT': os.environ.get('FORMAT_STRICT', '1'), 'JLAW_REQUIRED': '1' if s.jlaw_required else '0'})

    def on_success(s, info):
        s.pdf, s.pages = info['pdf'], info['pages']; s.pdfs = [s.pdf]
        s.log(f'build 成功：{info["pages"]} 頁，QA {info["qa_work"]} 項＋PDF 回查 {info["qa_pdf"]} 項')
