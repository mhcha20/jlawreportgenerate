"""futu_verify.py — 經 Mac 上嘅富途 OpenD 核實行情（用戶 2026-11-19 要求：網站出報告時用富途數據核實）。

做法：報告 job 呼叫 kline() → 請求放入記憶體隊列 → Mac（screencapture bin/futu_bridge.py，由 remote_agent.py 開 thread）
長輪詢 POST /api/futu/agent/poll（header x-capture-token＝CAPTURE_TOKEN）攞走 → 經本機 FutuOpenD 攞日線 →
POST /api/futu/agent/result 交返 → job 收到結果同 Yahoo 行情比對。Mac 只用富途行情接口，唔開交易。
Mac 離線、OpenD 未開／未登入、逾時都唔會令報告失敗：報告寫「今次冇富途核實」。"""
import datetime as dt, itertools, os, threading, time
from zoneinfo import ZoneInfo

HKZ = ZoneInfo('Asia/Hong_Kong')
WAIT = int(os.environ.get('FUTU_WAIT', '120'))   # job 等 Mac 回覆最多幾多秒
_cv = threading.Condition()
_queue, _results, _ids = [], {}, itertools.count(1)
_status = {'at': 0.0, 'ok': False, 'msg': '未有聯絡', 'host': ''}


class FutuError(Exception):
    pass


def symbol(t):
    """本地代號 → 富途代號；唔支援（韓股、ADR／外國股）回 None。"""
    import jlaw
    t = t.strip().upper()
    if t in jlaw.ADR: return None
    if t.isalpha() or (t[:1].isalpha() and t.replace('.', '').isalnum()): return f'US.{t}'
    if t.isdigit() and (len(t) == 5 or (len(t) == 4 and t.startswith('0'))): return f'HK.{int(t):05d}'
    if t.isdigit() and len(t) == 4: return f'JP.{t}'
    return None


def online():
    return time.time() - _status['at'] < 90


def status():
    age = int(time.time() - _status['at']) if _status['at'] else None
    return {'online': online(), 'ok': _status['ok'] and online(), 'msg': _status['msg'] if online() else ('Mac 富途橋接未聯絡' if age is None else f'Mac 富途橋接 {age} 秒冇聯絡'),
            'host': _status['host'], 'age': age}


def _request(kind, params, wait=WAIT):
    if not online(): raise FutuError('Mac 富途橋接離線（Mac 未開、remote agent 未更新，或者網站啱啱重開未聯絡）')
    rid = f'{int(time.time())}-{next(_ids)}'
    with _cv:
        _queue.append({'id': rid, 'kind': kind, 'params': params, 'at': time.time()}); _cv.notify_all()
        end = time.time() + wait
        while rid not in _results:
            left = end - time.time()
            if left <= 0:
                _queue[:] = [q for q in _queue if q['id'] != rid]
                raise FutuError(f'Mac {wait} 秒內冇回覆')
            _cv.wait(left)
        r = _results.pop(rid)
    if not r.get('ok'): raise FutuError(r.get('msg') or '富途出錯')
    return r


def kline(tickers, date, days=10):
    """{本地代號: {'bars': {日期: {o,h,l,c,v}}, 'src'} 或 {'error'}}；唔支援嘅代號唔會問。"""
    codes = {symbol(t): t for t in tickers if symbol(t)}
    if not codes: return {}
    start = (dt.date.fromisoformat(date) - dt.timedelta(days=days)).isoformat()
    data = _request('kline', {'codes': list(codes)[:40], 'start': start, 'end': date})['data']
    return {codes[c]: v for c, v in data.items() if c in codes}


