import { listArticles } from '../../lib.js';

// GET /api/articles/:slug — 详情 + 阅读计数（KV 持久化，不可用时降级为静态值）
export async function onRequestGet({ request, env, params, waitUntil }) {
  const article = listArticles().find(a => a.slug === params.slug);
  if (!article) {
    return Response.json({ error: 'Article not found' }, { status: 404 });
  }

  let views = article.views;
  try {
    if (env.VIEWS) {
      const stored = await env.VIEWS.get(`views:${article.slug}`);
      views = stored ? Number(stored) + 1 : article.views + 1;
      waitUntil(env.VIEWS.put(`views:${article.slug}`, String(views)));
    }
  } catch (e) {
    // KV 异常不阻塞响应，降级为静态计数
  }

  return Response.json({ ...article, views });
}
