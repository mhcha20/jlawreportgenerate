"""jlaw.py — 經 jlaw-report 網站 API 攞 Drive 截圖、舊報告，同上載 PDF（唔使 Google 金鑰）。"""
import datetime as dt, io, json, os, re, urllib.parse, urllib.request

SITE = os.environ.get('JLAW_SITE', 'https://jlaw-report-a74806.up.railway.app')
MROOT = '1M8hNhlePL5MHD-_SvGZlQ02srBHFq_rl'   # 大盤截圖根資料夾（按日期分子資料夾「DD mon YYYY」）
MSHOTS = ['IWM', 'VIX', 'SPY', 'QQQ', 'SOX', 'XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLB', 'XLC', 'XLI', 'XLP', 'XLU', 'XLRE', 'DXY', 'GC1!', 'US10Y']
MONTHS = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()


def _open(url, data=None, headers=None, timeout=120, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def get_json(path, tries=2):
    last = None
    for _ in range(tries):
        try:
            with _open(SITE + path) as r: return json.load(r)
        except Exception as e: last = e
    raise last


def ls(folder): return get_json(f'/api/drive/ls?folder={folder}')['files']


def folder_name(date):
    y, m, d = date.split('-'); return f'{int(d):02d} {MONTHS[int(m) - 1]} {y}'


def date_folders():
    """大盤截圖根資料夾入面有邊啲日期（YYYY-MM-DD，新→舊）"""
    out = []
    for f in ls(MROOT):
        m = re.fullmatch(r'(\d{1,2}) ([a-z]{3}) (\d{4})', f['name'].strip().lower())
        if m and m.group(2) in MONTHS:
            out.append((f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}', f['id']))
    return sorted(out, reverse=True)


def market_shots(date):
    """回傳 {'folder','files':{ticker: {id,name,createdTime}},'missing':[…]}；冇日期資料夾 → folder=None"""
    fname = folder_name(date)
    f = [x for x in ls(MROOT) if x['name'].strip().lower() == fname]
    if not f: return {'folder': None, 'files': {}, 'missing': list(MSHOTS), 'name': fname}
    got = {}
    for x in ls(f[0]['id']):
        m = re.match(r'(\d\d)_(.+)_Daily\.png$', x['name'], re.I)
        if m: got[m.group(2).upper()] = x
    return {'folder': f[0]['id'], 'name': fname, 'files': got, 'missing': [t for t in MSHOTS if t not in got]}


def download(file_id):
    with _open(f'https://drive.google.com/uc?export=download&id={file_id}', timeout=180) as r: return r.read()


def prev_market_report(date):
    """Drive 入面最近一份（早過 date）大盤報告：(名, 文字)；冇就 (None, '')"""
    rows = [r for r in get_json('/api/sync')['rows'] if r[0] == 'market' and re.match(r'\d{4}-\d\d-\d\d', r[2]) and r[2][:10] < date]
    if not rows: return None, ''
    r = sorted(rows, key=lambda r: (r[2][:10], r[3]), reverse=True)[0]
    with _open(f'{SITE}/pdf/{r[1]}', timeout=180) as f: return r[2], _pdf_text(f.read())


def _pdf_text(data):
    """PDF → 文字：優先 pdftotext -layout（保留表格版面），冇 poppler 先用 pypdf"""
    import subprocess
    try:
        p = subprocess.run(['pdftotext', '-layout', '-', '-'], input=data, capture_output=True, timeout=120)
        if p.returncode == 0 and p.stdout.strip(): return p.stdout.decode('utf-8', 'replace')
    except Exception: pass
    from pypdf import PdfReader
    return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(data)).pages)


def report_by_name(prefix):
    """Drive 入面檔名以 prefix 開頭嘅最新一份報告：(名, 文字)；冇就 (None, '')"""
    rows = [r for r in get_json('/api/sync')['rows'] if r[2].startswith(prefix)]
    if not rows: return None, ''
    r = sorted(rows, key=lambda r: r[3], reverse=True)[0]
    with _open(f'{SITE}/pdf/{r[1]}', timeout=180) as f: return r[2], _pdf_text(f.read())


