# Turbo Blog

Turbo Blog 是一个轻量个人博客项目。前端保留简约蓝色视觉和蓝发二次元头像，后端已经从 Node.js 重构为 Django。现在一个 Python 服务即可同时提供前端页面、博客 API、文章写作、评论审核、图片上传、RSS、sitemap 和 robots.txt。

## 当前功能

- 公开博客首页、文章列表、文章详情页
- 文章搜索、分类标签筛选
- 网页端写作、编辑、删除文章
- 编辑器支持 Markdown 加粗、代码块、图片链接和本地图片上传
- 文章评论、验证码、敏感词过滤、频率限制
- 评论默认进入审核，管理员可通过、拒绝或删除
- 管理员令牌登录、用户名密码登录、会话 token、退出登录
- 默认 Django + SQLite 存储
- AI 助手支持 RAG：先检索博客内容，再用 DeepSeek/GPT 等模型生成回答并返回来源
- `sitemap.xml`、`rss.xml`、`robots.txt`，方便公网收录
- 旧 Node 后端保留在 `backend/legacy_node/` 作为回滚参考

## 环境要求

- Python 3.11+
- Django 5.2+
- Windows 可直接使用 `start-blog.bat`

安装依赖：

```bash
python -m pip install -r requirements.txt
```

## 本地启动

推荐方式：

```bat
start-blog.bat
```

或者手动运行：

```bash
python manage.py migrate --noinput
python manage.py seed_initial_data
python manage.py runserver [::]:5173
```

启动后访问：

- 博客：http://localhost:5173
- 后端健康检查：http://localhost:5173/api/health
- sitemap：http://localhost:5173/sitemap.xml
- RSS：http://localhost:5173/rss.xml
- robots：http://localhost:5173/robots.txt

停止本地服务：

```bat
stop-blog.bat
```

## 写作与管理

1. 打开 http://localhost:5173
2. 点击页面顶部的写作入口
3. 本地默认密码或令牌填写 `dev-token`
4. 填写标题、摘要、标签和正文
5. 保存文章后回到首页或详情页查看

生产环境请务必修改管理员令牌：

```bash
ADMIN_TOKEN=your-strong-token python manage.py runserver [::]:5173
```

PowerShell：

```powershell
$env:ADMIN_TOKEN="your-strong-token"
python manage.py runserver [::]:5173
```

也可以设置管理员密码：

```bash
ADMIN_PASSWORD=your-strong-password python manage.py runserver [::]:5173
```

## 数据存储

默认 SQLite 文件：

```text
backend/data/turbo-blog-django.sqlite
```

如果部署平台支持持久磁盘，建议设置：

```text
SQLITE_FILE=/data/turbo-blog-django.sqlite
```

上传图片会保存到：

```text
assets/uploads/
```

## AI 助手与 RAG

AI 助手采用安全 RAG 流程：

```text
用户提问 -> Django 检索已发布博客 -> 取相关片段 -> 调用模型 API -> 返回答案和来源文章
```

模型不会直接连接 SQL，也不会拿到数据库账号密码。数据库只由 Django 后端访问。

不配置 API Key 时，系统会自动使用本地检索回答，项目仍然可以正常运行。

### DeepSeek 示例

```bash
AI_PROVIDER=deepseek
AI_API_KEY=你的 DeepSeek API Key
AI_MODEL=deepseek-chat
```

PowerShell：

```powershell
$env:AI_PROVIDER="deepseek"
$env:AI_API_KEY="你的 DeepSeek API Key"
$env:AI_MODEL="deepseek-chat"
python manage.py runserver 127.0.0.1:5173
```

### OpenAI 示例

```bash
AI_PROVIDER=openai
AI_API_KEY=你的 OpenAI API Key
AI_MODEL=gpt-4o-mini
```

也可以手动指定 OpenAI-compatible 地址：

```bash
AI_API_URL=https://api.example.com/v1/chat/completions
AI_API_KEY=你的 API Key
AI_MODEL=你的模型名
```

## 目录结构

```text
assets/
  avatar-blue-anime.png        站点头像、favicon、分享图
  uploads/                     后台上传图片目录
blog/
  models.py                    Django 数据模型
  views.py                     API、RSS、sitemap、静态页面入口
  middleware.py                CORS 处理
  management/commands/         初始数据导入命令
turboblog/
  settings.py                  Django 配置
  urls.py                      路由
backend/
  data/db.json                 旧数据种子，首次迁移会导入
  data/turbo-blog-django.sqlite 默认 Django SQLite 数据库
  legacy_node/                 旧 Node 后端，仅保留参考
_legacy-static/                早期纯静态博客版本
manage.py                     Django 管理入口
requirements.txt              Python 依赖
Procfile                      云平台启动命令
config.js                     前端 API 地址配置
index.html                    前端入口
script.js                     前端路由、渲染和交互逻辑
styles.css                    页面样式
start-blog.bat                Windows 启动脚本
stop-blog.bat                 Windows 停止脚本
```

## 公网部署

详细步骤见 `DEPLOYMENT.md`。当前推荐：

```text
GitHub 存代码
Railway / Render / VPS 运行 Django
SQLite 文件放到持久磁盘
```

云平台安装命令：

```bash
pip install -r requirements.txt
```

云平台启动命令：

```bash
python manage.py migrate --noinput && python manage.py seed_initial_data && gunicorn turboblog.wsgi:application --bind 0.0.0.0:$PORT
```

重要环境变量：

```text
DJANGO_SECRET_KEY=换成很长的随机字符串
DJANGO_DEBUG=0
ADMIN_TOKEN=换成你的后台强密码令牌
ALLOWED_HOSTS=你的公网域名
```

## 测试

运行 Django 后端检查：

```bash
python scripts/test_django_backend.py
```

也可以运行 Django 自检：

```bash
python manage.py check
```

## 常见问题

### 页面打不开

确认 Django 是否运行在 `http://localhost:5173`。

### 管理员登录失败

本地默认令牌是 `dev-token`。如果设置过 `ADMIN_TOKEN` 或 `ADMIN_PASSWORD`，请使用你设置的新值。

### 前端请求不到后端

当前默认同域请求 API。也就是说，页面在 `http://localhost:5173`，API 也是 `http://localhost:5173/api/...`。如果你未来前后端分开部署，再修改 `config.js` 的 `apiBase`。

### 旧 Node 后端还用吗

不用。它已经移动到 `backend/legacy_node/`，只是作为参考保留。
