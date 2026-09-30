// Cloudflare Worker: daily-cron v2
// 升级要点（vs v1）:
//   1. 写端点 AUTH_TOKEN 认证（/set /delete /sync 必须带 Authorization header）
//   2. last_run 记录到 KV（/status 可查历史）
//   3. KV 读取失败不再静默 fallback DEFAULT_TASKS，而是告警
//   4. /dryrun 端点（只构建 Bark URL 不真发）
//   5. /health 端点（version + task_count + last_run）
//   6. /sync 端点（接收完整任务列表，幂等覆盖 KV，带认证）
//
// 部署:
//   Cloudflare Dashboard → Workers & Pages → Create Worker（或覆盖现有 daily-cron）
//   KV Namespace: TASKS（需在 Dashboard 创建并绑定）
//   Secrets: BARK_KEY, AUTH_TOKEN
//   Trigger: Cron */30 * * * * (UTC 每 30 分钟)
//
// 任务格式（每条 = 一条 Bark 推送）:
//   { tag: "TASK:pulse", body: "轻量训练脉冲",
//     params: { isArchive: 1, group: "cron", level: "timeSensitive",
//               copy: "bash /var/minis/shared/second-brain-pulse.sh",
//               url: "minis://open_terminal" } }

const VERSION = "2.0.0";

