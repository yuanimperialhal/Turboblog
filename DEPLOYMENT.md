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

## Railway / Render 部署

1. 把项目推送到 GitHub。
2. 在 Railway 或 Render 里新建 Web Service。
3. 连接 GitHub 仓库。
4. 安装命令：

```bash
pip install -r requirements.txt
```

5. 启动命令：

```bash
python manage.py migrate --noinput && python manage.py seed_initial_data && gunicorn turboblog.wsgi:application --bind 0.0.0.0:$PORT
```

项目也带了 `Procfile`，支持会读取 Procfile 的平台自动部署。

### Render Blueprint

仓库根目录的 `render.yaml` 已包含完整 Render 配置。把仓库连接为 Blueprint 后，Render 会创建一个 `starter` Web Service，并挂载 1 GB 持久磁盘到 `/data`。

Render 的免费 Web Service 不能挂载持久磁盘，因此该配置会产生付费资源。数据库和上传图片分别保存在：

```text
/data/turbo-blog-django.sqlite
/data/uploads/
```

`DJANGO_SECRET_KEY` 和 `ADMIN_TOKEN` 由 Render 自动生成，不写入仓库。部署后检查：

- `https://你的 Render 域名/`
- `https://你的 Render 域名/api/health`
- `https://你的 Render 域名/sitemap.xml`

## 必填环境变量

```text
DJANGO_SECRET_KEY=换成一串很长的随机字符
DJANGO_DEBUG=0
ADMIN_TOKEN=换成你的后台强密码令牌
ALLOWED_HOSTS=你的域名或平台分配域名
```

例如：

```text
ALLOWED_HOSTS=turbo-blog-production.up.railway.app
```

如果暂时不知道域名，也可以先用：

```text
ALLOWED_HOSTS=*
```

## 数据保存

默认 SQLite 文件：

```text
backend/data/turbo-blog-django.sqlite
```

如果部署平台支持持久磁盘，建议把数据库放到持久目录：

```text
SQLITE_FILE=/data/turbo-blog-django.sqlite
```

图片上传会保存到：

```text
/data/uploads/
```

本地开发未设置 `UPLOAD_DIR` 时仍使用 `assets/uploads/`。长期公网运行也可以后续迁移到对象存储。

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
