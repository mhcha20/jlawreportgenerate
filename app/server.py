"""server.py — JLaw 報告生成網站：撳掣出大盤報告、睇進度、下載 PDF、上載 Drive；另有每日定時排程。
環境變數：ANTHROPIC_API_KEY（主力）、XAI_API_KEY（後備：Claude 出錯先用 Grok）、GEN_PASSWORD（網站密碼，必須）、JLAW_ADMIN_PASSWORD（上載 Drive 用＝jlaw-report 嘅 ADMIN_PASSWORD）、
JLAW_SITE、DATA_DIR（默認 /data，Railway volume）、AUTO_MARKET（1＝開排程）、AUTO_START／AUTO_END（香港時間 HH:MM，默認 06:30／11:30）、AUTO_UPLOAD（1＝自動上載）。"""
import datetime as dt, hmac, json, os, queue, re, threading, time, traceback, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
from zoneinfo import ZoneInfo
import jlaw, auth, longbridge


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat()

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('DATA_DIR', '/data' if os.path.isdir('/data') else os.path.join(os.path.dirname(HERE), 'var'))
JOBS = os.path.join(DATA, 'jobs'); os.makedirs(JOBS, exist_ok=True)
PW = os.environ.get('GEN_PASSWORD', '')
HKZ = ZoneInfo('Asia/Hong_Kong')
Q = queue.Queue(); LOCK = threading.Lock()


WATCH = os.path.join(DATA, 'watchlist.json')
WATCH_DEFAULT = ['CAT', 'FPS', 'AAPL', 'ESTC', 'BE', 'XLV', 'PLTR', 'NVDA', 'MCD', 'SPCX', 'WM', 'COPX']   # 用戶 2026-11-06 每日睇嘅股票


def watchlist():
    try: return json.load(open(WATCH, encoding='utf-8'))['tickers']
    except Exception: return list(WATCH_DEFAULT)


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


ENGINES = ('auto', 'gemini', 'grok')


def new_job(date, by='網頁', upload=False, kind='market', ticker=None, engine='auto'):
    for j in all_jobs():
        if j['date'] == date and j.get('kind', 'market') == kind and j.get('ticker') == ticker and j['status'] in ('queued', 'running'): return j, False
    jid = dt.datetime.now(HKZ).strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:4]
    os.makedirs(os.path.join(JOBS, jid))
    j = dict(id=jid, kind=kind, ticker=ticker, date=date, status='queued', created=now(), by=by, auto_upload=upload, log=[], pdf=None, pdfs=[], cost=0, uploaded=None,
             engine_pref=engine if engine in ENGINES else 'auto')
    save(j); Q.put(jid); return j, True


MARKET_LOCK = threading.Lock()   # 大盤報告共用 gen/market/data，一次只可以做一份


CANCEL = set()   # 用戶撳咗取消嘅 job id：排緊隊就唔做；做緊就喺下一輪 AI 回覆之前停（agent.Job.check_cancel）


def worker():
    import agent, stock
    while True:
        jid = Q.get(); j = load(jid)
        if not j: continue
        if jid in CANCEL or j.get('status') == 'cancelled':
            CANCEL.discard(jid)
            if j.get('status') == 'queued': j['status'] = 'cancelled'; j['finished'] = now(); save(j)
            continue
        if j.get('kind') == 'market' and not MARKET_LOCK.acquire(blocking=False):
            Q.put(jid); time.sleep(5); continue
        try: _run(j, agent, stock)
        finally:
            if j.get('kind') == 'market': MARKET_LOCK.release()


