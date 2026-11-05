// 用 Jlaw-report 網站同一個 signals.js（parseCard／classify）解析行動卡 PDF，輸出 JSON：node sigcheck.js card.pdf
// signals.js 由 mhcha20/Jlaw-report 原封不動複製；網站改解析規則時要同步更新。
const s = require('./signals.js'), fs = require('fs');
(async () => {
  const raw = await s.pdfText(fs.readFileSync(process.argv[2]));
  const c = s.parseCard(raw, '');
  console.log(JSON.stringify({date: c.date, gen: c.gen || '', ticker: c.titleTicker, stars: c.stars, rating: c.rating, score: c.score,
    flat: c.flat, held: c.held, close: c.close, levels: c.levels, alerts: c.alerts.length, cls: s.classify(c)}));
})().catch(e => { console.error(e.message); process.exit(2); });
