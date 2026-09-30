// 全局状态
let token = localStorage.getItem('blog_token');
let posts = [];
let images = [];
let videos = [];

// API 请求封装
async function api(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const response = await fetch(`/api${endpoint}`, {
    ...options,
    headers
  });
  
  const data = await response.json();
  
  if (!data.success) {
    alert(data.message || '请求失败');
    throw new Error(data.message);
  }
  
  return data;
}

// 页面切换
function showPage(page) {
  document.querySelectorAll('.content-page').forEach(p => p.classList.add('hidden'));
  document.getElementById(`${page}-page`).classList.remove('hidden');
  
  document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
  document.querySelector(`[data-page="${page}"]`).classList.add('active');
  
  // 加载对应数据
  if (page === 'dashboard') loadDashboard();
  if (page === 'posts') loadPosts();
  if (page === 'media') loadMedia();
  if (page === 'settings') loadSettings();
}

// 登录处理
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  
  try {
    const data = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    
    token = data.token;
    localStorage.setItem('blog_token', token);
    
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('admin-page').classList.remove('hidden');
    
    showPage('dashboard');
  } catch (err) {
    // 错误已在 api 函数中处理
  }
});

// 退出登录
document.getElementById('logout-btn').addEventListener('click', () => {
  token = null;
  localStorage.removeItem('blog_token');
  document.getElementById('admin-page').classList.add('hidden');
  document.getElementById('login-page').classList.remove('hidden');
});

// 导航点击
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const page = item.dataset.page;
    showPage(page);
  });
});

// 加载概览数据
async function loadDashboard() {
  try {
    const data = await api('/stats');
    const stats = data.data;
    
    document.getElementById('stat-posts').textContent = stats.totalPosts;
    document.getElementById('stat-published').textContent = stats.publishedPosts;
    document.getElementById('stat-images').textContent = stats.totalImages;
    document.getElementById('stat-videos').textContent = stats.totalVideos;
    document.getElementById('stat-views').textContent = stats.totalViews;
  } catch (err) {
    console.error('加载统计数据失败', err);
  }
}

// 加载文章列表
async function loadPosts() {
  try {
    const data = await api('/posts');
    posts = data.data;
    renderPosts();
  } catch (err) {
    console.error('加载文章失败', err);
  }
}

