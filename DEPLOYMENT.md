# Turbo Blog Django 公网发布指南

当前项目由一个 Django 服务同时提供前端页面、博客 API、文章管理、评论审核、图片上传、RSS、sitemap 和 robots.txt。推荐拓扑是 Railway Free + Neon Free + Railway Bucket：Neon 保存业务数据，私有 Railway Bucket 保存上传对象，Django 仍然保持前后端同源。

这是一套“尽量使用免费额度”的部署方案，不是无限或永久零成本承诺。Railway Bucket 会按存储量计费，服务到 Bucket 或用户的网络流量也可能计入服务用量；Neon 和 Railway 也有各自的额度和限制。部署后请在 Railway Workspace Usage 设置 Compute Hard Limit，达到硬限额时工作负载会下线以阻止继续产生超额计算费用。可按需在服务设置中启用 Serverless，让不活跃服务休眠。

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
- 存储状态：http://localhost:5173/api/storage
- sitemap：http://localhost:5173/sitemap.xml

Windows 可直接运行：

```bat
start-blog.bat
```

## 推荐部署：Railway Free + Neon Free + Railway Bucket

### 1. 创建 Neon Free 数据库

在 Neon 创建 Free 项目，复制 pooled PostgreSQL 连接字符串作为 `DATABASE_URL`。不要把连接字符串写入仓库；在 Railway 服务的 Variables 页面填写或使用密封变量。

### 2. 从 GitHub 创建 Railway Django 服务

从本仓库创建一个 Web Service。仓库根目录的 `railway.json` 会被 Railway Config as Code 自动读取：

- 默认使用 Railpack 根据 `requirements.txt` 构建；无需提交 Dockerfile。
- 启动命令执行 `migrate`、`seed_initial_data`，再以 Gunicorn 启动 Django。
- Gunicorn 绑定 `0.0.0.0:$PORT`；`PORT` 由 Railway 注入，不要把端口写死。
- 健康检查路径是 `/api/health`，返回 HTTP 200 后 Railway 才会切换部署流量。
- Railway 健康检查请求的主机名是 `healthcheck.railway.app`，必须加入 `ALLOWED_HOSTS`。

在 Networking 中生成 Railway 公网域名，并记下完整的 `<railway-public-domain>`。Railway 提供的 `RAILWAY_PUBLIC_DOMAIN` 会被初始数据命令用于生成站点公开 URL。

### 3. 创建并连接一个 Railway Bucket

在同一 Railway 项目中创建一个 Bucket。Bucket 是私有 S3-compatible 存储；新 Bucket 通常使用 `virtual` URL style，旧 Bucket 可能需要 `path`，以 Bucket Credentials 页面显示的值为准。

在 Django 服务的 Variables 中添加以下应用变量。尖括号是占位符，不是可提交的真实值：

```text
DJANGO_SECRET_KEY=<生成一串很长的随机字符串>
DJANGO_DEBUG=0
ADMIN_TOKEN=<生成一个强随机后台令牌>
ALLOWED_HOSTS=<railway-public-domain>,healthcheck.railway.app
DATABASE_URL=<Neon pooled PostgreSQL connection string>
REQUIRE_DATABASE_URL=1
OBJECT_STORAGE_ENABLED=1
```

然后添加 Bucket 的 S3 变量。最直接的方式是在 Bucket 的 Credentials 页面复制 `railway bucket credentials` 输出的同名 `AWS_*` 行到 Railway Variables，再把占位符替换为实际值。也可以使用 Railway Variable References；以下映射使用 Railway Bucket 提供的变量名（示例服务名为 `railway-bucket`，如果实际 Bucket 服务名不同请替换前缀）：

```text
AWS_ENDPOINT_URL=${{railway-bucket.ENDPOINT}}
AWS_ACCESS_KEY_ID=${{railway-bucket.ACCESS_KEY_ID}}
AWS_SECRET_ACCESS_KEY=${{railway-bucket.SECRET_ACCESS_KEY}}
AWS_S3_BUCKET_NAME=${{railway-bucket.BUCKET}}
AWS_DEFAULT_REGION=${{railway-bucket.REGION}}
AWS_S3_URL_STYLE=virtual
```

`AWS_SECRET_ACCESS_KEY` 是敏感值，使用 Reference 或 Sealed Variable，不要写进 README、`.env.example`、日志或 Git。`AWS_S3_URL_STYLE` 必须使用 Bucket Credentials 提供的值：新 Bucket 通常为 `virtual`；如果旧 Bucket 页面显示 `path`，就填写 `path`。如果 Railway 的自动注入已经生成这些 `AWS_*` 变量，不要再创建第二套同名变量。

