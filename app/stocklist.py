"""stocklist.py — 網站加／移除截圖股票（用戶 2026-11-12 要求：唔使搵 Claude，網站撳掣就得；美股＋港日韓）。

流程：用戶打代號 → lookup() 查 Yahoo（正式公司名、交易所、股票定 ETF、有冇報價）＋對現有清單 →
網頁列表俾用戶核對（用戶 2026-11-11 規定：加股票前一定要核對公司名再確認）→ 確認後經 capture 排
add_stock 動作，Mac 上 screencapture bin/stock_registry.py 開 Drive 資料夾同記低設定。
validate_item() 同 Mac 嗰邊 stock_registry.validate() 用同一套規則，兩邊都驗。"""
import json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {'User-Agent': 'Mozilla/5.0 (jlawreportgenerate stock lookup)'}
US_EXCH = {'NYQ': 'NYSE', 'NYSE': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ', 'NASDAQ': 'NASDAQ',
           'PCX': 'AMEX', 'ASE': 'AMEX', 'BTS': 'AMEX', 'NYSEARCA': 'AMEX', 'NYSE ARCA': 'AMEX', 'NYSEAMERICAN': 'AMEX',
           'NYSE AMERICAN': 'AMEX', 'CBOE': 'AMEX', 'CBOE US': 'AMEX'}
MKT_NAME = {'us': '美股', 'hk': '港股', 'jp': '日股', 'kr': '韓股'}
SUFFIX = {'hk': '.HK', 'jp': '.T', 'kr': '.KS'}
NAME_RE = re.compile(r"[A-Za-z0-9 &.,'()\-]{2,40}")
DROP = {'inc', 'inc.', 'corp', 'corp.', 'corporation', 'co', 'co.', 'company', 'ltd', 'ltd.', 'limited', 'plc', 'holdings',
        'holding', 'group', 'sa', 's.a.', 'ag', 'nv', 'n.v.', 'incorporated', 'the', 'class', 'etf', 'trust', 'fund', 'shares'}