def jlaw_materials(date, max_n=3, max_age=10):
    """J Law 觀點私人資料夾：發布日期（檔名 YYYY-MM-DD）≤ date、10 日內，最新 max_n 份 → [(名, 文字)]。要 JLAW_ADMIN_PASSWORD"""
    pw = os.environ.get('JLAW_ADMIN_PASSWORD', '')
    if not pw: return None
    h = {'x-admin-password': pw}
    with _open(f'{SITE}/api/upload?op=jlaw-list', data=b'', headers=h, method='POST') as r: files = json.load(r)['files']
    lo = (dt.date.fromisoformat(date) - dt.timedelta(days=max_age)).isoformat()
    pick = sorted([f for f in files if re.match(r'\d{4}-\d\d-\d\d', f['name']) and lo <= f['name'][:10] <= date], key=lambda f: f['name'], reverse=True)[:max_n]
    out = []
    for f in pick:
        with _open(f'{SITE}/api/upload?op=jlaw-get&id={f["id"]}', data=b'', headers=h, method='POST', timeout=300) as r:
            data = r.read()
        out.append((f['name'], _pdf_text(data) if data[:4] == b'%PDF' else data.decode('utf-8', 'replace')))
    return out


def has_report(date):
    """Drive 已經有 date 嘅大盤報告？"""
    try: return any(r[0] == 'market' and r[2].startswith(date) for r in get_json('/api/sync')['rows'])
    except Exception: return False


def upload(pdf_path):
    pw = os.environ.get('JLAW_ADMIN_PASSWORD', '')
    if not pw: raise RuntimeError('未設定 JLAW_ADMIN_PASSWORD（jlaw-report 網站嘅 ADMIN_PASSWORD），上載唔到')
    name = os.path.basename(pdf_path)
    with _open(f'{SITE}/api/upload?name={urllib.parse.quote(name)}&cat=auto&replace=1', data=open(pdf_path, 'rb').read(),
               headers={'Content-Type': 'application/pdf', 'x-admin-password': pw}, timeout=300, method='POST') as r:
        return json.load(r)


def last_us_trading_day(now=None):
    """香港而家計，最近一個已收市嘅美股交易日（唔計美國假期；假期冇截圖資料夾，排程會自動跳過）"""
    from zoneinfo import ZoneInfo
    ny = (now or dt.datetime.now(ZoneInfo('America/New_York')))
    d = ny.date() if ny.hour >= 17 else ny.date() - dt.timedelta(days=1)
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d.isoformat()


# ---------------------------------------------------------------- 個股
SROOT = '1xkPBlGhK0SEn2dGIzAINQNIFL33m0hG_'   # 個股截圖根資料夾：<代號>/<DD mon YYYY>/NN_*.png
# 外國股／ADR（字母代號但唔係美國公司）：冇美國內部人申報 → 第 15 張（內部人）可缺（用戶 2026-11-05 指出）
ADR = {x.strip().upper() for x in os.environ.get('ADR_TICKERS', 'SCHN,NESN,MC,ATD').split(',') if x.strip()}


_THEMES = {'at': 0, 'map': {}}


def _csv_rows(text):
    import csv
    return list(csv.reader(io.StringIO(text)))


def themes():
    """股票清單 Google Sheet（第一個分頁「個股 research list」）：A 欄 Focus Theme＝行業／主題、B 欄名、C 欄代號 → {代號: (主題, 名)}。
    經 jlaw-report /api/sheet（要 JLAW_ADMIN_PASSWORD，報告中心要已連接 Google）；1 小時快取；讀唔到就回傳上次結果（或空）。"""
    import time
    if _THEMES['map'] and time.time() - _THEMES['at'] < 3600: return _THEMES['map']
    pw = os.environ.get('JLAW_ADMIN_PASSWORD', '')
    if not pw: return _THEMES['map']
    try:
        with _open(SITE + '/api/sheet', headers={'x-admin-password': pw}, timeout=60) as r: csv_text = json.load(r)['csv']
        out = {}
        for row in _csv_rows(csv_text)[1:]:
            if len(row) < 3: continue
            th, name, t = row[0].strip(), row[1].strip(), row[2].strip().upper()
            if not t or not th or t in ('TICKER SYMBOL',) or '大盤' in t: continue
            th = re.sub(r'\s*[（(]\s*續\s*[）)]\s*$', '', th)            # 「AI基建 (續)」併入「AI基建」
            if t.isdigit(): t = t.zfill(5) if len(t) <= 5 else t           # 港股 66 → 00066（同截圖資料夾一致）
            out.setdefault(t, (th, name))
        _THEMES.update(at=time.time(), map=out)
    except Exception as e:
        print('themes', e, flush=True); _THEMES['at'] = time.time() - 3000   # 失敗 10 分鐘後再試
    return _THEMES['map']


