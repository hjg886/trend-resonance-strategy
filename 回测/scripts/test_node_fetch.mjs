const tests = [
  // 重测实时接口（间歇性检查）
  ["https://push2.eastmoney.com/api/qt/stock/get?secid=1.512880&fields=f43,f44,f45,f46,f47,f48", "realtime-retest"],
  // push2 kline 极小范围
  ["https://push2.eastmoney.com/api/qt/stock/kline/get?secid=1.512880&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&beg=20240102&end=20240110&lmt=100", "push2-kline-7rec"],
  // 腾讯分段拉取测试：3段覆盖全历史
  ["https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh512690,day,2018-01-01,2021-06-30,800,qfq", "tx-512690-2018to2021"],
  ["https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh512690,day,2021-07-01,2026-06-30,800,qfq", "tx-512690-2021to2026"],
];
(async () => {
for (const [u, name] of tests) {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 20000);
    const r = await fetch(u, { signal: ctrl.signal, headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://quote.eastmoney.com/" } });
    clearTimeout(t);
    const text = await r.text();
    console.log("[" + name + "] STATUS:", r.status, "LEN:", text.length);
    console.log("  PREVIEW:", text.slice(0, 300).replace(/\n/g, " "));
    console.log("---");
  } catch (e) {
    console.log("[" + name + "] ERROR:", e.message);
    console.log("---");
  }
}
})();
