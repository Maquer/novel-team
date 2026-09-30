import { listArticles } from '../../lib.js';

// GET /api/tags
export function onRequestGet() {
  const tags = [...new Set(listArticles().flatMap(a => a.tags))];
  return Response.json(tags);
}
