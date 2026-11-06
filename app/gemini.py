"""gemini.py — 用 Google Gemini 出報告（網頁揀「Gemini」先會用；唔會自動取代 Claude／Grok）。用戶 2026-11-06 要求加入做比較。
兩步：
1. 上網核實：Gemini 原生 API（generateContent＋google_search grounding，header x-goog-api-key）查催化劑／日程（個股：財報日、新聞、評級），
   結果連來源網址寫成一段筆記。（原生「搜尋＋自訂函數同一請求」仲係預覽功能，所以分開做。）
2. 主分析：OpenAI 相容接口（/v1beta/openai/chat/completions，Bearer＝同一個 API key，串流）睇截圖、call build_report／inspect_data，
   失敗就改好再交，流程同 Grok 一樣。Gemini 3+ 每個 tool call 帶 thought_signature（extra_content），一定要原封不動送返，所以對話紀錄只加唔改
   （亦令 Gemini 自動快取重送嘅前段）。
環境變數：GEMINI_API_KEY（必須）、GEMINI_MODEL（默認 gemini-4-argon）、GEMINI_SEARCH_MODEL（上網核實用，默認同 GEMINI_MODEL）、
GEMINI_REASONING（選填 low／medium／high）、GEMINI_PRICE_IN／OUT／CACHED（美元／百萬 token，只用嚟估用量，默認 2／10／0.2；
以 Google AI Studio 帳單為準；上網核實（grounding）每次請求另計，未包）。"""
import json, os, time, types, urllib.error, urllib.request

BASE = 'https://generativelanguage.googleapis.com/v1beta'
MODEL = os.environ.get('GEMINI_MODEL', 'gemini-4-argon')
SEARCH_MODEL = os.environ.get('GEMINI_SEARCH_MODEL', MODEL)
PRICE_IN = float(os.environ.get('GEMINI_PRICE_IN', '2'))
PRICE_OUT = float(os.environ.get('GEMINI_PRICE_OUT', '10'))
PRICE_CACHED = float(os.environ.get('GEMINI_PRICE_CACHED', '0.2'))
IDLE = int(os.environ.get('GEMINI_IDLE_TIMEOUT', '300'))
MAX_TURNS = 40
NOTE = ('（今次由 Google Gemini 做。上網核實已經由網站先做好，結果喺上面「上網核實（Google 搜尋）」一段，每項有來源網址；'
        '用嗰段寫催化劑／日程，冇講到嘅標「未核實」，唔好補造。S["meta"]["ai"] 寫上面嘅模型識別碼，ai_note 註明「由 Google Gemini 生成」。'
        '注意篇幅：過往 Gemini 第一次交成日超出上限（本體 11–12 頁、今日動作 >40 字、朗讀稿超字數），每超一次都要重做收費。'
        'work 檔 texts 正文合共大約 2.5–3 萬字就夠（ESTC 範本篇幅），本體報告一定 ≤10 頁；今日動作 ≤40 字；script3 ≤950、scriptfull ≤3,500 字；'
        '提交前自己用 len() 數一次。）')

TOOLS = [{'type': 'function', 'function': {
            'name': 'inspect_data',
            'description': '睇資料用（唔計 build 次數，但每份報告最多 5 次，要一次過 print 晒需要嘅數）：跑一段短 Python，m 已經準備好（大盤＝mlib.Market(DATE)；個股＝lib.metrics(TICKER)），回傳 print() 結果。唔好用 build_report 嚟 probe 資料。',
            'parameters': {'type': 'object', 'properties': {'code': {'type': 'string', 'description': 'Python 源碼，用 print() 輸出'}}, 'required': ['code']}}},
         {'type': 'function', 'function': {
            'name': 'build_report',
            'description': '提交完整 work 檔（Python 源碼，要有 BASIS、spec(m)、texts(m, S)、qa(m, S, T)），網站會跑 build（QA＋格式擋位）並回傳結果。失敗就照錯誤逐項改好，再提交完整 work 檔。',
            'parameters': {'type': 'object', 'properties': {'work_py': {'type': 'string', 'description': '完整 work 檔源碼'}}, 'required': ['work_py']}}}]


def enabled(): return bool(os.environ.get('GEMINI_API_KEY'))


def _req(url, body, headers, timeout):
    return urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(), method='POST',
                                  headers={'Content-Type': 'application/json', **headers})


