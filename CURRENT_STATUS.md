# Turbo Blog 当前状态

更新时间：2026-05-06

## 项目状态

- 项目名已经从 `Yuan Blog` 改为 `Turbo Blog`。
- Django 项目包名是 `turboblog`。
- 正确启动模块是 `turboblog.wsgi:application`。
- 本地后端 15 项冒烟测试通过。
- Railway 配置文件 `railway.json` 已加入仓库。
- Docker 部署入口已加入仓库：`Dockerfile` + `start.sh`。

## Railway 当前问题

`https://turboblog.up.railway.app/` 在中国国内网络下不稳定，必须开全局代理才能访问。

本机曾解析到异常地址：

```text
::1
221.228.32.13
```

这说明问题主要在 `*.up.railway.app` 默认域名的 DNS/线路层，不是前端登录问题，也不是 `/api/health` 接口问题。客户端代理规则只能解决你自己的电脑，不能解决所有国内访客。

## 不开代理的可行路线

按稳定性排序：

1. 香港 VPS + 自己域名 + Caddy/Nginx
   - 国内访问更可控。
   - 不使用中国内地服务器，通常不走 ICP 备案。
   - 需要购买服务器，配置一次反向代理。

2. Railway 继续用，但绑定自己的域名并开启 Cloudflare 代理
   - 可以绕开 `up.railway.app` 默认域名。
   - 不保证所有国内网络都很快，但通常比直接访问 Railway 默认域名更可用。
   - 需要一个自己的域名。

3. 换 Zeabur 等对中文用户更友好的平台
   - 操作更顺，国内访问可能更友好。
   - 仍然要实测，不保证每条国内网络都稳定。

## 后续回答约定

后续继续处理部署时，默认以上状态为准，不再从头重新梳理项目。
