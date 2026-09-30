// AgentRouter 每日签到 - Cloudflare Worker
// 从 773075692/agentrouter-checkin (Python) 改写
// 原理: 账号密码登录 = 每日签到; 登录成功后查 /api/log/self 核验 type=4 日志

const BASE_URL = (env.BASE_URL || "https://agentrouter.org").replace(/\/$/, "");
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36";
const CHECKIN_LOG_TYPE = 4;

// ============ 账号解析 ============
function parseAccounts(env) {
  const accounts = [];
  // 多账号: & 分隔 (每个是 "name|email|password", 若 name 空则只 email|password)
  if (env.AGENTROUTER_ACCOUNTS) {
    for (const raw of env.AGENTROUTER_ACCOUNTS.split("&")) {
      const parts = raw.trim().split("|");
      if (parts.length === 3 && parts[0] && parts[1] && parts[2]) {
        accounts.push({ name: parts[0], email: parts[1], password: parts[2] });
      } else if (parts.length === 2 && parts[0] && parts[1]) {
        accounts.push({ name: "账号" + (accounts.length + 1), email: parts[0], password: parts[1] });
      }
    }
    if (accounts.length) return accounts;
  }
  // 单账号: 邮箱#密码
  if (env.AGENTROUTER_ACCOUNT) {
    const idx = env.AGENTROUTER_ACCOUNT.indexOf("#");
    if (idx > 0) {
      accounts.push({
        name: "默认账号",
        email: env.AGENTROUTER_ACCOUNT.slice(0, idx).trim(),
        password: env.AGENTROUTER_ACCOUNT.slice(idx + 1).trim(),
      });
    }
  }
  return accounts;
}

// ============ 登录 + 签到 ============
async function loginAndCheckin(email, password) {
  const headers = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Referer": `${BASE_URL}/login`,
    "Origin": BASE_URL,
  };
  const r = await fetch(`${BASE_URL}/api/user/login`, {
    method: "POST",
    headers,
    body: JSON.stringify({ username: email, password }),
  });

  const ct = r.headers.get("content-type") || "";
  const text = await r.text();

  // WAF 拦截特征: 返回 HTML
  if (ct.includes("text/html")) {
    return { status: "fail", message: "登录接口返回 HTML (WAF 拦截或路径变化)" };
  }

  let j;
  try { j = JSON.parse(text); }
  catch (e) { return { status: "fail", message: `登录响应非 JSON: ${text.slice(0, 120)}` }; }

  if (!j.success) {
    return { status: "fail", message: `登录失败: ${j.message || text.slice(0, 120)}` };
  }

  const data = j.data || {};
  const checkedIn = !!data.checked_in;
  const username = data.username || data.display_name || email;
  const quota = data.quota ?? data.remainder_quota ?? data.balance ?? null;
  const uid = data.id;

  if (checkedIn) {
    const v = await verifyCheckin(uid);
    if (v.level === "new") return { status: "success", message: `签到成功，日志已确认 (${v.detail})`, username, quota };
    if (v.level === "today") return { status: "success", message: `登录成功且服务端返回已签到，近 1 天内有日志: ${v.detail}`, username, quota };
    return { status: "success", message: `登录成功且服务端返回已签到，但日志未确认: ${v.detail}`, username, quota };
  }
  return { status: "success", message: "登录成功，但 checked_in=false (可能今日额度已发或接口变化)", username, quota };
}

// ============ 日志核验 ============
async function verifyCheckin(uid) {
  if (!uid) return { level: "error", detail: "缺少 uid" };
  try {
    const r = await fetch(`${BASE_URL}/api/log/self/?p=1&page_size=20`, {
      headers: { "New-API-User": String(uid), "User-Agent": UA },
    });
    if (r.status !== 200) return { level: "error", detail: `日志接口 HTTP ${r.status}` };
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("text/html")) return { level: "error", detail: "日志接口返回 HTML" };
    const items = ((await r.json()).data || {}).items || [];
    const now = Math.floor(Date.now() / 1000);
    let newestTs = null, newestContent = "";
    for (const it of items) {
      const content = it.content || "";
      if (content.includes("签到成功") || it.type === CHECKIN_LOG_TYPE) {
        const ts = it.created_at;
        if (typeof ts === "number" && (newestTs === null || ts > newestTs)) {
          newestTs = ts; newestContent = content;
        }
      }
    }
    if (newestTs === null) return { level: "none", detail: "日志中未找到任何签到记录" };
    const ago = now - newestTs;
    const agoStr = ago < 60 ? `${ago} 秒前`
                : ago < 3600 ? `${Math.floor(ago / 60)} 分钟前`
                : ago < 86400 ? `${Math.floor(ago / 3600)} 小时前`
                : `${Math.floor(ago / 86400)} 天前`;
    if (newestTs >= now - 300) return { level: "new", detail: `本次运行已生成签到日志 (${agoStr})` };
    if (newestTs >= now - 86400) return { level: "today", detail: `近 1 天内有签到记录 (${agoStr})` };
    return { level: "none", detail: `最近一条签到日志较旧 (${agoStr})` };
  } catch (e) {
    return { level: "error", detail: `日志查询异常: ${e.message || e}` };
  }
}

// ============ 主入口 ============
async function run(env) {
  const accounts = parseAccounts(env);
  const results = [];
  if (accounts.length === 0) {
    return [{ status: "fail", name: "—", message: "未配置账号：请设置 AGENTROUTER_ACCOUNT 或 AGENTROUTER_ACCOUNTS", time: new Date().toISOString() }];
  }
  for (const a of accounts) {
    try {
      const res = await loginAndCheckin(a.email, a.password);
      res.name = a.name;
      res.time = new Date().toISOString();
      results.push(res);
    } catch (e) {
      results.push({ status: "fail", name: a.name, message: `异常: ${e.message || e}`, time: new Date().toISOString() });
    }
    if (accounts.length > 1) await new Promise(r => setTimeout(r, 2000));
  }
  return results;
}

function buildResponse(results) {
  const lines = results.map(r => {
    const tag = { success: "✅", already: "🟡", fail: "❌" }[r.status] || "❓";
    const quotaStr = r.quota !== undefined && r.quota !== null ? `${r.quota}` : "未知";
    const who = r.username || r.name;
    return `${tag} ${r.name}(${who})：${r.message} | 额度 ${quotaStr} | ${r.time}`;
  });
  const allFail = results.every(r => r.status === "fail");
  return new Response(
    `# AgentRouter 签到汇总\n\n${lines.join("\n")}`,
    {
      status: allFail ? 500 : 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    }
  );
}

export default {
  async fetch(request, env) {
    if (!request.url.endsWith("/run")) {
      return new Response("POST /run 触发签到 | 或等定时触发。当前时间: " + new Date().toISOString(), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    return buildResponse(await run(env));
  },

  async scheduled(event, env) {
    const results = await run(env);
    if (env.WEAK_ALERT_URL) {
      try { await fetch(env.WEAK_ALERT_URL, { method: "POST", body: JSON.stringify(results) }); }
      catch (e) { console.error("alert fail:", e); }
    }
  },
};