def _retry(fn, log, what):
    for attempt in range(4):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:800]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                log(f'⚠ Gemini {what} {e.code}，{20 * (attempt + 1)} 秒後重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'Gemini {what} {e.code}：{msg}')
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 3: log(f'⚠ Gemini {what} 連線問題（{e}），重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'連唔到 Gemini：{e}')


# ---------- 1. 上網核實（原生 API＋google_search） ----------
def search(question, log=print, model=None):
    """回傳 (筆記文字, 來源數, usage)。失敗 raise RuntimeError。"""
    url = f'{BASE}/models/{model or SEARCH_MODEL}:generateContent'
    body = {'contents': [{'role': 'user', 'parts': [{'text': question}]}], 'tools': [{'google_search': {}}]}

    def go():
        with urllib.request.urlopen(_req(url, body, {'x-goog-api-key': os.environ['GEMINI_API_KEY']}, 300), timeout=300) as r:
            return json.load(r)
    d = _retry(go, log, '上網核實')
    c = (d.get('candidates') or [{}])[0]
    text = ''.join(p.get('text', '') for p in (c.get('content') or {}).get('parts') or [] if not p.get('thought'))
    chunks = (c.get('groundingMetadata') or {}).get('groundingChunks') or []
    src = [f"[{i + 1}] {(ch.get('web') or {}).get('title', '')} {(ch.get('web') or {}).get('uri', '')}" for i, ch in enumerate(chunks)]
    if src: text += '\n\n來源（Google 搜尋 grounding）：\n' + '\n'.join(src)
    return text.strip(), len(chunks), d.get('usageMetadata') or {}


def research_question(job):
    t = getattr(job, 'ticker', None)
    if t:
        return (f'股票代號 {t}，分析交易日 {job.date}（收市後）。請用 Google 搜尋核實並逐項列出，每項附來源網站名稱同日期：'
                f'①下次業績公布日期（盤前／盤後）；②{job.date} 之前 5 個交易日嘅重要新聞／催化劑（公司公告、評級變動、行業消息）；'
                f'③最新分析員評級同目標價（列機構、日期）。搵唔到嘅就寫「搵唔到」，唔好估。用繁體中文。')
    return (f'美股大盤，分析交易日 {job.date}（收市後）。請用 Google 搜尋核實並逐項列出，每項附來源網站名稱同日期：'
            f'①{job.date} 同之前 4 個交易日（共 5 日）每日美股主要市場消息／催化劑（經濟數據、聯儲局、重要業績、地緣政治），寫埋當日 SPY／QQQ 大約升跌；'
            f'②{job.date} 之後一星期美國經濟數據公布時間（美東時間）、聯儲局官員講話、重要公司業績日程。'
            '搵唔到嘅就寫「搵唔到」，唔好估。用繁體中文。')


# ---------- 2. 主分析（OpenAI 相容接口，串流） ----------
def _part(b):
    if b['type'] == 'text': return {'type': 'text', 'text': b['text']}
    src = b['source']
    return {'type': 'image_url', 'image_url': {'url': f'data:{src["media_type"]};base64,{src["data"]}'}}


def _stream(body, log):
    def go():
        msg = {'role': 'assistant', 'content': '', 'tool_calls': {}}; usage = {}; finish = None
        arg_chars, last_note = 0, time.time()
        req = _req(f'{BASE}/openai/chat/completions', dict(body, stream=True, stream_options={'include_usage': True}),
                   {'Authorization': f'Bearer {os.environ["GEMINI_API_KEY"]}', 'Accept': 'text/event-stream'}, IDLE)
        with urllib.request.urlopen(req, timeout=IDLE) as r:
            for raw in r:
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'): continue
                data = line[5:].strip()
                if data == '[DONE]': break
                try: ev = json.loads(data)
                except json.JSONDecodeError: continue
                if ev.get('error'): raise RuntimeError(f'Gemini 串流出錯：{json.dumps(ev["error"], ensure_ascii=False)[:500]}')
                usage = ev.get('usage') or usage
                for ch in ev.get('choices') or []:
                    finish = ch.get('finish_reason') or finish
                    dl = ch.get('delta') or {}
                    if dl.get('content'): msg['content'] += dl['content']
                    for tc in dl.get('tool_calls') or []:
                        k = tc.get('index', len(msg['tool_calls']))
                        cur = msg['tool_calls'].setdefault(k, {'id': None, 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                        if not cur['function']['name']: log('Gemini 開始寫 work 檔…' if (tc.get('function') or {}).get('name') == 'build_report' else 'Gemini 睇資料…')
                        if tc.get('id'): cur['id'] = tc['id']
                        if tc.get('extra_content'): cur['extra_content'] = tc['extra_content']   # thought_signature，要原封不動送返
                        f = tc.get('function') or {}
                        if f.get('name'): cur['function']['name'] += f['name']
                        if f.get('arguments'):
                            cur['function']['arguments'] += f['arguments']; arg_chars += len(f['arguments'])
                            if time.time() - last_note > 60: log(f'Gemini 寫緊 work 檔（{arg_chars:,} 字）…'); last_note = time.time()
        msg['tool_calls'] = [v for _, v in sorted(msg['tool_calls'].items())]
        if not msg['tool_calls']: del msg['tool_calls']
        if not msg['content'] and 'tool_calls' not in msg and finish is None: raise ConnectionError('Gemini 串流中斷，冇收到完整回覆')
        return msg, usage, finish
    return _retry(go, log, 'API')


def run(job, system, content):
    from agent import with_model
    if not enabled(): raise RuntimeError('未設定 GEMINI_API_KEY')
    job.log(f'Gemini 上網核實中（Google 搜尋，{SEARCH_MODEL}）…')
    try:
        rtxt, nsrc, _ = search(research_question(job), job.log)
        job.log(f'Gemini 上網核實完成：{nsrc} 個來源')
    except Exception as e:
        rtxt = f'（上網核實失敗：{str(e)[:300]}。今次冇網上核實，催化劑／日程標「未核實」。）'; job.log('⚠ ' + rtxt[:200])
    parts = [_part(b) for b in with_model(content, MODEL)]
    parts += [{'type': 'text', 'text': '上網核實（Google 搜尋，網站代做）：\n' + rtxt}, {'type': 'text', 'text': NOTE}]
    msgs = [{'role': 'system', 'content': system}, {'role': 'user', 'content': parts}]
    tin = tout = tcache = idle = 0
    for turn in range(MAX_TURNS):
        job.check_cancel()
        job.log('Gemini 分析中…')
        body = {'model': MODEL, 'messages': msgs, 'tools': TOOLS, 'max_tokens': 60000}
        if os.environ.get('GEMINI_REASONING'): body['reasoning_effort'] = os.environ['GEMINI_REASONING']
        msg, u, finish = _stream(body, job.log)
        p_in = u.get('prompt_tokens', 0) or 0
        cached = (u.get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0
        out = max((u.get('total_tokens', 0) or 0) - p_in, u.get('completion_tokens', 0) or 0)   # 思考 token 唔喺 completion_tokens，但係照收費
        tin += p_in - cached; tcache += cached; tout += out
        job.extra_cost = (tin * PRICE_IN + tcache * PRICE_CACHED + tout * PRICE_OUT) / 1e6
        calls = msg.get('tool_calls') or []
        job.log(f'Gemini 回覆（{finish}{"；工具 " + str(len(calls)) if calls else ""}；今輪輸入 {p_in:,} token'
                f'{"（快取 " + format(cached, ",") + "）" if cached else ""}；累計約 US${job.cost()}）')
        msgs.append(msg)   # 原封不動（包括 thought_signature）
        if finish == 'length' and calls:
            msgs.pop(); msgs.append({'role': 'user', 'content': '回覆被截斷。請重新用 build_report 提交完整 work 檔（精簡少少敘述）。'}); continue
        if calls:
            imgs = []
            for c in calls:
                try: args = json.loads(c['function'].get('arguments') or '{}')
                except json.JSONDecodeError: args = None
                res = job.tool(types.SimpleNamespace(name=c['function']['name'], id=c['id'], input=args))
                cont = res['content']
                if isinstance(cont, list):
                    text = '\n'.join(x['text'] for x in cont if x['type'] == 'text')
                    imgs += [_part(x) for x in cont if x['type'] == 'image']
                else: text = cont
                msgs.append({'role': 'tool', 'tool_call_id': c['id'], 'content': text})
            if imgs: msgs.append({'role': 'user', 'content': [{'type': 'text', 'text': 'build 成功後嘅每頁縮圖（對照格式範本檢查版面）：'}] + imgs})
            if job.builds >= int(os.environ.get('MAX_BUILDS', '10')) and not job.pdf: raise RuntimeError(f'build 試咗 {job.builds} 次都未過 QA／格式擋位，停止')
            continue
        if job.pdf:
            job.log('完成（Gemini）：' + (msg.get('content') or '')[:400]); return
        idle += 1
        if idle >= 3: raise RuntimeError('Gemini 連續 3 次冇提交 work 檔，停止')
        msgs.append({'role': 'user', 'content': '未有成功嘅 PDF。請用 build_report 工具提交完整 work 檔。'})
    raise RuntimeError('Gemini 對話輪數用晒都未出到 PDF')


def selftest(log=print):
    """伺服器啟動時：試一次上網核實（原生 API＋google_search），確認 key 同型號用得。"""
    if not enabled(): return
    try:
        txt, n, u = search('用一句繁體中文答：NVIDIA 下一次公布業績係幾時？', log)
        log(f'gemini OK（{SEARCH_MODEL}；Google 搜尋 {n} 個來源）：{txt.splitlines()[0][:120] if txt else ""}')
    except Exception as e:
        log(f'gemini 連唔到：{str(e)[:300]}')
