import { listArticles } from '../../lib.js';

// GET /api/articles/recent — 静态路由优先于 [slug] 动态路由
export function onRequestGet() {
  return Response.json(listArticles().slice(0, 5));
}
