"""sqa.py — 個股 work 檔嘅 QA 登記（網站版）：work 檔 qa(m, S, T) 入面用 chk()／chk_true() 重算寫死嘅數字。build.py 要求 ≥20 項全過。"""
QA = []
def chk(name, actual, expected, tol=0.00501):
    ok = abs(actual - expected) <= tol
    QA.append((name, ok, actual, expected)); return ok
def chk_true(name, cond, detail=''):
    QA.append((name, bool(cond), detail, True)); return bool(cond)
def qa_report():
    bad = [q for q in QA if not q[1]]
    for q in bad: print('QA 失敗：', q)
    print(f'QA：共 {len(QA)} 項，失敗 {len(bad)} 項')
    return len(QA), len(bad)
