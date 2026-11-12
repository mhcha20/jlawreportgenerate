"""capture.py — 網頁遙控 Mac 截圖（用戶 2026-11-07 要求：唔使開 Terminal，網頁撳掣就喺 Mac 手動截圖）。

做法：網頁將「動作」排隊（DATA_DIR/capture.json）；Mac 上 screencapture 嘅 bin/remote_agent.py 每 30 秒
POST /api/capture/agent/poll 攞下一個動作，照做，再 POST /api/capture/agent/<id>/progress 傳紀錄同結果。
Mac 主動連網站，Mac 唔使開任何對外端口。Mac 嘅請求用 header x-capture-token 對 Railway 變數 CAPTURE_TOKEN（≥24 字）。
只接受下面 ACTIONS 列明嘅動作同參數（日期、代號、市場都會驗證），Mac 唔會執行任何自由文字指令。"""
import datetime as dt, hmac, json, os, re, threading, uuid
from zoneinfo import ZoneInfo

HKZ = ZoneInfo('Asia/Hong_Kong')
LOCK = threading.Lock()
KEEP = 60                      # 保留最近幾多個動作
OFFLINE_AFTER = 180            # Mac 幾多秒冇聯絡當離線

# 動作：label＝網頁顯示；need＝必填參數（date／tickers／markets）；opt＝選填；futu＝要用富途（截個股）
ACTIONS = {
    'check':         dict(label='檢查 Drive 齊唔齊', need=['date']),
    'fill':          dict(label='檢查並自動補截欠嘅', need=['date'], futu=True),
    'stocks':        dict(label='截股票', need=['tickers'], opt=['date'], futu=True),
    'us_market':     dict(label='截美股大盤 19 張', need=['date']),
    'asia_market':   dict(label='截香港／日本／韓國大盤', need=['markets', 'date']),
    'rerun_morning': dict(label='重跑朝早美股排程', need=[], futu=True),
    'rerun_asia':    dict(label='重跑 17:15 亞洲排程', need=[], futu=True),
    'fix_display':   dict(label='修正螢幕解像度', need=[]),
    'update':        dict(label='更新 Mac 程式', need=[]),
    'add_stock':     dict(label='加股票入截圖清單', need=['items']),      # 用戶 2026-11-12：網站加／移除股票
    'remove_stock':  dict(label='移除股票（停止截圖）', need=['tickers']),
}


def _path(data): return os.path.join(data, 'capture.json')
def _now(): return dt.datetime.now(HKZ).strftime('%Y-%m-%d %H:%M:%S')


def _load(data):
    try: return json.load(open(_path(data), encoding='utf-8'))
    except Exception: return {'tasks': [], 'mac': {}}


def _save(data, st):
    st['tasks'] = st['tasks'][-KEEP:]
    tmp = _path(data) + '.tmp'
    json.dump(st, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False); os.replace(tmp, _path(data))


def token_ok(given):
    want = os.environ.get('CAPTURE_TOKEN', '')
    return len(want) >= 24 and bool(given) and hmac.compare_digest(given.encode(), want.encode())


def clean(action, params):
    """驗證動作同參數；唔啱 raise ValueError（訊息俾網頁顯示）"""
    if action not in ACTIONS: raise ValueError(f'唔識呢個動作：{action}')
    a, p, out = ACTIONS[action], params or {}, {}
    for k in a['need'] + a.get('opt', []):
        v = p.get(k)
        if v in (None, '', []):
            if k in a['need']: raise ValueError(f'缺少 {k}')
            continue
        if k == 'date':
            v = str(v).strip()
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', v): raise ValueError('日期要 YYYY-MM-DD')
            dt.date.fromisoformat(v)
        elif k == 'tickers':
            v = [t.strip().upper() for t in re.split(r'[\s,，、]+', v) if t.strip()] if isinstance(v, str) else [str(t).strip().upper() for t in v]
            bad = [t for t in v if not re.fullmatch(r'[A-Z0-9.]{1,10}', t)]
            if bad: raise ValueError(f'代號唔啱：{"、".join(bad)}')
            if not v: raise ValueError('至少一隻股票')
            if len(v) > 40: raise ValueError('一次最多 40 隻')
        elif k == 'items':
            import stocklist
            if not isinstance(v, list) or not 1 <= len(v) <= 20: raise ValueError('一次加 1–20 隻')
            v = [stocklist.validate_item(it) for it in v]
        elif k == 'markets':
            v = [m for m in (v if isinstance(v, list) else str(v).split(',')) if m in ('hk', 'jp', 'kr')]
            if not v: raise ValueError('揀最少一個市場')
        out[k] = v
    return out


