"""render.py — HTML → A4 PDF（Python Playwright；取代 Jlaw-report 嘅 node render.js，版面設定一樣）。
jobs＝[{html, pdf, footer}]。Chromium 路徑可用環境變數 CHROMIUM_PATH 指定（本地測試用），默認用 Playwright 自帶。"""
import json, os, sys
from playwright.sync_api import sync_playwright

def render(jobs):
    exe = os.environ.get('CHROMIUM_PATH') or None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=['--no-sandbox'])
        for j in jobs:
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
