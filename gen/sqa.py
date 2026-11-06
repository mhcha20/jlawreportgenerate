"""sqa.py — 個股 work 檔嘅 QA 登記（網站版）：work 檔 qa(m, S, T) 入面用 chk()／chk_true() 重算寫死嘅數字。build.py 要求 ≥20 項全過。"""
QA = []
def chk(name, actual, expected, tol=0.00501):
    ok = abs(actual - expected) <= tol
    QA.append((name, ok, actual, expected, tol)); return ok
def chk_true(name, cond, detail=''):
    QA.append((name, bool(cond), detail, True)); return bool(cond)
def qa_report():
    bad = [q for q in QA if not q[1]]
    for q in bad:
        if len(q) == 5:   # chk：重算值 vs 寫死值
            print(f'QA 失敗：{q[0]}：重算 {q[2]!r} vs 寫死 {q[3]!r}（差 {abs(q[2] - q[3]):.4g}，容差 {q[4]}）。'
                  '先睇邊個啱：通常改 spec／texts 用 m 取值（f-string），唔好改重算；'
                  '如果只係顯示時四捨五入（例如 1 位小數），chk 要傳返同精度嘅容差，例如 tol=0.05')
        else: print(f'QA 失敗：{q[0]}：條件唔成立（{q[2]}）')
    print(f'QA：共 {len(QA)} 項，失敗 {len(bad)} 項')
    return len(QA), len(bad)