### 4. 私有上传的访问行为

应用不会把 Railway Bucket 设为公开（Railway Bucket 本身是私有的）：

1. `POST /api/uploads` 把图片写入 Bucket，并返回稳定的同源 `/assets/uploads/<key>` 路径。
2. 浏览器访问该路径时，Django 为对象生成新的短时 signed GET URL，并返回 HTTP redirect。
3. 文件内容由 Bucket 直接提供；稳定路径可以长期保存在文章正文中，签名 URL 会在每次访问时刷新。

如果关闭 `OBJECT_STORAGE_ENABLED`，本地开发会回退到 `assets/uploads/`。生产 Railway 服务必须保持 `OBJECT_STORAGE_ENABLED=1`，否则部署文件系统不是上传持久层。

### 5. 部署后检查

生成域名并部署后，按顺序检查：

- `https://<railway-public-domain>/`：首页。
- `https://<railway-public-domain>/api/health`：健康检查返回 `ok=true`。
- `https://<railway-public-domain>/api/storage`：显示 PostgreSQL，并确认对象存储已启用。
- 使用 `ADMIN_TOKEN` 登录管理入口。
- 上传一张图片，确认响应 URL 是 `/assets/uploads/` 开头；再请求该 URL，确认它重定向到新的 signed URL 并能加载图片。
- `https://<railway-public-domain>/sitemap.xml`、`/rss.xml`、`/robots.txt`：确认站点公开 URL 正确。

Railway 官方参考：[`Config as Code`](https://docs.railway.com/config-as-code)、[`Variables`](https://docs.railway.com/variables)、[`Healthchecks`](https://docs.railway.com/deployments/healthchecks)、[`Cost Control`](https://docs.railway.com/pricing/cost-control)、[`Storage Buckets`](https://docs.railway.com/storage-buckets)、[`Uploading & Serving Files`](https://docs.railway.com/storage-buckets/uploading-serving)。

## 必填变量速查

生产 Django 服务的最小变量集合如下；任何值都只在部署平台填写：

```text
DJANGO_SECRET_KEY=<secret>
DJANGO_DEBUG=0
ADMIN_TOKEN=<secret>
ALLOWED_HOSTS=<railway-public-domain>,healthcheck.railway.app
DATABASE_URL=<Neon pooled URL>
REQUIRE_DATABASE_URL=1
OBJECT_STORAGE_ENABLED=1
AWS_ENDPOINT_URL=<Railway Bucket endpoint>
AWS_ACCESS_KEY_ID=<Railway Bucket access key>
AWS_SECRET_ACCESS_KEY=<Railway Bucket secret>
AWS_S3_BUCKET_NAME=<Railway Bucket S3 name>
AWS_DEFAULT_REGION=<Railway Bucket region, commonly auto>
AWS_S3_URL_STYLE=<virtual-or-path from Bucket Credentials>
```

## 本地数据与回退

默认 SQLite 文件：

```text
backend/data/turbo-blog-django.sqlite
```

未设置 `DATABASE_URL` 时使用 SQLite。支持持久磁盘的平台可以设置：

```text
SQLITE_FILE=/data/turbo-blog-django.sqlite
```

未启用对象存储时，图片上传保存到：

```text
assets/uploads/
```

可用 `UPLOAD_DIR` 修改本地目录。Railway 服务不应依赖临时本地文件系统保存生产数据或上传。

## 搜索引擎收录

上线后确认这些地址能访问：

- `https://<railway-public-domain>/sitemap.xml`
- `https://<railway-public-domain>/rss.xml`
- `https://<railway-public-domain>/robots.txt`

然后到 Google Search Console 或 Bing Webmaster Tools 提交 sitemap。

## 可选旧方案：Render + Cloudflare R2

仓库仍保留 `render.yaml` 和 `R2_*` 兼容变量，便于已有部署迁移或回滚。该方案不是当前推荐路径，也不应描述为零成本：Render、Cloudflare R2 的免费额度、休眠、流量和持久性规则由各自平台决定。若确实使用旧方案，请查看 `render.yaml`，并把所有密钥和 R2 endpoint 仅填写在 Render Dashboard 中；不要把旧配置复制到新的 Railway 服务。

## 旧 Node 后端

旧 Node 后端已经移动到：

```text
backend/legacy_node/
```

它只是作为回滚参考保留，当前主后端是 Django。
