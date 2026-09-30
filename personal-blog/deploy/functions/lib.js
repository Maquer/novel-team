// 非路由模块（不导出 onRequest，不会被当作 route）
// 文章数据以 JSON 模块内嵌进函数包，零外部依赖
import raw from '../functions-data.json';

export const articles = raw.articles;

export function listArticles({ category, tag, search } = {}) {
  let result = [...articles];
  if (category) result = result.filter(a => a.category === category);
  if (tag) result = result.filter(a => a.tags.includes(tag));
  if (search) {
    const s = String(search).toLowerCase();
    result = result.filter(a =>
      a.title.toLowerCase().includes(s) ||
      a.excerpt.toLowerCase().includes(s) ||
      a.content.toLowerCase().includes(s)
    );
  }
  result.sort((a, b) => b.date.localeCompare(a.date));
  return result;
}