// KV 为空时使用的兜底任务（仅 1 条通用唤醒，不是生产配置）
const DEFAULT_TASKS = [
  {
    tag: "TASK:daily-cron",
    body: "定时唤醒 · 跑 countdown-scheduler check --catchup",
    params: {
      isArchive: 1,
      group: "cloudflare-cron",
      level: "timeSensitive",
      copy: "python3 /var/minis/shared/countdown-scheduler.py check --catchup",
      url: "minis://open_terminal"
    }
  }
];

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runAllTasks(env));
  },

  async fetch(request, env) {
    const url = new URL(request.url);

    // --- 公开端点（无需认证） ---

    // GET /health — 版本 + 任务数 + 最后运行
    if (url.pathname === "/health") {
      const tasks = await getTasks(env);
      const lastRun = await env.TASKS.get("last_run");
      return json({
        version: VERSION,
        task_count: tasks.length,
        last_run: lastRun ? JSON.parse(lastRun) : null,
        bark_key_set: !!env.BARK_KEY,
        auth_token_set: !!env.AUTH_TOKEN
      });
    }

    // GET /tasks — 查看当前任务列表
    if (url.pathname === "/tasks") {
      const tasks = await getTasks(env);
      return json({ tasks, source: tasks === DEFAULT_TASKS ? "default" : "kv" });
    }

    // GET /dryrun — 构建 Bark URL 但不真发
    if (url.pathname === "/dryrun") {
      const tasks = await getTasks(env);
      const urls = tasks.map(t => buildBarkUrl(env, t));
      return json({ count: urls.length, urls });
    }

    // GET /test — 手动触发所有任务（真发 Bark）
    if (url.pathname === "/test") {
      const result = await runAllTasks(env);
      return json({ triggered: result });
    }

    // --- 认证端点 ---

    // POST /sync — 接收完整任务列表，幂等覆盖 KV
    if (url.pathname === "/sync" && request.method === "POST") {
      const authErr = checkAuth(request, env);
      if (authErr) return authErr;

      let body;
      try { body = await request.json(); } catch { return json({ error: "Invalid JSON" }, 400); }
      const tasks = body.tasks || [];
      const errs = validateTasks(tasks);
      if (errs.length) return json({ error: "Validation failed", details: errs }, 400);

      await env.TASKS.put("tasks", JSON.stringify(tasks));
      return json({ ok: true, count: tasks.length, synced_at: new Date().toISOString() });
    }

    // POST /set — 别名 /sync（兼容 v1 调用方）
    if (url.pathname === "/set" && request.method === "POST") {
      const authErr = checkAuth(request, env);
      if (authErr) return authErr;

      let body;
      try { body = await request.json(); } catch { return json({ error: "Invalid JSON" }, 400); }
      const tasks = body.tasks || [];
      const errs = validateTasks(tasks);
      if (errs.length) return json({ error: "Validation failed", details: errs }, 400);

      await env.TASKS.put("tasks", JSON.stringify(tasks));
      return json({ ok: true, count: tasks.length });
    }

    // POST /delete — 删除 KV tasks（回退到 DEFAULT_TASKS）
    if (url.pathname === "/delete" && request.method === "POST") {
      const authErr = checkAuth(request, env);
      if (authErr) return authErr;

      await env.TASKS.delete("tasks");
      return json({ ok: true, message: "Tasks deleted, will use default" });
    }

    // ═══════════════════════════════════════════════════════
    // 提醒审批端点（公开，无需认证 — 由 Bark URL 触发）
    // ═══════════════════════════════════════════════════════

    // GET /remind/approve?rem_id=REM-XXXX
    //   Bark 通知里"批"按钮的 URL → 用户点一下 → Worker 记录审批
    if (url.pathname === "/remind/approve") {
      const remId = url.searchParams.get("rem_id");
      if (!remId) return json({ error: "missing rem_id" }, 400);
      const result = await approveRemind(env, remId);
      return json(result);
    }

    // GET /remind/reject?rem_id=REM-XXXX&reason=...
    if (url.pathname === "/remind/reject") {
      const remId = url.searchParams.get("rem_id");
      if (!remId) return json({ error: "missing rem_id" }, 400);
      const reason = url.searchParams.get("reason") || "未提供理由";
      const result = await rejectRemind(env, remId, reason);
      return json(result);
    }

    // GET /remind/decisions — 拉取待处理的审批决定（供 remind-action.py 同步）
    if (url.pathname === "/remind/decisions") {
      const decisions = await getRemindDecisions(env);
      return json({ decisions, count: decisions.length });
    }

    // POST /remind/delete-decisions — 清空已处理的决定
    if (url.pathname === "/remind/delete-decisions" && request.method === "POST") {
      if (env.TASKS) await env.TASKS.delete(REMIND_DECISIONS_KEY);
      return json({ ok: true, message: "decisions cleared" });
    }

    // GET /remind/decision/{rem_id} — 查单个决定
    const decisionMatch = url.pathname.match(/^\/remind\/decision\/(REM-\S+)$/);
    if (decisionMatch) {
      const remId = decisionMatch[1];
      const decision = await getRemindDecision(env, remId);
      return json(decision || { rem_id: remId, status: "pending" });
    }

    // 默认响应
    return new Response(
      `daily-cron v${VERSION}\n` +
      `Endpoints:\n` +
      `  GET  /health  — version + status\n` +
      `  GET  /tasks   — current task list\n` +
      `  GET  /dryrun  — preview Bark URLs (no push)\n` +
      `  GET  /test    — trigger all tasks (real push)\n` +
      `  POST /sync    — overwrite tasks (auth required)\n` +
      `  POST /set     — alias of /sync (auth required)\n` +
      `  POST /delete  — clear tasks (auth required)\n` +
      `\n` +
      `  提醒审批（公开，Bark URL 触发）:\n` +
      `  GET  /remind/approve?rem_id=REM-XXXX\n` +
      `  GET  /remind/reject?rem_id=REM-XXXX&reason=...\n` +
      `  GET  /remind/decisions — 拉取待处理决定\n` +
      `  GET  /remind/decision/REM-XXXX — 查单个决定`,
      { headers: { "content-type": "text/plain" } }
    );
  }
};

// --- 认证 ---
function checkAuth(request, env) {
  const token = env.AUTH_TOKEN;
  if (!token) return json({ error: "AUTH_TOKEN secret not set on Worker" }, 500);
  const header = request.headers.get("Authorization") || "";
  const provided = header.replace(/^Bearer\s+/i, "");
  if (provided !== token) return json({ error: "Unauthorized" }, 401);
  return null;
}

// --- 任务校验 ---
function validateTasks(tasks) {
  const errs = [];
  if (!Array.isArray(tasks)) return ["tasks must be an array"];
  for (let i = 0; i < tasks.length; i++) {
    const t = tasks[i];
    if (!t.tag) errs.push(`task[${i}]: missing tag`);
    if (!t.body) errs.push(`task[${i}]: missing body`);
  }
  return errs;
}

