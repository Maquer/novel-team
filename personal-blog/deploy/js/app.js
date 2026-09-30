// Simple SPA-like app using vanilla JS
const API_BASE = '/api';

async function fetchJSON(url) {
  const res = await fetch(url);
  return res.json();
}

function renderArticleCard(article) {
  return `
    <a href="/article.html?slug=${article.slug}" class="article-card">
      <span class="category-tag">${article.category}</span>
      <h3>${article.title}</h3>
      <p class="excerpt">${article.excerpt}</p>
      <div class="meta">
        <span>${article.date}</span>
        <span>${article.views} 阅读</span>
      </div>
    </a>
  `;
}

function renderArticleListItem(article) {
  return `
    <a href="/article.html?slug=${article.slug}" class="article-list-item">
      <div class="list-item-content">
        <h3>${article.title}</h3>
        <p class="excerpt-small">${article.excerpt}</p>
      </div>
      <div class="list-item-meta">
        <span class="date">${article.date}</span>
        <span class="views">${article.views} 阅读</span>
      </div>
    </a>
  `;
}

// Home page
if (document.getElementById('featured-articles')) {
  Promise.all([
    fetchJSON(`${API_BASE}/articles?limit=3`),
    fetchJSON(`${API_BASE}/articles/recent`),
    fetchJSON(`${API_BASE}/categories`)
  ]).then(([featured, recent, categories]) => {
    const featuredEl = document.getElementById('featured-articles');
    const recentEl = document.getElementById('recent-articles');
    const catsEl = document.getElementById('categories');
    
    featuredEl.innerHTML = featured.data.map(renderArticleCard).join('');
    recentEl.innerHTML = recent.slice(0, 5).map(renderArticleListItem).join('');
    catsEl.innerHTML = categories.map(cat => 
      `<li><a href="/articles.html?category=${encodeURIComponent(cat)}">${cat}</a></li>`
    ).join('');
  }).catch(() => {
    featuredEl && (featuredEl.innerHTML = '<div class="loading">加载失败</div>');
  });
}

// Articles page
if (document.getElementById('article-list')) {
  const params = new URLSearchParams(window.location.search);
  const category = params.get('category');
  let url = `${API_BASE}/articles?limit=20`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  
  fetch(url).then(r => r.json()).then(data => {
    const list = document.getElementById('article-list');
    if (!list) return;
    list.innerHTML = data.data.map(renderArticleCard).join('') || '<div class="loading">暂无文章</div>';
  });
}

// Article detail page
if (document.getElementById('article-content')) {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('slug');
  if (!slug) {
    document.getElementById('article-content').innerHTML = '<div class="loading">未指定文章</div>';
  } else {
    fetch(`${API_BASE}/articles/${slug}`).then(r => r.json()).then(article => {
      document.getElementById('article-title').textContent = article.title;
      document.getElementById('article-meta').innerHTML = `
        <span class="category">${article.category}</span>
        <span>${article.date}</span>
        <span>${article.views} 阅读</span>
      `;
      document.getElementById('article-tags').innerHTML = article.tags.map(t => 
        `<span class="tag">${t}</span>`
      ).join('');
      // Simple markdown-like rendering
      document.getElementById('article-content').innerHTML = article.content
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
        .replace(/`(.*?)`/gim, '<code>$1</code>')
        .replace(/\n/gim, '<br>')
        .replace(/^- (.*$)/gim, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>')
        .replace(/<br><br>/gim, '</p><p>');
      
      // Wrap consecutive <li> in <ul>
      const content = document.getElementById('article-content');
      let html = content.innerHTML;
      html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');
      content.innerHTML = html;
    }).catch(() => {
      document.getElementById('article-content').innerHTML = '<div class="loading">加载失败</div>';
    });
  }
}

// Categories on articles page
if (document.getElementById('filter-categories')) {
  fetch(`${API_BASE}/categories`).then(r => r.json()).then(categories => {
    const el = document.getElementById('filter-categories');
    if (el) {
      el.innerHTML = `<button class="filter-btn active" data-cat="">全部</button>` + 
        categories.map(cat => `<button class="filter-btn" data-cat="${cat}">${cat}</button>`).join('');
      // Add click handlers
      el.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          el.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const cat = btn.dataset.cat;
          const url = cat ? `/articles.html?category=${encodeURIComponent(cat)}` : '/articles.html';
          window.history.pushState({}, '', url);
          location.reload();
        });
      });
    }
  });
}
