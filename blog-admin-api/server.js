const express = require('express');
const multer = require('multer');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = 3001;

// 中间件
app.use(cors());
app.use(express.json());
app.use('/uploads', express.static(path.join(__dirname, 'public', 'uploads')));
app.use(express.static(path.join(__dirname, 'public')));

// 数据目录
const DATA_DIR = path.join(__dirname, 'data');
const UPLOAD_DIR = path.join(__dirname, 'public', 'uploads');

// 确保目录存在
[DATA_DIR, UPLOAD_DIR, path.join(UPLOAD_DIR, 'images'), path.join(UPLOAD_DIR, 'videos')].forEach(dir => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
});

// 配置文件存储
let config = {
  posts: [],
  images: [],
  videos: [],
  settings: {
    siteTitle: '个人博客',
    siteDescription: '探索思考，记录成长',
    adminUser: 'admin',
    adminPassword: 'admin123'
  }
};

// 加载数据
function loadData() {
  const dataFile = path.join(DATA_DIR, 'data.json');
  if (fs.existsSync(dataFile)) {
    config = JSON.parse(fs.readFileSync(dataFile, 'utf8'));
  } else {
    config.posts = [
      {
        id: '1',
        title: 'Hello World',
        slug: 'hello-world',
        content: '# Hello World\n\n这是我的第一篇文章，关于如何开始学习编程。\n\n## 为什么学习编程\n\n编程是现代技能...',
        excerpt: '这是我的第一篇文章，关于如何开始学习编程。',
        category: '技术',
        tags: ['编程', '入门'],
        coverImage: '',
        status: 'published',
        createdAt: '2026-09-27T10:00:00.000Z',
        updatedAt: '2026-09-27T10:00:00.000Z',
        views: 5
      },
      {
        id: '2',
        title: '探索 AI 编程助手',
        slug: 'explore-ai-coding-assistants',
        content: '# 探索 AI 编程助手\n\nAI 正在改变我们编写代码的方式...\n\n## 主流工具\n\n- GitHub Copilot\n- Cursor\n- Claude Code',
        excerpt: '本文盘点主流 AI 编程助手，探讨它们如何改变开发工作流。',
        category: 'AI',
        tags: ['AI', '编程', '效率工具'],
        coverImage: '',
        status: 'published',
        createdAt: '2026-09-26T10:00:00.000Z',
        updatedAt: '2026-09-26T10:00:00.000Z',
        views: 0
      }
    ];
    saveData();
  }
}

// 保存数据
function saveData() {
  fs.writeFileSync(path.join(DATA_DIR, 'data.json'), JSON.stringify(config, null, 2));
}