def _get(url, timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def _quote(sym):
    """Yahoo：(名, 交易所碼, 類型, 現價, 貨幣)；查唔到回傳 None"""
    try:
        meta = _get(f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5d&interval=1d')['chart']['result'][0]['meta']
    except Exception:
        return None
    price = meta.get('regularMarketPrice')
    if price is None: return None   # VSCO 教訓：舊代號冇報價
    name, qtype, exch = meta.get('longName') or meta.get('shortName'), meta.get('instrumentType'), meta.get('exchangeName')
    try:   # 搜尋 API 嘅名通常齊啲（chart 間中冇 longName）
        for q in _get(f'https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(sym)}&quotesCount=5&newsCount=0').get('quotes', []):
            if q.get('symbol') == sym:
                name = q.get('longname') or q.get('shortname') or name
                qtype = q.get('quoteType') or qtype; exch = q.get('exchDisp') or exch
                break
    except Exception: pass
    return dict(name=name or sym, exch=str(exch or ''), type=str(qtype or ''), price=price, ccy=meta.get('currency', ''))


def check_word(name):
    """富途核對字眼：正式名去咗 Inc／Co／Ltd 等，取頭一兩個字"""
    words = [w for w in re.split(r'\s+', re.sub(r"[^A-Za-z0-9 &.'\-]", ' ', name or '')) if w]
    keep = []
    for w in words:
        if w.lower().strip(',') in DROP: break
        keep.append(w.strip(','))
        if len(keep) == 2: break
    while keep and keep[-1] in ('&', '-'): keep.pop()
    word = ' '.join(keep)[:40]
    return word if NAME_RE.fullmatch(word or '') else ''


def candidates(token):
    """用戶打嘅一個代號 → [(market, 資料夾名, Yahoo 代號, TradingView 代號)]"""
    t = token.strip().upper()
    m = re.fullmatch(r'(\d{1,6})\.(HK|T|KS|KQ)', t)
    if m:
        code, suf = m.groups()
        if suf == 'HK': return [('hk', code.zfill(5), f'{int(code):04d}.HK', f'HKEX:{int(code)}')]
        if suf == 'T' and len(code) == 4: return [('jp', code, f'{code}.T', f'TSE:{code}')]
        if suf in ('KS', 'KQ') and len(code) == 6: return [('kr', code, f'{code}.{suf}', f'KRX:{code}')]
        return []
    if re.fullmatch(r'\d{1,6}', t):
        if len(t) == 6: return [('kr', t, f'{t}.KS', f'KRX:{t}'), ('kr', t, f'{t}.KQ', f'KRX:{t}')]
        if len(t) == 4 and t[0] != '0':   # 4 位：可能係日股（7974）亦可能係港股（1299 友邦），兩樣都查
            return [('jp', t, f'{t}.T', f'TSE:{t}'), ('hk', t.zfill(5), f'{t}.HK', f'HKEX:{int(t)}')]
        if len(t) <= 5 and int(t) > 0: return [('hk', t.zfill(5), f'{int(t):04d}.HK', f'HKEX:{int(t)}')]
        return []
    if re.fullmatch(r'[A-Z][A-Z0-9]{0,5}([.-][A-Z])?', t):
        return [('us', t.replace('-', '.'), t.replace('.', '-'), None)]
    return []


def _row(token, cand, existing):
    market, folder, ysym, tv = cand
    q = _quote(ysym)
    if not q: return None
    row = dict(input=token, ticker=folder, market=market, market_name=MKT_NAME[market], yahoo=ysym, name=q['name'],
               exch=q['exch'], etf=q['type'].upper() == 'ETF', price=q['price'], ccy=q['ccy'], check=check_word(q['name']), status='new', note='')
    if market == 'us':
        ex = US_EXCH.get(q['exch'].upper().replace('-', ' ')) or US_EXCH.get(q['exch'].upper().replace(' ', ''))
        if not ex:
            row.update(status='unsupported', note=f'交易所 {q["exch"] or "?"} 唔支援（場外／外國交易所要搵 Claude 設定）')
        row['exchange'] = ex or q['exch']
    else:
        row['tv'] = tv; row['exchange'] = tv.split(':')[0]
        if market == 'kr' and ysym.endswith('.KQ'): row['note'] = 'KOSDAQ 上市（TradingView 用 KRX）'
    if folder in existing: row.update(status='exists', note='已經喺截圖清單')
    if not row['check'] and row['status'] == 'new': row['note'] = '自動估唔到核對字眼，請自己填英文公司名'
    return row


def lookup(text, existing):
    tokens = [t for t in re.split(r'[\s,，、]+', text or '') if t][:20]
    jobs = [(tok, c) for tok in tokens for c in candidates(tok)]
    with ThreadPoolExecutor(8) as ex:
        found = list(ex.map(lambda a: _row(a[0], a[1], existing), jobs))
    rows, seen = [], set()
    for (tok, c), r in zip(jobs, found):
        if r and (r['market'], r['ticker']) not in seen:
            seen.add((r['market'], r['ticker'])); rows.append(r)
    hit = {r['input'] for r in rows}
    for tok in tokens:
        if tok not in hit:
            rows.append(dict(input=tok, ticker=tok.upper(), status='notfound', note='Yahoo 查唔到，或者代號格式唔啱（港股可打 700 或 0700.HK、日股 7974、韓股 000660）'))
    return rows


def validate_item(it):
    """網頁傳嚟要加嘅一隻（同 Mac stock_registry.validate 一樣規則）"""
    if not isinstance(it, dict): raise ValueError('格式唔啱')
    market, t = it.get('market'), str(it.get('ticker', '')).upper()
    pat = {'us': r'[A-Z][A-Z0-9.]{0,9}', 'hk': r'\d{5}', 'jp': r'\d{4}', 'kr': r'\d{6}'}.get(market)
    if not pat or not re.fullmatch(pat, t): raise ValueError(f'代號唔啱：{t}')
    names = [str(n).strip() for n in (it.get('names') or []) if str(n).strip()][:3]
    if not names or not all(NAME_RE.fullmatch(n) for n in names): raise ValueError(f'{t}：核對字眼要 2–40 個英文字母／數字')
    out = dict(ticker=t, market=market, names=names, etf=bool(it.get('etf')))
    if market == 'us':
        ex = str(it.get('exchange', '')).upper()
        if ex not in ('NYSE', 'NASDAQ', 'AMEX'): raise ValueError(f'{t}：交易所 {ex} 唔支援')
        out['exchange'] = ex
    else:
        tv = str(it.get('tv', '')).upper()
        want = {'hk': 'HKEX', 'jp': 'TSE', 'kr': 'KRX'}[market]
        if not re.fullmatch(rf'{want}:\d{{1,6}}', tv): raise ValueError(f'{t}：TradingView 代號唔啱')
        out['tv'] = tv
    return out
