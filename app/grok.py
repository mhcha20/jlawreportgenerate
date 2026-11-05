"""grok.py — Claude 用唔到時嘅後備：用 xAI Grok（OpenAI 相容 chat completions，https://api.x.ai/v1）做同一個大盤報告流程。
同 Claude 版一樣：睇 19 張圖 → 寫 work 檔 → build_report 工具跑 QA → 失敗改好再交。分別：冇 web_search（催化劑／日程標「未核實」）。
環境變數：XAI_API_KEY（必須）、XAI_MODEL（默認 grok-4）、XAI_BASE（默認 https://api.x.ai/v1）、XAI_PRICE_IN／XAI_PRICE_OUT（美元／百萬 token，只用嚟估用量）。"""
import json, os, time, types, urllib.error, urllib.request

BASE = os.environ.get('XAI_BASE', 'https://api.x.ai/v1').rstrip('/')
MODEL = os.environ.get('XAI_MODEL', 'grok-4')
PRICE_IN = float(os.environ.get('XAI_PRICE_IN', '3'))
PRICE_OUT = float(os.environ.get('XAI_PRICE_OUT', '15'))
MAX_TURNS = 30
NOTE = ('（後備模式：今次由 xAI Grok 代替 Claude 做，冇 web_search 工具。過去 5 日催化劑同未來一星期日程只可以寫你肯定嘅已知事項，'
        '其餘一律標「未核實」，唔好補造；S["meta"]["ai"] 寫上面嘅模型識別碼，ai_note 註明「Claude API 用唔到，後備模型」。）')

TOOLS = [{'type': 'function', 'function': {
    'name': 'build_report',
    'description': '提交完整 work 檔（Python 源碼，要有 BASIS、spec(m)、texts(m, S)、qa(m, S, T)），網站會跑 market/build.py 並回傳結果。失敗就照錯誤改好，再提交完整 work 檔。',
    'parameters': {'type': 'object', 'properties': {'work_py': {'type': 'string', 'description': '完整 work 檔源碼'}}, 'required': ['work_py']}}}]


def _part(b):
    """Anthropic 格式 content block → OpenAI 相容格式"""
    if b['type'] == 'text': return {'type': 'text', 'text': b['text']}
    src = b['source']
    return {'type': 'image_url', 'image_url': {'url': f'data:{src["media_type"]};base64,{src["data"]}', 'detail': 'high'}}


def _post(body, log):
    key = os.environ['XAI_API_KEY']
    data = json.dumps(body, ensure_ascii=False).encode()
    for attempt in range(4):
        req = urllib.request.Request(BASE + '/chat/completions', data=data, method='POST',
                                     headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=1200) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                log(f'⚠ Grok API {e.code}，{20 * (attempt + 1)} 秒後重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'Grok API {e.code}：{msg}')
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3: log(f'⚠ 連唔到 Grok（{e}），重試'); time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f'連唔到 Grok：{e}')


def run(job, system, content):
    from agent import with_model
    msgs = [{'role': 'system', 'content': system},
            {'role': 'user', 'content': [_part(b) for b in with_model(content, MODEL)] + [{'type': 'text', 'text': NOTE}]}]
    tin = tout = 0
    for turn in range(MAX_TURNS):
        job.log('Grok 分析中…')
        r = _post({'model': MODEL, 'messages': msgs, 'tools': TOOLS, 'max_tokens': 64000}, job.log)
        u = r.get('usage') or {}
        tin += u.get('prompt_tokens', 0); tout += u.get('completion_tokens', 0)
        job.extra_cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6
        ch = r['choices'][0]; m = ch['message']; fin = ch.get('finish_reason')
        job.log(f'Grok 回覆（{fin}；累計約 US${job.cost()}）')
        msgs.append({k: v for k, v in m.items() if k in ('role', 'content', 'tool_calls') and v is not None})
        calls = m.get('tool_calls') or []
        if calls and fin != 'length':
            imgs = []
            for c in calls:
                try: args = json.loads(c['function']['arguments'] or '{}')
                except json.JSONDecodeError: args = None
                res = job.tool(types.SimpleNamespace(name=c['function']['name'], id=c['id'], input=args))
                cont = res['content']
                if isinstance(cont, list):     # 成功：文字入 tool 訊息，縮圖另外用 user 訊息俾佢睇
                    text = '\n'.join(x['text'] for x in cont if x['type'] == 'text')
                    imgs += [_part(x) for x in cont if x['type'] == 'image']
                else: text = cont
                msgs.append({'role': 'tool', 'tool_call_id': c['id'], 'content': text})
            if imgs: msgs.append({'role': 'user', 'content': [{'type': 'text', 'text': 'build 成功後嘅每頁縮圖：'}] + imgs})
            if job.builds >= int(os.environ.get('MAX_BUILDS', '8')) and not job.pdf: raise RuntimeError(f'build 試咗 {job.builds} 次都未過 QA，停止')
            continue
        if fin == 'length':
            msgs.append({'role': 'user', 'content': '回覆被截斷。請重新用 build_report 提交完整 work 檔（精簡敘述）。'}); continue
        if job.pdf:
            job.log('完成（Grok）：' + str(m.get('content') or '')[:400]); return
        msgs.append({'role': 'user', 'content': '未有成功嘅 PDF。請用 build_report 工具提交完整 work 檔。'})
    raise RuntimeError('Grok 對話輪數用晒都未出到 PDF')
