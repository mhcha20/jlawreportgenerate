#!/usr/bin/env python3
"""prep.py — 個股報告前置：行情 → data/<TICKER>.json；截圖 → 裁切／拼接圖。
用法：
  python3 prep.py data NVDA 2026-10-21 [--extra '<JSON list>']  # 由 jlaw-report 網站 /api/ohlcv 攞日線，只取 ≤ 報告日嘅完整交易日
  python3 prep.py images NVDA <folder_with_pngs>  # 將 Futubull 截圖裁切（_c.png）同拼接表格（_t.png：標籤欄＋最近 6 季）
行情來源同網站回測一致（Yahoo Finance 日線，不復權）；成交量為綜合量（股），輸出 bars 內單位為千股。
"""
import json, os, re, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.environ.get('JLAW_SITE', 'https://jlaw-report-a74806.up.railway.app')

def data(ticker, date, extra=None):
    with urllib.request.urlopen(f'{SITE}/api/ohlcv?t={ticker}&range=2y', timeout=60) as r:
        j = json.load(r)
    rows = [x for x in j['rows'] if x['d'] <= date]
    if extra:   # 手動補充嘅日線（例如 Yahoo 未有當日 bar 時由 Longbridge 攞）：JSON list of {d,o,h,l,c,v}，v 單位股
        em = {x['d']: x for x in json.loads(extra)}; rows = sorted([x for x in rows if x['d'] not in em] + [x for x in em.values() if x['d'] <= date], key=lambda x: x['d'])
    last = rows[-1] if rows else None
    if last and last['d'] == date and not extra and re.fullmatch(r'[A-Z]{1,5}', ticker) and last.get('fa', '9') < date + 'T20:30:00Z':
        raise SystemExit(f'{ticker} {date} 嘅 bar 係盤中（fa={last.get("fa")}）未收市，唔可以用；收市後再跑')
    assert rows and rows[-1]['d'] == date, f'最後一根 K 線 {rows[-1]["d"] if rows else None} ≠ 報告日 {date}（行情未更新？）'
    assert len(rows) >= 60, f'日線只有 {len(rows)} 根'
    if len(rows) < 260: print(f'⚠ 日線只有 {len(rows)} 根（新上市／短歷史）：MA200 等長週期指標會係 NaN，要標 N/A、52 週高低改用上市以來', file=sys.stderr)
    rows = rows[-319:] if len(rows) > 319 else rows
    bars = [[x['d'][5:], round(x['o'], 4), round(x['h'], 4), round(x['l'], 4), round(x['c'], 4), round(x['v'] / 1000)] for x in rows[-135:]]
    out = {'closes': [round(x['c'], 4) for x in rows], 'bars': bars, 'symbol': j['symbol']}
    os.makedirs(f'{HERE}/data', exist_ok=True)
    json.dump(out, open(f'{HERE}/data/{ticker}.json', 'w'))
    json.dump(out, open(f'{HERE}/data/{ticker}_{date}.json', 'w'))   # 每日專屬檔，build.py 優先用
    print(f'{ticker} {j["symbol"]}: {len(rows)} 根，最後 {rows[-1]["d"]} 收 {rows[-1]["c"]} 量 {rows[-1]["v"]:,}')

def _images_magick(ticker, folder):
    """PIL 用唔到時（排程環境曾出現）改用 ImageMagick，裁切同 PIL 版一樣"""
    import glob, subprocess
    for f in sorted(glob.glob(f'{folder}/*Futubull*.png')):
        w, h = map(int, subprocess.check_output(['identify', '-format', '%w %h', f]).split())
        x0, y0, x1, y1 = int(w*0.108), int(h*0.045), int(w*0.888), int(h*0.965)
        c = f.replace('.png', '_c.png')
        subprocess.check_call(['convert', f, '-crop', f'{x1-x0}x{y1-y0}+{x0}+{y0}', '+repage', c])
        if os.path.basename(f)[:2] in ('06', '07', '08', '09'):
            cw, ch = x1 - x0, y1 - y0
            subprocess.check_call(['convert', '(', c, '-crop', f'560x{ch-150}+0+150', '+repage', ')', '(', c, '-crop', f'1330x{ch-150}+{cw-1330}+150', '+repage', ')', '+append', f.replace('.png', '_t.png')])
    print('done', ticker, '(ImageMagick)')

def images(ticker, folder):
    try:
        from PIL import Image
    except Exception as e:
        print('PIL 用唔到（' + type(e).__name__ + '），改用 ImageMagick', file=sys.stderr)
        return _images_magick(ticker, folder)
    import glob
    for f in sorted(glob.glob(f'{folder}/*Futubull*.png')):
        im = Image.open(f); w, h = im.size
        c = im.crop((int(w*0.108), int(h*0.045), int(w*0.888), int(h*0.965)))
        c.save(f.replace('.png', '_c.png'))
        base = os.path.basename(f)[:2]
        if base in ('06', '07', '08', '09'):
            cw, ch = c.size
            a = c.crop((0, 150, 560, ch)); b = c.crop((cw-1330, 150, cw, ch))
            o = Image.new('RGB', (a.width+b.width, a.height)); o.paste(a, (0, 0)); o.paste(b, (a.width, 0))
            o.save(f.replace('.png', '_t.png'))
    print('done', ticker)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'data': data(sys.argv[2], sys.argv[3], sys.argv[sys.argv.index('--extra') + 1] if '--extra' in sys.argv else None)
    elif cmd == 'images': images(sys.argv[2], sys.argv[3])
    else: print(__doc__)