# ---- Mac 嗰邊（server.py 轉駁）
def agent_poll(body, hold=25):
    """Mac 長輪詢：報狀態；有請求即刻回，冇就等最多 hold 秒"""
    with _cv:
        _status.update(at=time.time(), ok=bool(body.get('ok')), msg=str(body.get('msg', ''))[:300], host=str(body.get('host', ''))[:60])
        end = time.time() + hold
        while True:
            _queue[:] = [q for q in _queue if time.time() - q['at'] < WAIT + 30]
            if _queue: return {'req': _queue.pop(0)}
            left = end - time.time()
            if left <= 0: return {'req': None}
            _cv.wait(left)
            _status['at'] = time.time()


def agent_result(body):
    rid = str(body.get('id', ''))
    with _cv:
        _status['at'] = time.time()
        if body.get('msg') and 'data' not in body: _status.update(ok=bool(body.get('ok')), msg=str(body['msg'])[:300])
        _results[rid] = body; _cv.notify_all()
        for k in list(_results)[:-50]: _results.pop(k, None)   # 冇人等嘅舊結果唔好積
    return {'ok': True}


# ---- 比對
def compare(fb, mine, ref='Yahoo'):
    """富途 bar 同本地 bar：開高低收差 ≤0.02 或 ≤0.05% 當一致（同 Longbridge 一樣）"""
    ok, parts = True, []
    for k, name in (('o', '開'), ('h', '高'), ('l', '低'), ('c', '收')):
        diff = abs(fb[k] - mine[k]); good = diff <= 0.02 or diff <= 0.0005 * abs(fb[k]); ok &= good
        parts.append(f'{name} 富途 {fb[k]:g}／{ref} {mine[k]:g}{"" if good else "（差 " + format(diff, ".4f") + "）"}')
    vr = fb['v'] / mine['v'] if mine.get('v') else float('nan')
    parts.append(f'量 富途 {fb["v"]:,.0f}／{ref} {mine["v"]:,.0f}（比 {vr:.2f}，口徑可能唔同）')
    return ok, '；'.join(parts)


def verify_dir(ddir, date, log):
    """大盤：data 資料夾 _meta.json 嘅 have 每隻最後一根（要係 date）同富途比"""
    import json
    pairs = []
    try:
        for t in json.load(open(os.path.join(ddir, '_meta.json')))['have']:
            r = json.load(open(os.path.join(ddir, f'{t}.json')))['rows'][-1]
            if r.get('d') == date: pairs.append((t, r))
    except Exception as e: return f'今次冇富途核實（讀唔到行情檔：{e}）。'
    return verify(pairs, date, log)


def verify(pairs, date, log):
    """pairs＝[(代號, 本地 bar dict{o,h,l,c,v})]（報告日嗰根）→ 俾 AI 嘅一段文字。任何失敗都只係寫冇核實。"""
    pairs = [(t, b) for t, b in pairs if symbol(t)]
    if not pairs: return '今次冇富途核實（呢個市場富途橋接唔支援）。'
    try: fk = kline([t for t, _ in pairs], date)
    except FutuError as e:
        log(f'⚠ 富途核實：{e}'); return f'今次冇富途核實（{e}）。報告照寫，資料來源唔好提富途。'
    ok_list, bad, skip = [], [], []
    for t, mine in pairs:
        r = fk.get(t) or {}
        b = (r.get('bars') or {}).get(date)
        if not b: skip.append(f'{t}（{r.get("error") or "富途未有 " + date + " 嗰根"}）'); continue
        ok, txt = compare(b, mine)
        tag = '（富途快照）' if r.get('src') == 'snapshot' else ''
        (ok_list if ok else bad).append(f'{t}{tag}' if ok else f'{t}{tag}：{txt}')
    log(f'富途核實：一致 {len(ok_list)}、不一致 {len(bad)}、未比對 {len(skip)}')
    lines = []
    if ok_list: lines.append(f'{date} 開高低收同富途一致（差 ≤0.02 或 ≤0.05%）：{"、".join(ok_list)}。')
    if bad: lines.append('⚠ 同富途不一致（資料來源一節並列兩邊數字，查日期／復權）：' + '；'.join(bad))
    if skip: lines.append('富途未能比對：' + '、'.join(skip) + '。')
    return '\n'.join(lines)