def _run(j, agent, stock):
    jid = j['id']
    if True:
        j['status'] = 'running'; j['started'] = now(); save(j)
        def log(msg):
            j['log'].append(f'{dt.datetime.now(HKZ):%H:%M:%S} {msg}'); save(j); print(jid, msg, flush=True)
        folder = os.path.join(JOBS, jid)
        if j.get('kind') == 'stock': job = stock.StockJob(jid, j['date'], j['ticker'], folder, log)
        elif j.get('kind') == 'amarket':
            import asia
            job = asia.AsiaJob(jid, j['date'], j['ticker'], folder, log)   # ticker＝市場 hk／jp／kr
        else: job = agent.Job(jid, j['date'], folder, log)
        job.cancelled = lambda: jid in CANCEL
        job.engine_pref = j.get('engine_pref', 'auto')
        def keep():
            j['pdfs'] = [os.path.basename(x) for x in job.pdfs]; j['pdf'] = j['pdfs'][0] if j['pdfs'] else None; j['pages'] = job.pages
            if getattr(job, 'info', None): j['result'] = {k: job.info.get(k) for k in ('rating', 'score', 'action', 'tier', 'signals')}
        try:
            job.run()
            j['status'] = 'done'; keep()
            if j.get('auto_upload'):
                try:
                    for f in job.pdfs: r = jlaw.upload(f); log('已上載 Drive：' + json.dumps(r, ensure_ascii=False)[:200])
                    j['uploaded'] = now()
                except Exception as e: log(f'⚠ 上載失敗：{e}')
        except agent.Cancelled:
            CANCEL.discard(jid); j['status'] = 'cancelled'; j['error'] = '已取消'; log('■ 用戶取消')
        except Exception as e:
            traceback.print_exc(); j['status'] = 'failed'; j['error'] = str(e)[:2000]; log('✗ ' + str(e)[:500])
            if job.pdfs: keep()   # 之前有過一版成功
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
        s.send_response(code); s.send_header('Content-Type', ctype); s.send_header('Content-Length', str(len(body)))
        if 'Cache-Control' not in (extra or {}): s.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items(): s.send_header(k, v)
        s.end_headers(); s.wfile.write(body)

    def _user(s):
        """已登入：Google cookie 嘅 email；或者（密碼登入未關）啱密碼 → '密碼'。否則 None"""
        e = auth.read_cookie(s.headers.get('Cookie'), DATA)
        if e: return e
        given = s.headers.get('x-password', '')
        if auth.password_on() and PW and hmac.compare_digest(given.encode(), PW.encode()): return '密碼'
        return None

    def _authed(s): return bool(s._user())

    def _redirect(s, url, cookies=()):
        s.send_response(302); s.send_header('Location', url); s.send_header('Cache-Control', 'no-store')
        for c in cookies: s.send_header('Set-Cookie', c)
        s.send_header('Content-Length', '0'); s.end_headers()

    def _auth_routes(s, p, q):
        """/auth/google（去 Google）、/auth/callback（返嚟）、/auth/logout；/api/me 俾網頁知點樣登入"""
        secure = '; Secure' if auth.base_url(s.headers).startswith('https') else ''
        if p == '/api/me':
            return s._send(200, {'user': s._user(), 'google': auth.google_on(), 'password': auth.password_on(),
                                 'engines': {'claude': bool(os.environ.get('ANTHROPIC_API_KEY')), 'grok': bool(os.environ.get('XAI_API_KEY')), 'gemini': bool(os.environ.get('GEMINI_API_KEY'))}}) or True
        if p == '/auth/google':
            if not auth.google_on(): return s._send(503, {'error': '未設定 GOOGLE_CLIENT_ID／GOOGLE_CLIENT_SECRET'}) or True
            st = uuid.uuid4().hex
            return s._redirect(auth.login_url(s.headers, st), [f'jlgen_state={st}; Path=/auth; Max-Age=600; HttpOnly; SameSite=Lax{secure}']) or True
        if p == '/auth/callback':
            st = next((c.split('=', 1)[1] for c in (s.headers.get('Cookie') or '').split(';') if c.strip().startswith('jlgen_state=')), '')
            err = (q.get('error') or [''])[0]
            try:
                if err: raise ValueError('Google 登入取消／失敗：' + err)
                if not st or not hmac.compare_digest(st.strip(), (q.get('state') or [''])[0]): raise ValueError('登入逾時或者唔係由呢度開始，請再撳一次「用 Google 登入」')
                email = auth.exchange((q.get('code') or [''])[0], s.headers)
            except Exception as e:
                return s._redirect('/?login_error=' + quote(str(e)[:200])) or True
            if email not in auth.ALLOWED:
                return s._redirect('/?login_error=' + quote(f'{email} 冇權限登入呢個網站')) or True
            print('login', email, flush=True)
            return s._redirect('/', [f'{auth.COOKIE}={auth.make_cookie(email, DATA)}; Path=/; Max-Age={auth.MAX_AGE}; HttpOnly; SameSite=Lax{secure}',
                                     f'jlgen_state=; Path=/auth; Max-Age=0{secure}']) or True
        if p == '/auth/logout':
            return s._redirect('/', [f'{auth.COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure}']) or True
        return False

    def log_message(s, *a): pass

    def do_GET(s):
        u = urlparse(s.path); p = u.path; q = parse_qs(u.query)
        if p in ('/', '/index.html'):
            return s._send(200, open(os.path.join(HERE, 'static', 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
        if p == '/health': return s._send(200, {'ok': True})
        if s._auth_routes(p, q): return
        if not (PW or auth.google_on()): return s._send(503, {'error': '伺服器未設定登入方式（GOOGLE_CLIENT_ID 或 GEN_PASSWORD）'})
        if not s._authed(): return s._send(401, {'error': '未登入'})
        if p == '/api/jobs':
            aj = all_jobs()
            return s._send(200, {'jobs': [{k: v for k, v in j.items() if k != 'log'} | {'last': (j['log'] or [''])[-1]} for j in aj[:200]],
                                 'n_queued': sum(1 for j in aj if j['status'] == 'queued'), 'n_running': sum(1 for j in aj if j['status'] == 'running'),
                                 'auto': os.environ.get('AUTO_MARKET') == '1', 'can_upload': bool(os.environ.get('JLAW_ADMIN_PASSWORD'))})
        m = re.fullmatch(r'/api/jobs/([\w-]+)', p)
        if m:
            j = load(m.group(1)); return s._send(200, j) if j else s._send(404, {'error': '冇呢個 job'})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/page', p)   # 網頁內閱讀：PDF 第 p 頁轉 PNG（快取喺 job 資料夾）
        if m:
            j = load(m.group(1)); names = (j or {}).get('pdfs') or ([j['pdf']] if j and j.get('pdf') else [])
            i, pg = int((q.get('i') or ['0'])[0]), int((q.get('p') or ['1'])[0])
            if not names or not 0 <= i < len(names) or pg < 1: return s._send(404, {'error': '未有 PDF'})
            folder = os.path.join(JOBS, j['id']); pdf = os.path.join(folder, names[i])
            if not j.get('npages') or str(i) not in j['npages']:
                import subprocess
                info = subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout
                j.setdefault('npages', {})[str(i)] = int(re.search(r'Pages:\s+(\d+)', info).group(1)); save(j)
            n = j['npages'][str(i)]
            if (q.get('count') or [''])[0]: return s._send(200, {'pages': n, 'name': names[i]})
            if pg > n: return s._send(404, {'error': '冇呢頁'})
            png = os.path.join(folder, f'view_{i}_{pg}.png')
            if not os.path.exists(png):
                import subprocess
                subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', '-f', str(pg), '-l', str(pg), pdf, png[:-4]], capture_output=True, timeout=120)
            if not os.path.exists(png): return s._send(500, {'error': '轉圖失敗'})
            return s._send(200, open(png, 'rb').read(), 'image/png', {'Cache-Control': 'private, max-age=86400'})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/pdf', p)
        if m:
            j = load(m.group(1)); names = (j or {}).get('pdfs') or ([j['pdf']] if j and j.get('pdf') else [])
            i = int((q.get('i') or ['0'])[0])
            if not names or not 0 <= i < len(names): return s._send(404, {'error': '未有 PDF'})
            f = os.path.join(JOBS, j['id'], names[i])
            from urllib.parse import quote
            return s._send(200, open(f, 'rb').read(), 'application/pdf', {'Content-Disposition': f"inline; filename*=UTF-8''{quote(names[i])}"})
        if p == '/api/stocks':
            d = (q.get('date') or [''])[0]
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', d): return s._send(400, {'error': '日期要 YYYY-MM-DD'})
            try:
                th = jlaw.themes(); rows = []; dc = jlaw.drive_cards(d)
                mine = {j.get('ticker') for j in all_jobs() if j.get('kind') == 'stock' and j['date'] == d and j['status'] == 'done'}
                busy = {j.get('ticker') for j in all_jobs() if j.get('kind') == 'stock' and j['date'] == d and j['status'] in ('queued', 'running')}
                sl, at = jlaw.stock_list(d)
                for r in sl:
                    x = {k: r.get(k) for k in ('ticker', 'status', 'have', 'need', 'missing', 'layout')}
                    if r.get('kind') == 'ADR': x['layout'] = 'foreign'
                    tk = r.get('ticker', ''); t2 = tk.zfill(5) if tk.isdigit() and len(tk) <= 5 else tk
                    x['theme'], x['name'] = th.get(tk) or th.get(t2) or ('未分類', '')
                    x['done'] = 'busy' if tk in busy else 'site' if tk in mine else 'drive' if tk in dc else ''   # 已經出過／做緊：網頁會提示
                    rows.append(x)
                return s._send(200, {'date': d, 'rows': rows, 'themes_ok': bool(th), 'checked_at': at or now_iso()})
            except Exception as e: return s._send(502, {'error': str(e)})
        if p == '/api/market_done':   # 大盤：呢日本站做過／Drive 已有？
            d = (q.get('date') or [''])[0]
            site = any(j.get('kind', 'market') == 'market' and j['date'] == d and j['status'] in ('done', 'queued', 'running') for j in all_jobs())
            return s._send(200, {'site': site, 'drive': jlaw.has_report(d)})
        if p == '/api/asia_shots':   # 香港／日本／韓國大盤截圖齊唔齊＋本站／Drive 做過未
            d = (q.get('date') or [''])[0]
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', d): return s._send(400, {'error': '日期要 YYYY-MM-DD'})
            try:
                import asia
                from concurrent.futures import ThreadPoolExecutor
                out, root = [], jlaw.ls(jlaw.MROOT)
                try: sync = jlaw.get_json('/api/sync')['rows']
                except Exception: sync = []
                with ThreadPoolExecutor(3) as ex: shots = dict(zip(asia.PROFILES, ex.map(lambda k: jlaw.asia_shots(k, d, root), asia.PROFILES)))
                for k, pr in asia.PROFILES.items():
                    sh = shots[k]
                    site = any(j.get('kind') == 'amarket' and j.get('ticker') == k and j['date'] == d and j['status'] in ('done', 'queued', 'running') for j in all_jobs())
                    out.append({'mkt': k, 'name': pr['name'], 'title': pr['title'], 'folder': sh['folder'], 'path': sh['name'], 'n': len(pr['shots']),
                                'have': sorted(sh['files']), 'missing': sh['missing'], 'site': site, 'drive': jlaw.has_asia_report(pr['title'], d, sync)})
                return s._send(200, {'date': d, 'markets': out, 'checked_at': now_iso()})
            except Exception as e: return s._send(502, {'error': str(e)})
        if p == '/api/shots':
            d = (q.get('date') or [''])[0]
            try:
                if not d: d = jlaw.date_folders()[0][0]
                sh = jlaw.market_shots(d)
                return s._send(200, {'date': d, 'folder': sh['folder'], 'name': sh['name'], 'have': sorted(sh['files']), 'missing': sh['missing'], 'checked_at': now_iso()})
            except Exception as e: return s._send(502, {'error': str(e)})
        if p == '/api/watchlist': return s._send(200, {'tickers': watchlist()})
        if p == '/api/suggest':   # 今日值得出報告推介（唔用 AI）
            d = (q.get('date') or [''])[0]
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', d): return s._send(400, {'error': '日期要 YYYY-MM-DD'})
            try:
                import suggest
                return s._send(200, suggest.suggest(d))
            except Exception as e: return s._send(502, {'error': str(e)})
        if p == '/api/longbridge':   # Longbridge 連線狀態（攞 NVDA.US 報價）
            if not longbridge.enabled(): return s._send(200, {'ok': False, 'msg': '未設定 Longbridge 金鑰'})
            try: return s._send(200, {'ok': True, 'msg': longbridge.check()})
            except longbridge.LBError as e: return s._send(200, {'ok': False, 'msg': str(e)})
        if p == '/api/dates':
            try:
                md = [d for d, _ in jlaw.date_folders()[:30]]; sd, sdef = jlaw.stock_dates(md)
                return s._send(200, {'dates': md, 'default': jlaw.last_us_trading_day(), 'stock_dates': sd, 'stock_default': sdef})
            except Exception as e: return s._send(502, {'error': str(e)})
        s._send(404, {'error': 'not found'})

    def do_POST(s):
        p = urlparse(s.path).path
        if not (PW or auth.google_on()): return s._send(503, {'error': '伺服器未設定登入方式（GOOGLE_CLIENT_ID 或 GEN_PASSWORD）'})
        if not s._authed(): return s._send(401, {'error': '未登入'})
        n = int(s.headers.get('Content-Length') or 0); body = json.loads(s.rfile.read(n) or b'{}') if n else {}
        if p == '/api/auth': return s._send(200, {'ok': True})
        if p == '/api/watchlist':   # 每日清單（存喺 volume，所有裝置共用）
            ts = []
            for x in body.get('tickers') or []:
                x = str(x).strip().upper()
                if re.fullmatch(r'[A-Z0-9.]{1,10}', x) and x not in ts: ts.append(x)
            with LOCK: json.dump({'tickers': ts, 'at': now()}, open(WATCH, 'w', encoding='utf-8'), ensure_ascii=False)
            return s._send(200, {'tickers': ts})
        if p == '/api/generate':
            d = str(body.get('date', ''))
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', d): return s._send(400, {'error': '日期要 YYYY-MM-DD'})
            if dt.date.fromisoformat(d).weekday() >= 5: return s._send(400, {'error': f'{d} 係週末，唔係美股交易日'})
            eng = str(body.get('engine') or 'auto')
            if eng not in ENGINES: return s._send(400, {'error': f'唔識呢個引擎：{eng}'})
            if eng == 'gemini' and not os.environ.get('GEMINI_API_KEY'): return s._send(503, {'error': '伺服器未設定 GEMINI_API_KEY'})
            if eng == 'grok' and not os.environ.get('XAI_API_KEY'): return s._send(503, {'error': '伺服器未設定 XAI_API_KEY'})
            if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('XAI_API_KEY') or eng == 'gemini'): return s._send(503, {'error': '伺服器未設定 ANTHROPIC_API_KEY／XAI_API_KEY'})
            if body.get('kind') == 'amarket':   # 香港／日本／韓國大盤：markets＝['hk','jp','kr'] 揀幾個
                ms = [str(x) for x in body.get('markets') or [] if str(x) in ('hk', 'jp', 'kr')]
                if not ms: return s._send(400, {'error': '揀最少一個市場'})
                made = [new_job(d, upload=bool(body.get('upload')), kind='amarket', ticker=k, engine=eng) for k in ms]
                return s._send(200, {'jobs': [j_['id'] for j_, _ in made], 'created': sum(1 for _, c in made if c)})
            if body.get('kind') == 'stock':
                ts = [str(x).strip().upper() for x in body.get('tickers') or [] if re.fullmatch(r'[A-Za-z0-9.]{1,10}', str(x).strip())]
                if not ts: return s._send(400, {'error': '揀最少一隻股票'})
                made = [new_job(d, upload=bool(body.get('upload')), kind='stock', ticker=t_, engine=eng) for t_ in ts]
                return s._send(200, {'jobs': [j_['id'] for j_, _ in made], 'created': sum(1 for _, c in made if c)})
            j, created = new_job(d, upload=bool(body.get('upload')), engine=eng)
            return s._send(200, {'job': j['id'], 'created': created})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/retry', p)   # 重做：同一 kind／日期／代號開一個新 job（舊紀錄保留）
        if m:
            j = load(m.group(1))
            if not j: return s._send(404, {'error': '冇呢個 job'})
            if j['status'] in ('queued', 'running'): return s._send(400, {'error': '仲做緊／排緊隊'})
            nj, created = new_job(j['date'], upload=bool(body.get('upload', j.get('auto_upload'))), kind=j.get('kind', 'market'), ticker=j.get('ticker'),
                                  engine=str(body.get('engine') or j.get('engine_pref') or 'auto'))
            return s._send(200, {'job': nj['id'], 'created': created})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/cancel', p)
        if m:
            j = load(m.group(1))
            if not j or j['status'] not in ('queued', 'running'): return s._send(400, {'error': '呢個 job 唔係排緊隊／做緊'})
            CANCEL.add(j['id'])
            if j['status'] == 'queued': j['status'] = 'cancelled'; j['error'] = '已取消'; j['finished'] = now(); save(j)
            return s._send(200, {'ok': True, 'status': j['status']})
        if p == '/api/cancel_queued':   # 一次過取消全部排緊隊嘅（做緊嗰啲唔郁）
            n = 0
            for j in all_jobs():
                if j['status'] == 'queued':
                    CANCEL.add(j['id']); j['status'] = 'cancelled'; j['error'] = '已取消'; j['finished'] = now(); save(j); n += 1
            return s._send(200, {'cancelled': n})
        m = re.fullmatch(r'/api/jobs/([\w-]+)/upload', p)
        if m:
            j = load(m.group(1))
            if not j or not j.get('pdf'): return s._send(404, {'error': '未有 PDF'})
            try:
                r = [jlaw.upload(os.path.join(JOBS, j['id'], f)) for f in (j.get('pdfs') or [j['pdf']])]; j['uploaded'] = now(); save(j)
                return s._send(200, {'ok': True, 'result': r})
            except Exception as e: return s._send(502, {'error': str(e)})
        s._send(404, {'error': 'not found'})


def main():
    for j in all_jobs():    # 重新部署：未完成嘅 job 標失敗（唔會自動重跑，避免重複收費）
        if j['status'] in ('queued', 'running'):
            j['status'] = 'failed'; j['error'] = '伺服器重新啟動，job 中斷；請再撳一次'; save(j)
    for _ in range(max(1, int(os.environ.get('WORKERS', '2')))): threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    def lb_selftest():
        if not longbridge.enabled(): print('longbridge: 未設定金鑰', flush=True); return
        try: print('longbridge OK:', longbridge.check(), flush=True)
        except longbridge.LBError as e: print('longbridge 連唔到:', e, flush=True)
    threading.Thread(target=lb_selftest, daemon=True).start()
    import gemini
    threading.Thread(target=lambda: gemini.selftest(lambda m: print(m, flush=True)), daemon=True).start()
    port = int(os.environ.get('PORT', '8080'))
    print('listening', port, 'data', DATA, flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()


if __name__ == '__main__': main()