def add(data, action, params, by):
    p = clean(action, params)
    with LOCK:
        st = _load(data)
        same = [t for t in st['tasks'] if t['status'] in ('queued', 'running') and t['action'] == action and t['params'] == p]
        if same: return same[0], False
        t = dict(id=dt.datetime.now(HKZ).strftime('%m%d-%H%M%S-') + uuid.uuid4().hex[:4], action=action, label=ACTIONS[action]['label'],
                 params=p, status='queued', created=_now(), by=by, log='', rc=None)
        st['tasks'].append(t); _save(data, st)
    return t, True


def view(data):
    with LOCK: st = _load(data)
    mac = st.get('mac') or {}
    age = None
    if mac.get('at'):
        try: age = int((dt.datetime.now(HKZ) - dt.datetime.fromisoformat(mac['at'])).total_seconds())
        except Exception: age = None
    mac = dict(mac, age=age, online=age is not None and age <= OFFLINE_AFTER)
    tasks = [dict(t, log=t.get('log', '')[-4000:]) for t in reversed(st['tasks'])]
    return {'mac': mac, 'tasks': tasks, 'actions': {k: v['label'] for k, v in ACTIONS.items()}, 'token_set': len(os.environ.get('CAPTURE_TOKEN', '')) >= 24}


def cancel(data, tid):
    with LOCK:
        st = _load(data)
        t = next((x for x in st['tasks'] if x['id'] == tid), None)
        if not t: raise ValueError('冇呢個動作')
        if t['status'] == 'queued': t['status'] = 'cancelled'; t['finished'] = _now()
        elif t['status'] == 'running': t['cancel'] = True   # Mac 下次傳紀錄時會收到，停咗佢
        else: raise ValueError('已經完咗')
        _save(data, st)
    return t


def poll(data, info):
    """Mac 每 30 秒：報到（busy＝排程或者其他截圖行緊）；唔忙就攞最舊一個排緊隊嘅動作"""
    with LOCK:
        st = _load(data)
        st['mac'] = {'at': dt.datetime.now(HKZ).isoformat(timespec='seconds'), 'host': str(info.get('host', ''))[:60],
                     'version': str(info.get('version', ''))[:40], 'busy': str(info.get('busy', ''))[:200]}
        cur = info.get('current')
        for t in st['tasks']:   # Mac 話冇做緊呢個，但網站仲當做緊（Mac 重開機／程式更新）→ 標中斷
            if t['status'] == 'running' and t['id'] != cur:
                t['status'] = 'failed'; t['finished'] = _now(); t['summary'] = 'Mac 中途停咗（重開機或者程式重新啟動），冇完成'
        task = None
        if not info.get('busy') and not cur and not any(t['status'] == 'running' for t in st['tasks']):
            task = next((t for t in st['tasks'] if t['status'] == 'queued'), None)
            if task: task['status'] = 'running'; task['started'] = _now()
        _save(data, st)
    return {'task': {k: task[k] for k in ('id', 'action', 'params')} if task else None}


def progress(data, tid, body):
    """Mac 傳紀錄（log 尾段）；done＝True 時記結果。回傳 cancel＝True 叫 Mac 停"""
    with LOCK:
        st = _load(data)
        t = next((x for x in st['tasks'] if x['id'] == tid), None)
        if not t: return {'cancel': True}
        t['log'] = str(body.get('log', ''))[-8000:]
        if body.get('done'):
            rc = body.get('rc'); t['rc'] = rc; t['finished'] = _now()
            t['status'] = 'cancelled' if t.get('cancel') else ('done' if rc == 0 else 'failed')
            if body.get('summary'): t['summary'] = str(body['summary'])[:500]
        _save(data, st)
        return {'cancel': bool(t.get('cancel'))}