def stock_list(date):
    """jlaw-report 截圖檢查：當日每隻股票截圖齊唔齊 → [{ticker,status,…}]"""
    rows = get_json(f'/api/shots?date={date}')['stocks']['rows']
    for r in rows:   # ADR：jlaw-report 截圖檢查當美股要 01–17，呢度只缺 15 都當齊
        if r.get('ticker') in ADR and r.get('status') == 'incomplete' and set(r.get('missing') or []) <= {15} and not r.get('extra'):
            r['status'] = 'ok'; r['kind'] = 'ADR'
    return rows


def stock_shots(ticker, date):
    """個股截圖：{'folder','files':[{id,name,createdTime}],'kind':'US|ETF|ASIA','missing':[編號],'ok':bool}。規則同 Jlaw-report drive.py：
    美股要啱啱 01–17（ADR 清單內嘅外國股 15 內部人可缺）；檔名有 Fund_ 當 ETF，要啱啱 01–12；全數字代號當亞洲，01–14 齊就得（15–17 可缺）。"""
    tf = [x for x in ls(SROOT) if x['name'].strip() == ticker]
    if not tf: return {'folder': None, 'files': [], 'kind': None, 'missing': [], 'ok': False, 'why': f'Drive 冇 {ticker} 截圖資料夾'}
    fname = folder_name(date)
    df = [x for x in ls(tf[0]['id']) if x['name'].strip().lower() == fname]
    if not df: return {'folder': None, 'files': [], 'kind': None, 'missing': [], 'ok': False, 'why': f'{ticker} 未有「{fname}」截圖資料夾'}
    fs = sorted([x for x in ls(df[0]['id']) if x['name'].lower().endswith('.png')], key=lambda x: x['name'])
    nums = sorted(int(x['name'][:2]) for x in fs if re.match(r'\d\d_', x['name']))
    etf = any('Fund_' in x['name'] for x in fs); asia = ticker.isdigit(); adr = ticker in ADR and not etf and not asia
    need = list(range(1, 13)) if etf else list(range(1, 15)) if asia else [n for n in range(1, 18) if n != 15] if adr else list(range(1, 18))
    ok = all(n in nums for n in need) and all(n <= 17 for n in nums) if (adr or (asia and not etf)) else nums == need
    return {'folder': df[0]['id'], 'files': fs, 'kind': 'ETF' if etf else 'ASIA' if asia else 'ADR' if adr else 'US', 'missing': sorted(set(need) - set(nums)), 'ok': ok,
            'why': '' if ok else f'{ticker} 截圖未齊：有 {len(fs)} 張，缺 {sorted(set(need) - set(nums))}' + ('（多出／編號唔啱）' if not (set(need) - set(nums)) else '')}


def prior_stock(ticker, date):
    """同股票最近一份（早過 date）報告：{'card':(名,文字),'rep':(名,文字)}；檔名 YYYY-MM-DD_TICKER_類型"""
    rows = [r for r in get_json('/api/sync')['rows'] if re.match(rf'^\d{{4}}-\d\d-\d\d_{re.escape(ticker)}_', r[2]) and r[2][:10] < date]
    out = {}
    for key, pat in (('card', '行動卡'), ('rep', '股票分析終極報告')):
        rr = sorted([r for r in rows if pat in r[2]], key=lambda r: (r[2][:10], r[3]), reverse=True)
        if rr:
            with _open(f'{SITE}/pdf/{rr[0][1]}', timeout=180) as f: out[key] = (rr[0][2], _pdf_text(f.read()))
    return out


def market_report_for(date):
    """美股個股要承襲當日大盤報告：優先 date 當日（Claude核實版＞Grok核實版＞其他），冇就最近一份。→ (名, 文字, 係咪當日)"""
    rows = [r for r in get_json('/api/sync')['rows'] if r[0] == 'market' and re.match(r'\d{4}-\d\d-\d\d', r[2]) and r[2][:10] <= date]
    if not rows: return None, '', False
    rank = lambda r: (r[2][:10], 2 if 'Claude核實版' in r[2] else 1 if '核實版' in r[2] else 0, r[3])
    r = sorted(rows, key=rank, reverse=True)[0]
    with _open(f'{SITE}/pdf/{r[1]}', timeout=180) as f: return r[2], _pdf_text(f.read()), r[2][:10] == date
