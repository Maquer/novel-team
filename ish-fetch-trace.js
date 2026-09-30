// 追踪所有 fetch 调用（iSH 诊断用）
const origFetch = globalThis.fetch;
let n = 0;
globalThis.fetch = async function (input, init) {
  const id = ++n;
  const url = typeof input === 'string' ? input : (input && input.url) || String(input);
  const t0 = Date.now();
  try {
    const r = await origFetch(input, init);
    if (process.env.ISH_TRACE) console.error(`[fetch#${id} +${Date.now()-t0}ms OK ${r.status}] ${url.slice(0,120)}`);
    return r;
  } catch (e) {
    console.error(`[fetch#${id} +${Date.now()-t0}ms FAIL] ${url.slice(0,120)}`);
    console.error(`  cause: ${e.cause ? (e.cause.message || e.cause.code || JSON.stringify(e.cause).slice(0,300)) : 'n/a'}`);
    if (e.cause && e.cause.cause) console.error(`  cause.cause: ${JSON.stringify(e.cause.cause).slice(0,300)}`);
    throw e;
  }
};
