// iSH 兼容补丁：undici 7.x 的 native llhttp 绑定在 iSH 上不可用
// 把 wrangler 里所有 undici 的 fetch/FormData/File 重定向到 Node 22 全局实现
const Module = require('module');
const origLoad = Module._load;

function patchUndici(exp) {
  if (!exp || exp.__ish_patched) return;
  exp.__ish_patched = true;
  const redirect = (prop) => {
    if (prop in exp && typeof globalThis[prop] === 'function') {
      try {
        Object.defineProperty(exp, prop, {
          value: globalThis[prop], writable: true, configurable: true, enumerable: true
        });
      } catch (e) { /* 某些版本属性不可重定义，忽略 */ }
    }
  };
  redirect('fetch');
  redirect('FormData');
  redirect('File');
  redirect('Request');
  redirect('Response');
  redirect('Headers');
  redirect('Blob');
}

Module._load = function (request, parent, isMain) {
  const exp = origLoad.apply(this, arguments);
  if (request === 'undici' || String(request).includes('undici')) patchUndici(exp);
  return exp;
};

// 诊断模式
process.env.ISH_DEBUG_PATCH && console.error('[ish-patch] loaded');
const _origPatch = patchUndici;
patchUndici = function (exp) {
  if (process.env.ISH_DEBUG_PATCH) console.error('[ish-patch] patching:', exp && exp.__ish_patched ? 'already' : 'new');
  return _origPatch(exp);
};
if (process.env.ISH_DEBUG_PATCH) console.error('[ish-patch] active');
