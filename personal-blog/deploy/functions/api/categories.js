import { listArticles } from '../../lib.js';

// GET /api/categories
export function onRequestGet() {
  const categories = [...new Set(listArticles().map(a => a.category))];
  return Response.json(categories);
}
