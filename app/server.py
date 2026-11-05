"""server.py — JLaw 報告生成網站：撳掣出大盤報告、睇進度、下載 PDF、上載 Drive；另有每日定時排程。
環境變數：ANTHROPIC_API_KEY（主力）、XAI_API_KEY（後備：Claude 出錯先用 Grok）、GEN_PASSWORD（網站密碼，必須）、JLAW_ADMIN_PASSWORD（上載 Drive 用＝jlaw-report 嘅 ADMIN_PASSWORD）、
JLAW_SITE、DATA_DIR（默認 /data，Railway volume）、AUTO_MARKET（1＝開排程）、AUTO_START／AUTO_END（香港時間 HH:MM，默認 06:30／11:30）、AUTO_UPLOAD（1＝自動上載）。"""
import datetime as dt, hmac, json, os, queue, re, threading, time, traceback, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
import jlaw

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('DATA_DIR', '/data' if os.path.isdir('/data') else os.path.join(os.path.dirname(HERE), 'var'))
JOBS = os.path.join(DATA, 'jobs'); os.makedirs(JOBS, exist_ok=True)
PW = os.environ.get('GEN_PASSWORD', '')
HKZ = ZoneInfo('Asia/Hong_Kong')
Q = queue.Queue(); LOCK = threading.Lock()


def now(): return dt.datetime.now(HKZ).strftime('%Y-%m-%d %H:%M:%S')
def jpath(jid): return os.path.join(JOBS, jid, 'job.json')
def load(jid):
    try: return json.load(open(jpath(jid), encoding='utf-8'))
    except Exception: return None
def save(j):
    with LOCK:
        tmp = jpath(j['id']) + '.tmp'; json.dump(j, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False); os.replace(tmp, jpath(j['id']))
def all_jobs():
    out = [load(x) for x in os.listdir(JOBS)]
    return sorted([j for j in out if j], key=lambda j: j['created'], reverse=True)


def new_job(date, by='網頁', upload=False):
    for j in all_jobs():
        if j['date'] == date and j['status'] in ('queued', 'running'): return j, False
    jid = dt.datetime.now(HKZ).strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:4]
    os.makedirs(os.path.join(JOBS, jid))
    j = dict(id=jid, kind='market', date=date, status='queued', created=now(), by=by, auto_upload=upload, log=[], pdf=None, cost=0, uploaded=None)
    save(j); Q.put(jid); return j, True


def worker():
    import agent
    while True:
        jid = Q.get(); j = load(jid)
        if not j: continue
        j['status'] = 'running'; j['started'] = now(); save(j)
        def log(msg):
            j['log'].append(f'{dt.datetime.now(HKZ):%H:%M:%S} {msg}'); save(j); print(jid, msg, flush=True)
        job = agent.Job(jid, j['date'], os.path.join(JOBS, jid), log)
        try:
            job.run()
            j['status'] = 'done'; j['pdf'] = os.path.basename(job.pdf); j['pages'] = job.pages
            if j.get('auto_upload'):
                try: r = jlaw.upload(job.pdf); j['uploaded'] = now(); log('已上載 Drive：' + json.dumps(r, ensure_ascii=False)[:300])
                except Exception as e: log(f'⚠ 上載失敗：{e}')
        except Exception as e:
            traceback.print_exc(); j['status'] = 'failed'; j['error'] = str(e)[:2000]; log('✗ ' + str(e)[:500])
            if job.pdf: j['pdf'] = os.path.basename(job.pdf); j['pages'] = job.pages   # 之前有過一版成功
        j['cost'] = job.cost(); j['usage'] = job.usage; j['engine'] = job.engine; j['builds'] = job.builds; j['finished'] = now(); save(j)


def scheduler():
    """每 15 分鐘：香港時間喺 AUTO_START–AUTO_END 之間，最近美股交易日截圖齊、Drive 未有報告、今日未做過 → 自動出（失敗唔會重試）"""
    if os.environ.get('AUTO_MARKET') != '1': return
    a, b = os.environ.get('AUTO_START', '06:30'), os.environ.get('AUTO_END', '11:30')
    while True:
        try:
            t = dt.datetime.now(HKZ).strftime('%H:%M')
            if a <= t <= b:
                d = jlaw.last_us_trading_day()
                tried = any(j['date'] == d and j['by'] == '排程' for j in all_jobs())
                if not tried and not jlaw.has_report(d):
                    sh = jlaw.market_shots(d)
                    if sh['folder'] and not sh['missing']:
                        new_job(d, by='排程', upload=os.environ.get('AUTO_UPLOAD') == '1')
        except Exception as e: print('scheduler', e, flush=True)
        time.sleep(900)


