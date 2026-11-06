"""grok.py — 用 xAI Grok 做大盤報告（Claude 用唔到或者冇 ANTHROPIC_API_KEY 時）。
用 xAI Responses API（https://api.x.ai/v1/responses）：伺服器端 web_search（上網核實催化劑／日程）＋自訂 function build_report。
流程同 Claude 版一樣：睇 19 張圖 → 上網核實 → 寫 work 檔 → build_report 跑 QA＋格式擋位 → 失敗改好再交。
環境變數：XAI_API_KEY（必須）、XAI_MODEL（默認 grok-4.7）、XAI_BASE（默認 https://api.x.ai/v1）、XAI_REASONING（選填：low／medium／high）、
XAI_PRICE_IN／XAI_PRICE_OUT（美元／百萬 token，默認 grok-4.7 嘅 2／6，只用嚟估用量；上網搜尋另計，未包）。"""
import json, os, time, types, urllib.error, urllib.request

BASE = os.environ.get('XAI_BASE', 'https://api.x.ai/v1').rstrip('/')
MODEL = os.environ.get('XAI_MODEL', 'grok-4.7')
PRICE_IN = float(os.environ.get('XAI_PRICE_IN', '2'))
PRICE_OUT = float(os.environ.get('XAI_PRICE_OUT', '6'))
MAX_TURNS = 40
NOTE = ('（今次由 xAI Grok 做。你有 web_search 工具：一定要用嚟核實過去 5 個交易日每日嘅市場消息／催化劑，同未來一星期美國經濟數據、聯儲局、'
        '重要業績日程，每項附來源網站同日期；搵唔到先標「未核實」，唔好補造。S["meta"]["ai"] 寫上面嘅模型識別碼，ai_note 註明「由 xAI Grok 生成」。）')

TOOLS = [{'type': 'web_search'},
         {'type': 'function', 'name': 'inspect_data',
          'description': '睇資料用（唔計 build 次數，但每份報告最多 3 次，要一次過 print 晒需要嘅數）：跑一段短 Python，m 已經準備好（大盤＝mlib.Market(DATE)；個股＝lib.metrics(TICKER)），回傳 print() 結果。唔好用 build_report 嚟 probe 資料。',
          'parameters': {'type': 'object', 'properties': {'code': {'type': 'string', 'description': 'Python 源碼，用 print() 輸出'}}, 'required': ['code']}},
         {'type': 'function', 'name': 'build_report',
          'description': '提交完整 work 檔（Python 源碼，要有 BASIS、spec(m)、texts(m, S)、qa(m, S, T)），網站會跑 build（QA＋格式擋位）並回傳結果。失敗就照錯誤逐項改好，再提交完整 work 檔。',
          'parameters': {'type': 'object', 'properties': {'work_py': {'type': 'string', 'description': '完整 work 檔源碼'}}, 'required': ['work_py']}}]


def _part(b):
    """Anthropic 格式 content block → Responses API input 格式"""
    if b['type'] == 'text': return {'type': 'input_text', 'text': b['text']}
    src = b['source']
    return {'type': 'input_image', 'image_url': f'data:{src["media_type"]};base64,{src["data"]}', 'detail': 'high'}


IDLE = int(os.environ.get('XAI_IDLE_TIMEOUT', '300'))   # 串流超過呢個秒數冇任何資料就當斷線重試


def _stream(req, log, cancel=lambda: None):
    """讀 Responses API 串流（SSE），回傳最後嘅 response 物件；途中記低進度（上網搜尋、寫 work 檔）"""
    final = None; arg_chars = 0; last_note = time.time()
    with urllib.request.urlopen(req, timeout=IDLE) as r:
        for raw in r:
            cancel()   # 撳咗停止就喺串流途中即刻停
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'): continue
            data = line[5:].strip()
            if data == '[DONE]': break
            try: ev = json.loads(data)
            except json.JSONDecodeError: continue
            t = ev.get('type', '')
            if t in ('response.completed', 'response.incomplete', 'response.failed'): final = ev.get('response'); continue
            if t == 'error': raise RuntimeError(f'Grok 串流出錯：{json.dumps(ev, ensure_ascii=False)[:500]}')
            if t == 'response.output_item.added':
                it = (ev.get('item') or {}).get('type')
                if it == 'web_search_call': log('Grok 上網搜尋中…')
                elif it == 'function_call': log('Grok 開始寫 work 檔…')
            elif t == 'response.function_call_arguments.delta':
                arg_chars += len(ev.get('delta') or '')
                if time.time() - last_note > 60: log(f'Grok 寫緊 work 檔（{arg_chars:,} 字）…'); last_note = time.time()
    if not final: raise RuntimeError('Grok 串流中斷，冇收到完整回覆')
    if final.get('status') == 'failed': raise RuntimeError(f'Grok 回覆失敗：{json.dumps(final.get("error"), ensure_ascii=False)[:500]}')
    return final