function renderPosts() {
  const container = document.getElementById('posts-list');
  
  if (posts.length === 0) {
    container.innerHTML = '<p style="text-align:center;color:var(--text-muted)">暂无文章</p>';
    return;
  }
  
  container.innerHTML = posts.map(post => `
    <div class="post-card" onclick="editPost('${post.id}')">
      <div class="post-info">
        <h3>${escapeHtml(post.title)}</h3>
        <div class="post-meta">
          <span class="badge badge-${post.status === 'published' ? 'success' : 'warning'}">
            ${post.status === 'published' ? '已发布' : '草稿'}
          </span>
          <span>📂 ${post.category}</span>
          <span>👁️ ${post.views || 0} 阅读</span>
          <span>📅 ${new Date(post.createdAt).toLocaleDateString('zh-CN')}</span>
        </div>
      </div>
      <div class="post-actions">
        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); editPost('${post.id}')">编辑</button>
        <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deletePost('${post.id}')">删除</button>
      </div>
    </div>
  `).join('');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 显示编辑器
function showPostEditor(post = null) {
  document.getElementById('posts-list').classList.add('hidden');
  document.getElementById('post-editor').classList.remove('hidden');
  
  if (post) {
    document.getElementById('post-title').value = post.title;
    document.getElementById('post-content').value = post.content;
    document.getElementById('post-category').value = post.category;
    document.getElementById('post-tags').value = (post.tags || []).join(', ');
    document.getElementById('post-editor').dataset.id = post.id;
  } else {
    document.getElementById('post-title').value = '';
    document.getElementById('post-content').value = '';
    document.getElementById('post-tags').value = '';
    document.getElementById('post-editor').dataset.id = '';
  }
}

function hidePostEditor() {
  document.getElementById('posts-list').classList.remove('hidden');
  document.getElementById('post-editor').classList.add('hidden');
}

function editPost(id) {
  const post = posts.find(p => p.id === id);
  if (post) showPostEditor(post);
}

async function savePost(status) {
  const id = document.getElementById('post-editor').dataset.id;
  const title = document.getElementById('post-title').value.trim();
  const content = document.getElementById('post-content').value.trim();
  const category = document.getElementById('post-category').value;
  const tags = document.getElementById('post-tags').value.split(',').map(t => t.trim()).filter(t);
  
  if (!title || !content) {
    alert('请填写标题和内容');
    return;
  }
  
  const postData = { title, content, category, tags, status };
  
  try {
    if (id) {
      await api(`/posts/${id}`, {
        method: 'PUT',
        body: JSON.stringify(postData)
      });
    } else {
      await api('/posts', {
        method: 'POST',
        body: JSON.stringify(postData)
      });
    }
    
    hidePostEditor();
    loadPosts();
  } catch (err) {
    console.error('保存失败', err);
  }
}

async function deletePost(id) {
  if (!confirm('确定要删除这篇文章吗？')) return;
  
  try {
    await api(`/posts/${id}`, { method: 'DELETE' });
    loadPosts();
  } catch (err) {
    console.error('删除失败', err);
  }
}

// 加载媒体库
async function loadMedia() {
  try {
    const [imgData, vidData] = await Promise.all([
      api('/media/images'),
      api('/media/videos')
    ]);
    
    images = imgData.data;
    videos = vidData.data;
    renderMedia();
  } catch (err) {
    console.error('加载媒体失败', err);
  }
}

function renderMedia() {
  const imgContainer = document.getElementById('image-grid');
  const vidContainer = document.getElementById('video-grid');
  
  imgContainer.innerHTML = images.length === 0 
    ? '<p style="color:var(--text-muted)">暂无图片</p>'
    : images.map(img => `
      <div class="media-item" onclick="copyImageUrl('${img.url}')">
        <img src="${img.url}" alt="${escapeHtml(img.originalName)}">
        <div class="media-overlay">
          <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteMedia('images', '${img.id}')">删除</button>
        </div>
      </div>
    `).join('');
  
  vidContainer.innerHTML = videos.length === 0 
    ? '<p style="color:var(--text-muted)">暂无视频</p>'
    : videos.map(video => `
      <div class="media-item" onclick="copyVideoUrl('${video.url}')">
        <video src="${video.url}"></video>
        <div class="media-overlay">
          <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteMedia('videos', '${video.id}')">删除</button>
        </div>
      </div>
    `).join('');
}

function triggerUpload(type) {
  const input = document.getElementById(`${type}-upload`);
  input.click();
}

async function handleMediaUpload(type) {
  const input = document.getElementById(`${type}-upload`);
  const file = input.files[0];
  
  if (!file) return;
  
  const formData = new FormData();
  formData.append(type, file);
  
  try {
    const response = await fetch(`/api/upload/${type}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    
    const data = await response.json();
    
    if (data.success) {
      alert('上传成功！');
      loadMedia();
    } else {
      alert(data.message || '上传失败');
    }
  } catch (err) {
    console.error('上传失败', err);
    alert('上传失败');
  }
  
  input.value = '';
}

function copyImageUrl(url) {
  navigator.clipboard.writeText(url);
  alert('图片链接已复制：' + url);
}

function copyVideoUrl(url) {
  navigator.clipboard.writeText(url);
  alert('视频链接已复制：' + url);
}

async function deleteMedia(type, id) {
  if (!confirm('确定要删除这个文件吗？')) return;
  
  try {
    await api(`/media/${type}/${id}`, { method: 'DELETE' });
    loadMedia();
  } catch (err) {
    console.error('删除失败', err);
  }
}

// 加载设置
async function loadSettings() {
  try {
    const data = await api('/settings');
    const settings = data.data;
    
    document.getElementById('setting-site-title').value = settings.siteTitle || '';
    document.getElementById('setting-site-desc').value = settings.siteDescription || '';
    document.getElementById('setting-admin-user').value = settings.adminUser || '';
    document.getElementById('setting-admin-password').value = settings.adminPassword || '';
  } catch (err) {
    console.error('加载设置失败', err);
  }
}

async function saveSettings() {
  const settings = {
    siteTitle: document.getElementById('setting-site-title').value,
    siteDescription: document.getElementById('setting-site-desc').value,
    adminUser: document.getElementById('setting-admin-user').value,
    adminPassword: document.getElementById('setting-admin-password').value
  };
  
  try {
    await api('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings)
    });
    
    alert('设置已保存');
  } catch (err) {
    console.error('保存失败', err);
  }
}

// 初始化检查
if (token) {
  document.getElementById('login-page').classList.add('hidden');
  document.getElementById('admin-page').classList.remove('hidden');
}