class H(BaseHTTPRequestHandler):
    def _send(s, code, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str): body = body.encode()
        s.send_response(code); s.send_header('Content-Type', ctype); s.send_header('Content-Length', str(len(body))); s.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items(): s.send_header(k, v)
        s.end_headers(); s.wfile.write(body)

    def _authed(s):
        given = s.headers.get('x-password', '')
        return bool(PW) and hmac.compare_digest(given.encode(), PW.encode())

    def log_message(s, *a): pass

    def do_GET(s):
        u = urlparse(s.path); p = u.path; q = parse_qs(u.query)
        if p in ('/', '/index.html'):
            return s._send(200, open(os.path.join(HERE, 'static', 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
        if p == '/health': return s._send(200, {'ok': True})
        if not PW: return s._send(503, {'error': '伺服器未設定 GEN_PASSWORD'})
        if not s._authed(): return s._send(401, {'error': '密碼錯誤'})
        if p == '/api/jobs':
            return s._send(200, {'jobs': [{k: v for k, v in j.items() if k != 'log'} | {'last': (j['log'] or [''])[-1]} for j in all_jobs()[:30]],
                                 'auto': os.environ.get('AUTO_MARKET') == '1', 'can_upload': bool(os.environ.get('JLAW_ADMIN_PASSWORD'))})
        m = re.fullmatch(r'/api/jobs/([\w-]+)', p)
        if m:
            j = load(m.group(1)); return s._send(200, j) if j else s._send(404, {'error': '冇呢個 job'})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/pdf', p)
        if m:
            j = load(m.group(1))
            if not j or not j.get('pdf'): return s._send(404, {'error': '未有 PDF'})
            f = os.path.join(JOBS, j['id'], j['pdf'])
            from urllib.parse import quote
            return s._send(200, open(f, 'rb').read(), 'application/pdf', {'Content-Disposition': f"inline; filename*=UTF-8''{quote(j['pdf'])}"})
        if p == '/api/shots':
            d = (q.get('date') or [''])[0]
            try:
                if not d: d = jlaw.date_folders()[0][0]
                sh = jlaw.market_shots(d)
                return s._send(200, {'date': d, 'folder': sh['folder'], 'name': sh['name'], 'have': sorted(sh['files']), 'missing': sh['missing']})
            except Exception as e: return s._send(502, {'error': str(e)})
        if p == '/api/dates':
            try: return s._send(200, {'dates': [d for d, _ in jlaw.date_folders()[:30]], 'default': jlaw.last_us_trading_day()})
            except Exception as e: return s._send(502, {'error': str(e)})
        s._send(404, {'error': 'not found'})

    def do_POST(s):
        p = urlparse(s.path).path
        if not PW: return s._send(503, {'error': '伺服器未設定 GEN_PASSWORD'})
        if not s._authed(): return s._send(401, {'error': '密碼錯誤'})
        n = int(s.headers.get('Content-Length') or 0); body = json.loads(s.rfile.read(n) or b'{}') if n else {}
        if p == '/api/auth': return s._send(200, {'ok': True})
        if p == '/api/generate':
            d = str(body.get('date', ''))
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', d): return s._send(400, {'error': '日期要 YYYY-MM-DD'})
            if dt.date.fromisoformat(d).weekday() >= 5: return s._send(400, {'error': f'{d} 係週末，唔係美股交易日'})
            if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('XAI_API_KEY')): return s._send(503, {'error': '伺服器未設定 ANTHROPIC_API_KEY／XAI_API_KEY'})
            j, created = new_job(d, upload=bool(body.get('upload')))
            return s._send(200, {'job': j['id'], 'created': created})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/upload', p)
        if m:
            j = load(m.group(1))
            if not j or not j.get('pdf'): return s._send(404, {'error': '未有 PDF'})
            try:
                r = jlaw.upload(os.path.join(JOBS, j['id'], j['pdf'])); j['uploaded'] = now(); save(j)
                return s._send(200, {'ok': True, 'result': r})
            except Exception as e: return s._send(502, {'error': str(e)})
        s._send(404, {'error': 'not found'})


def main():
    for j in all_jobs():    # 重新部署：未完成嘅 job 標失敗（唔會自動重跑，避免重複收費）
        if j['status'] in ('queued', 'running'):
            j['status'] = 'failed'; j['error'] = '伺服器重新啟動，job 中斷；請再撳一次'; save(j)
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    port = int(os.environ.get('PORT', '8080'))
    print('listening', port, 'data', DATA, flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()


if __name__ == '__main__': main()