def _post(body, log, cancel=lambda: None):
    key = os.environ['XAI_API_KEY']
    data = json.dumps(dict(body, stream=True), ensure_ascii=False).encode()
    for attempt in range(4):
        req = urllib.request.Request(BASE + '/responses', data=data, method='POST',
                                     headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
        try:
            return _stream(req, log, cancel)
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:800]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                log(f'⚠ Grok API {e.code}，{20 * (attempt + 1)} 秒後重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'Grok API {e.code}：{msg}')
        except (urllib.error.URLError, TimeoutError, ConnectionError, RuntimeError) as e:
            if isinstance(e, RuntimeError) and '中斷' not in str(e): raise
            if attempt < 3: log(f'⚠ Grok 連線問題（{e}），重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'連唔到 Grok：{e}')


def _text(item):
    return ''.join(c.get('text', '') for c in item.get('content') or [] if c.get('type') in ('output_text', 'text'))


OLD_WORK = json.dumps({'work_py': '（舊版 work 檔已省略，以最新一版為準）'}, ensure_ascii=False)
IMG_NOTE = ('（截圖已經喺第一次提交 work 檔之前睇過；為咗慳用量，之後唔再重送圖片。修改時以你 work 檔入面已抄低嘅讀數為準，'
            '唔好改動圖面讀數，除非錯誤訊息直接指出。）')


def _compact(inp):
    """store:false 每輪重送成段對話：第一次提交 work 檔之後，截圖、舊版 work 檔、舊 build 結果、舊縮圖都唔再重送（只留最新一版），
    慳 input token；最新一版 work 檔同佢嘅 build 結果完整保留，AI 照樣改得。"""
    builds = [x for x in inp if x.get('type') == 'function_call' and x.get('name') == 'build_report']
    if not builds: return
    last = builds[-1]['call_id']
    u = inp[1]
    if isinstance(u.get('content'), list) and any(p.get('type') == 'input_image' for p in u['content']):
        u['content'] = [p for p in u['content'] if p.get('type') != 'input_image'] + [{'type': 'input_text', 'text': IMG_NOTE}]
    old = {x['call_id'] for x in builds if x['call_id'] != last}
    for x in inp:
        if x.get('type') == 'function_call' and x.get('call_id') in old: x['arguments'] = OLD_WORK
        elif x.get('type') == 'function_call_output' and x.get('call_id') in old and len(x.get('output', '')) > 600:
            x['output'] = x['output'][:600] + '…（舊版 build 結果已截短）'
    thumbs = [i for i, x in enumerate(inp) if x.get('role') == 'user' and isinstance(x.get('content'), list)
              and any(p.get('type') == 'input_image' for p in x['content']) and i > 1]
    for i in thumbs[:-1]: inp[i] = {'role': 'user', 'content': '（之前一版嘅縮圖已省略）'}


def run(job, system, content):
    from agent import with_model
    inp = [{'role': 'system', 'content': system},
           {'role': 'user', 'content': [_part(b) for b in with_model(content, MODEL)] + [{'type': 'input_text', 'text': NOTE}]}]
    tin = tout = searches = idle = 0
    for turn in range(MAX_TURNS):
        job.check_cancel()
        _compact(inp)
        job.log('Grok 分析中…')
        body = {'model': MODEL, 'input': inp, 'tools': TOOLS, 'store': False, 'max_output_tokens': 64000}
        if os.environ.get('XAI_REASONING'): body['reasoning'] = {'effort': os.environ['XAI_REASONING']}
        r = _post(body, job.log, job.check_cancel)
        u = r.get('usage') or {}
        tin += u.get('input_tokens', 0) or 0; tout += u.get('output_tokens', 0) or 0
        cached = ((u.get('input_tokens_details') or {}).get('cached_tokens') or 0)
        job.extra_cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6
        out = r.get('output') or []
        n_s = sum(1 for x in out if x.get('type') == 'web_search_call'); searches += n_s
        calls = [x for x in out if x.get('type') == 'function_call']
        msg = ''.join(_text(x) for x in out if x.get('type') == 'message').strip()
        status = r.get('status')
        job.log(f'Grok 回覆（{status}{"；工具 " + str(len(calls)) if calls else ""}{"；上網搜尋 " + str(n_s) + " 次" if n_s else ""}；'
                f'今輪輸入 {u.get("input_tokens", 0) or 0:,} token{"（快取 " + format(cached, ",") + "）" if cached else ""}；累計約 US${job.cost()}）')
        # 對話紀錄（store=False，每次重送）：只保留訊息同 function call
        if msg: inp.append({'role': 'assistant', 'content': msg})
        for c in calls: inp.append({'type': 'function_call', 'call_id': c['call_id'], 'name': c['name'], 'arguments': c.get('arguments') or ''})
        if status == 'incomplete' and calls:
            inp = inp[:len(inp) - len(calls)]
            inp.append({'role': 'user', 'content': '回覆被截斷。請重新用 build_report 提交完整 work 檔（精簡少少敘述）。'}); continue
        if calls:
            imgs = []
            for c in calls:
                try: args = json.loads(c.get('arguments') or '{}')
                except json.JSONDecodeError: args = None
                res = job.tool(types.SimpleNamespace(name=c['name'], id=c['call_id'], input=args))
                cont = res['content']
                if isinstance(cont, list):     # 成功：文字入 function 輸出，縮圖另外用 user 訊息俾佢睇
                    text = '\n'.join(x['text'] for x in cont if x['type'] == 'text')
                    imgs += [_part(x) for x in cont if x['type'] == 'image']
                else: text = cont
                inp.append({'type': 'function_call_output', 'call_id': c['call_id'], 'output': text})
            if imgs: inp.append({'role': 'user', 'content': [{'type': 'input_text', 'text': 'build 成功後嘅每頁縮圖（對照格式範本檢查版面）：'}] + imgs})
            if job.builds >= int(os.environ.get('MAX_BUILDS', '10')) and not job.pdf: raise RuntimeError(f'build 試咗 {job.builds} 次都未過 QA／格式擋位，停止')
            if job.done_revising(): return
            continue
        if job.pdf:
            job.log(f'完成（Grok；上網搜尋共 {searches} 次）：' + msg[:400]); return
        idle += 1
        if idle >= 3: raise RuntimeError('Grok 連續 3 次冇提交 work 檔，停止')
        inp.append({'role': 'user', 'content': '未有成功嘅 PDF。請用 build_report 工具提交完整 work 檔。'})
    raise RuntimeError('Grok 對話輪數用晒都未出到 PDF')
