# Turbo Blog Django 公网发布指南

当前项目已经切换为 Django 后端：一个 Python 服务同时提供前端页面、博客 API、图片上传、RSS、sitemap 和 robots.txt。

## 本地运行

```bash
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py seed_initial_data
python manage.py runserver [::]:5173
```

访问：

- 博客：http://localhost:5173
- 健康检查：http://localhost:5173/api/health
- sitemap：http://localhost:5173/sitemap.xml

Windows 可直接运行：

```bat
start-blog.bat
```

## Render Free + Neon + Cloudflare R2

这套方案不依赖 Render 持久磁盘：Render Free 只运行 Django，Neon PostgreSQL 保存文章、评论和会话，Cloudflare R2 保存上传图片。

仓库根目录的 `render.yaml` 会创建一个 Render Free Web Service。先准备：

1. 在 Neon 创建免费项目，复制 pooled `DATABASE_URL`（建议使用带 `-pooler` 的连接地址）。
2. 在 Cloudflare R2 创建 `turboblog-uploads` bucket。
3. 为该 bucket 创建 Object Read & Write API token，并记录 S3 endpoint、Access Key ID、Secret Access Key。
4. 为 bucket 启用自定义域名或临时 `r2.dev` 公共地址，作为 `R2_PUBLIC_BASE_URL`。
5. 在 Render Dashboard 用仓库里的 `render.yaml` 创建 Blueprint，并填入下列未写入仓库的值。

```text
DATABASE_URL=Neon pooled connection string
R2_ENDPOINT_URL=https://你的账户ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=Cloudflare 生成的 Access Key ID
R2_SECRET_ACCESS_KEY=Cloudflare 生成的 Secret Access Key
R2_BUCKET_NAME=turboblog-uploads
R2_PUBLIC_BASE_URL=https://你的图片公共域名（末尾不要加 /）
```

`DJANGO_SECRET_KEY` 和 `ADMIN_TOKEN` 由 Render 自动生成，不写入仓库。`REQUIRE_DATABASE_URL=1` 和 `R2_STORAGE_ENABLED=1` 已由 Blueprint 设置；缺少 PostgreSQL 或任何 R2 配置时应用会明确拒绝启动，避免数据误写到 Render 临时文件系统。

Render 安装命令：

```bash
pip install -r requirements.txt
```

启动命令：

```bash
python manage.py migrate --noinput && python manage.py seed_initial_data && gunicorn turboblog.wsgi:application --bind 0.0.0.0:$PORT
```

项目也带了 `Procfile`，支持会读取 Procfile 的平台自动部署。部署后检查：

- `https://你的 Render 域名/`
- `https://你的 Render 域名/api/health`
- `https://你的 Render 域名/sitemap.xml`

## 必填环境变量

```text
DJANGO_SECRET_KEY=换成一串很长的随机字符
DJANGO_DEBUG=0
ADMIN_TOKEN=换成你的后台强密码令牌
ALLOWED_HOSTS=你的域名或平台分配域名
DATABASE_URL=PostgreSQL 连接地址（公网部署推荐）
```

例如：

```text
ALLOWED_HOSTS=turbo-blog-production.up.railway.app
```

如果暂时不知道域名，也可以先用：

```text
ALLOWED_HOSTS=*
```

## 数据保存与本地回退

默认 SQLite 文件：

```text
backend/data/turbo-blog-django.sqlite
```

未设置 `DATABASE_URL` 时使用 SQLite。支持持久磁盘的平台可以设置：

```text
SQLITE_FILE=/data/turbo-blog-django.sqlite
```

未启用 R2 时图片上传会保存到：

```text
assets/uploads/
```

可用 `UPLOAD_DIR` 修改本地目录。Render Free 的文件系统会被重置，因此公网部署必须使用 PostgreSQL 与 R2，不能依赖 SQLite 或本地上传目录。

## 搜索引擎收录

上线后确认这些地址能访问：

- `https://你的域名/sitemap.xml`
- `https://你的域名/rss.xml`
- `https://你的域名/robots.txt`

然后到 Google Search Console 或 Bing Webmaster Tools 提交 sitemap。

## 旧 Node 后端

旧 Node 后端已经移动到：

```text
backend/legacy_node/
```

它只是作为回滚参考保留，当前主后端是 Django。
