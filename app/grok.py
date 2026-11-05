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
         {'type': 'function', 'name': 'build_report',
          'description': '提交完整 work 檔（Python 源碼，要有 BASIS、spec(m)、texts(m, S)、qa(m, S, T)），網站會跑 market/build.py（QA＋格式擋位）並回傳結果。失敗就照錯誤逐項改好，再提交完整 work 檔。',
          'parameters': {'type': 'object', 'properties': {'work_py': {'type': 'string', 'description': '完整 work 檔源碼'}}, 'required': ['work_py']}}]


def _part(b):
    """Anthropic 格式 content block → Responses API input 格式"""
    if b['type'] == 'text': return {'type': 'input_text', 'text': b['text']}
    src = b['source']
    return {'type': 'input_image', 'image_url': f'data:{src["media_type"]};base64,{src["data"]}', 'detail': 'high'}


def _post(body, log):
    key = os.environ['XAI_API_KEY']
    data = json.dumps(body, ensure_ascii=False).encode()
    for attempt in range(4):
        req = urllib.request.Request(BASE + '/responses', data=data, method='POST',
                                     headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:800]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                log(f'⚠ Grok API {e.code}，{20 * (attempt + 1)} 秒後重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'Grok API {e.code}：{msg}')
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3: log(f'⚠ 連唔到 Grok（{e}），重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'連唔到 Grok：{e}')


def _text(item):
    return ''.join(c.get('text', '') for c in item.get('content') or [] if c.get('type') in ('output_text', 'text'))


def run(job, system, content):
    from agent import with_model
    inp = [{'role': 'system', 'content': system},
           {'role': 'user', 'content': [_part(b) for b in with_model(content, MODEL)] + [{'type': 'input_text', 'text': NOTE}]}]
    tin = tout = searches = idle = 0
    for turn in range(MAX_TURNS):
        job.log('Grok 分析中…')
        body = {'model': MODEL, 'input': inp, 'tools': TOOLS, 'store': False, 'max_output_tokens': 64000}
        if os.environ.get('XAI_REASONING'): body['reasoning'] = {'effort': os.environ['XAI_REASONING']}
        r = _post(body, job.log)
        u = r.get('usage') or {}
        tin += u.get('input_tokens', 0) or 0; tout += u.get('output_tokens', 0) or 0
        job.extra_cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6
        out = r.get('output') or []
        n_s = sum(1 for x in out if x.get('type') == 'web_search_call'); searches += n_s
        calls = [x for x in out if x.get('type') == 'function_call']
        msg = ''.join(_text(x) for x in out if x.get('type') == 'message').strip()
        status = r.get('status')
        job.log(f'Grok 回覆（{status}{"；工具 " + str(len(calls)) if calls else ""}{"；上網搜尋 " + str(n_s) + " 次" if n_s else ""}；累計約 US${job.cost()}）')
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
            continue
        if job.pdf:
            job.log(f'完成（Grok；上網搜尋共 {searches} 次）：' + msg[:400]); return
        idle += 1
        if idle >= 3: raise RuntimeError('Grok 連續 3 次冇提交 work 檔，停止')
        inp.append({'role': 'user', 'content': '未有成功嘅 PDF。請用 build_report 工具提交完整 work 檔。'})
    raise RuntimeError('Grok 對話輪數用晒都未出到 PDF')
