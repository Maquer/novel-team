import { listArticles } from '../../lib.js';

// GET /api/articles  支持 ?category=&tag=&search=
export function onRequestGet({ request }) {
  const url = new URL(request.url);
  const data = listArticles({
    category: url.searchParams.get('category'),
    tag: url.searchParams.get('tag'),
    search: url.searchParams.get('search'),
  });
  return Response.json({ data, meta: { total: data.length, page: 1 } });
}