// --- KV 读取 ---
async function getTasks(env) {
  if (!env.TASKS) {
    console.error("TASKS KV namespace not bound");
    return DEFAULT_TASKS;
  }
  const raw = await env.TASKS.get("tasks");
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      console.warn("KV tasks empty or invalid, falling back to default");
    } catch (e) {
      console.error("Failed to parse tasks from KV:", e.message);
    }
  }
  return DEFAULT_TASKS;
}

// --- 执行所有任务 ---
async function runAllTasks(env) {
  const tasks = await getTasks(env);
  const results = [];
  for (const task of tasks) {
    const r = await barkPush(env, task);
    results.push({ tag: task.tag, status: r.status, ok: r.status === 200 });
  }
  // 记录 last_run
  const lastRun = {
    ran_at: new Date().toISOString(),
    task_count: tasks.length,
    results
  };
  try { await env.TASKS.put("last_run", JSON.stringify(lastRun)); } catch (e) { console.error("Failed to save last_run:", e.message); }
  return lastRun;
}

// --- Bark push ---
function buildBarkUrl(env, task) {
  const params = new URLSearchParams(task.params || {});
  return `https://api.day.app/${env.BARK_KEY}/${encodeURIComponent(task.tag)}/${encodeURIComponent(task.body)}?${params}`;
}

async function barkPush(env, task) {
  if (!env.BARK_KEY) return { status: "error", reason: "BARK_KEY not set" };
  const url = buildBarkUrl(env, task);
  try {
    const res = await fetch(url);
    return { status: res.status, url };
  } catch (e) {
    return { status: "error", reason: e.message, url };
  }
}

// --- 工具 ---
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json" }
  });
}

// ═══════════════════════════════════════════════════════
// 提醒审批 — Worker 侧（公开端点，由 Bark URL 触发）
// ═══════════════════════════════════════════════════════
// 设计意图：Minis 被杀后台时，Bark 通知的 approve/reject 仍能被处理。
// 用户点 Bark 通知里的按钮 → 打开 Worker URL → Worker 记录决定到 KV。
// Minis 恢复后 remind-action.py sync-from-worker 拉取决定并执行。

const REMIND_DECISIONS_KEY = "remind_decisions";

async function getRemindDecisions(env) {
  if (!env.TASKS) return [];
  const raw = await env.TASKS.get(REMIND_DECISIONS_KEY);
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

async function getRemindDecision(env, remId) {
  const decisions = await getRemindDecisions(env);
  return decisions.find(d => d.rem_id === remId) || null;
}

async function saveRemindDecisions(env, decisions) {
  if (!env.TASKS) return;
  await env.TASKS.put(REMIND_DECISIONS_KEY, JSON.stringify(decisions));
}

async function approveRemind(env, remId) {
  const decisions = await getRemindDecisions(env);
  const idx = decisions.findIndex(d => d.rem_id === remId);
  const decision = {
    rem_id: remId,
    status: "approved",
    decided_at: new Date().toISOString(),
    decided_by: "01-lead (via Bark)"
  };
  if (idx >= 0) decisions[idx] = decision;
  else decisions.push(decision);
  await saveRemindDecisions(env, decisions);

  // 发确认 Bark
  await barkPush(env, {
    tag: `REM:approved:${remId}`,
    body: `✅ 已批准 ${remId}`,
    params: { isArchive: 1, group: "remind", level: "timeSensitive" }
  });

  return { ok: true, ...decision };
}

async function rejectRemind(env, remId, reason) {
  const decisions = await getRemindDecisions(env);
  const idx = decisions.findIndex(d => d.rem_id === remId);
  const decision = {
    rem_id: remId,
    status: "rejected",
    decided_at: new Date().toISOString(),
    decided_by: "01-lead (via Bark)",
    reason
  };
  if (idx >= 0) decisions[idx] = decision;
  else decisions.push(decision);
  await saveRemindDecisions(env, decisions);

  // 发确认 Bark
  await barkPush(env, {
    tag: `REM:rejected:${remId}`,
    body: `❌ 已驳回 ${remId}: ${reason}`,
    params: { isArchive: 1, group: "remind", level: "timeSensitive" }
  });

  return { ok: true, ...decision };
}
