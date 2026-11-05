"""format_stock.py — 個股報告硬性格式擋位（STOCK_STRICT=1）。範本未定之前只檢查頁數；用戶 send 範本後按範本補齊門檻。"""
import os
def check(S, T, pages):
    err = []
    lo = int(os.environ.get('STOCK_MIN_REPORT_PAGES', '7'))
    if pages.get('rep', 99) < lo: err.append(f'本體報告只有 {pages.get("rep")} 頁（要 ≥{lo} 頁，照範本每節寫足）')
    return err
