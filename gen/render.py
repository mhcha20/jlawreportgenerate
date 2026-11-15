"""render.py — HTML → A4 PDF（Python Playwright；取代 Jlaw-report 嘅 node render.js，版面設定一樣）。
jobs＝[{html, pdf, footer}]。Chromium 路徑可用環境變數 CHROMIUM_PATH 指定（本地測試用），默認用 Playwright 自帶。"""
import json, os, sys
from playwright.sync_api import sync_playwright

import re
_UP, _DN = '#1a7f4b', '#c0392b'
# AI 自己寫入文字嘅「▲0.54%」「▼25.36%」之前冇顏色（只有程式計嘅數字有），用戶 2026-11-15 要求所有報告上升綠、下跌紅：
# 轉 PDF 前將未上色嘅 ▲／▼＋數字包一層顏色（已經喺 span 入面嘅唔再包；冇數字嘅 ▲▼ 說明字唔郁）
_ARROW = re.compile(r'([▲▼])(\s?\d[\d,.]*(?:%|[KMB](?![A-Za-z])| ?點|倍|R)?)')
def color_arrows(h):
    def sub(seg):
        return _ARROW.sub(lambda m: f'<span style="color:{_UP if m.group(1) == "▲" else _DN}">{m.group(1)}{m.group(2)}</span>', seg)
    # 只改標籤之間嘅文字，唔郁 <tag …> 入面同 <style>／<script>
    out, pos, colored = [], 0, False   # colored＝上一個標籤係已經上色嘅 span（class up/dn/pu/pd 或者 style color）
    for m in re.finditer(r'<style.*?</style>|<script.*?</script>|<[^>]+>', h, flags=re.S):
        seg = h[pos:m.start()]
        out.append(seg if colored and re.match(r'\s*[▲▼]', seg) else sub(seg)); out.append(m.group(0)); pos = m.end()
        colored = bool(re.match(r'<span[^>]*(class="(?:up|dn|pu|pd)"|style="[^"]*color)', m.group(0)))
    out.append(sub(h[pos:]))
    return ''.join(out)


def render(jobs):
    exe = os.environ.get('CHROMIUM_PATH') or None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=['--no-sandbox'])
        for j in jobs:
            h = open(j['html'], encoding='utf-8').read(); h2 = color_arrows(h)
            if h2 != h: open(j['html'], 'w', encoding='utf-8').write(h2)
            pg = b.new_page()
            pg.goto('file://' + os.path.abspath(j['html']), wait_until='networkidle')
            pg.evaluate('document.fonts.ready')
            footer = (f'<div style="width:100%;font-size:7.5pt;padding:0 9.8mm;text-align:center;color:#777;'
                      f"font-family:'Noto Sans TC','Noto Sans CJK TC',sans-serif\">{j['footer']} · "
                      '<span class="pageNumber"></span>／<span class="totalPages"></span></div>')
            pg.pdf(path=j['pdf'], format='A4', print_background=True, display_header_footer=True,
                   header_template='<div></div>', footer_template=footer,
                   margin={'top': '10mm', 'bottom': '13mm', 'left': '9.8mm', 'right': '10mm'})
            pg.close()
        b.close()
    print('rendered', len(jobs))

if __name__ == '__main__': render(json.load(open(sys.argv[1])))