// Multer 配置
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const isVideo = file.mimetype.startsWith('video/');
    cb(null, isVideo ? path.join(UPLOAD_DIR, 'videos') : path.join(UPLOAD_DIR, 'images'));
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    cb(null, `${Date.now()}-${uuidv4().slice(0, 8)}${ext}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 50 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const allowed = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowed.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error('不支持的文件类型'));
    }
  }
});

// ==================== API 路由 ====================

// 认证
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  if (username === config.settings.adminUser && password === config.settings.adminPassword) {
    res.json({ success: true, token: uuidv4() });
  } else {
    res.status(401).json({ success: false, message: '用户名或密码错误' });
  }
});

// 获取站点设置
app.get('/api/settings', (req, res) => {
  res.json({ success: true, data: config.settings });
});

app.put('/api/settings', (req, res) => {
  config.settings = { ...config.settings, ...req.body };
  saveData();
  res.json({ success: true });
});

// ==================== 文章管理 ====================

app.get('/api/posts', (req, res) => {
  let posts = config.posts;
  if (req.query.status && req.query.status !== 'all') {
    posts = posts.filter(p => p.status === req.query.status);
  }
  if (req.query.category) {
    posts = posts.filter(p => p.category === req.query.category);
  }
  posts.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  res.json({ success: true, data: posts });
});

app.get('/api/posts/:id', (req, res) => {
  const post = config.posts.find(p => p.id === req.params.id);
  if (!post) {
    return res.status(404).json({ success: false, message: '文章不存在' });
  }
  post.views = (post.views || 0) + 1;
  saveData();
  res.json({ success: true, data: post });
});

app.post('/api/posts', (req, res) => {
  const { title, content, excerpt, category, tags, coverImage, slug, status } = req.body;
  const post = {
    id: uuidv4(),
    title,
    slug: slug || title.replace(/\s+/g, '-').toLowerCase(),
    content,
    excerpt: excerpt || content.slice(0, 100) + '...',
    category: category || '未分类',
    tags: tags || [],
    coverImage: coverImage || '',
    status: status || 'draft',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    views: 0
  };
  config.posts.push(post);
  saveData();
  res.json({ success: true, data: post });
});

app.put('/api/posts/:id', (req, res) => {
  const index = config.posts.findIndex(p => p.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ success: false, message: '文章不存在' });
  }
  config.posts[index] = {
    ...config.posts[index],
    ...req.body,
    id: config.posts[index].id,
    updatedAt: new Date().toISOString()
  };
  saveData();
  res.json({ success: true, data: config.posts[index] });
});

app.delete('/api/posts/:id', (req, res) => {
  const index = config.posts.findIndex(p => p.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ success: false, message: '文章不存在' });
  }
  config.posts.splice(index, 1);
  saveData();
  res.json({ success: true });
});

// ==================== 媒体管理 ====================

app.post('/api/upload/image', upload.single('image'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ success: false, message: '请选择图片文件' });
  }
  const imageData = {
    id: uuidv4(),
    filename: req.file.filename,
    originalName: req.file.originalname,
    url: `/uploads/images/${req.file.filename}`,
    size: req.file.size,
    mimetype: req.file.mimetype,
    createdAt: new Date().toISOString()
  };
  config.images.push(imageData);
  saveData();
  res.json({ success: true, data: imageData });
});

app.post('/api/upload/video', upload.single('video'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ success: false, message: '请选择视频文件' });
  }
  const videoData = {
    id: uuidv4(),
    filename: req.file.filename,
    originalName: req.file.originalname,
    url: `/uploads/videos/${req.file.filename}`,
    size: req.file.size,
    mimetype: req.file.mimetype,
    createdAt: new Date().toISOString()
  };
  config.videos.push(videoData);
  saveData();
  res.json({ success: true, data: videoData });
});

app.get('/api/media/images', (req, res) => {
  res.json({ success: true, data: config.images });
});

app.get('/api/media/videos', (req, res) => {
  res.json({ success: true, data: config.videos });
});

app.delete('/api/media/:type/:id', (req, res) => {
  const { type, id } = req.params;
  const collection = type === 'images' ? 'images' : 'videos';
  const index = config[collection].findIndex(m => m.id === id);
  if (index === -1) {
    return res.status(404).json({ success: false, message: '媒体不存在' });
  }
  const media = config[collection][index];
  const filePath = path.join(__dirname, 'public', media.url);
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
  config[collection].splice(index, 1);
  saveData();
  res.json({ success: true });
});

app.get('/api/stats', (req, res) => {
  const stats = {
    totalPosts: config.posts.length,
    publishedPosts: config.posts.filter(p => p.status === 'published').length,
    draftPosts: config.posts.filter(p => p.status === 'draft').length,
    totalImages: config.images.length,
    totalVideos: config.videos.length,
    totalViews: config.posts.reduce((sum, p) => sum + (p.views || 0), 0)
  };
  res.json({ success: true, data: stats });
});

// 路由
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.get('/', (req, res) => {
  res.redirect('/admin');
});

// 启动服务器
loadData();
app.listen(PORT, () => {
  console.log(`🚀 博客管理后台运行在 http://localhost:${PORT}`);
  console.log(`📝 管理界面: http://localhost:${PORT}/admin`);
  console.log(`🔑 默认登录: admin / admin123`);
});
