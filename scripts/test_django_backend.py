import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "backend" / "data" / "test-django.sqlite"
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "turboblog.settings")
os.environ["SQLITE_FILE"] = str(TEST_DB)
os.environ["ADMIN_TOKEN"] = "dev-token"
os.environ["COMMENT_RATE_LIMIT_MAX"] = "8"
os.environ["AI_PROVIDER"] = "local"
os.environ["AI_API_KEY"] = ""

import django  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client, override_settings  # noqa: E402


def record(results, name, passed, detail=""):
    results.append({"name": name, "passed": passed, "detail": detail})


def body(response):
    return json.loads(response.content.decode("utf-8") or "{}")


def main():
    if TEST_DB.exists():
        TEST_DB.unlink()
    django.setup()
    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_initial_data", verbosity=0)

    client = Client()
    admin_headers = {"HTTP_AUTHORIZATION": "Bearer dev-token"}
    results = []

    health = body(client.get("/api/health"))
    record(results, "Django 健康检查", health.get("ok") is True, health.get("service"))

    storage = body(client.get("/api/storage"))
    record(results, "Django SQLite 存储", storage.get("adapter") == "django-sqlite", storage.get("file"))

    site = body(client.get("/api/site"))
    record(results, "站点信息", site.get("title") == "Turbo Blog", site.get("title"))

    posts = body(client.get("/api/posts")).get("posts", [])
    record(results, "文章列表", len(posts) >= 1, f"{len(posts)} posts")
    first_slug = posts[0]["slug"]

    post = body(client.get(f"/api/posts/{first_slug}")).get("post", {})
    record(results, "文章详情", post.get("slug") == first_slug, post.get("title"))

    login = body(client.post("/api/auth/login", data=json.dumps({"token": "dev-token"}), content_type="application/json"))
    token = login.get("token")
    record(results, "令牌登录", bool(token), login.get("expiresAt"))
    session_headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    created = body(client.post(
        "/api/posts",
        data=json.dumps({
            "title": "Django 自动测试文章",
            "slug": "django-api-test",
            "excerpt": "Django backend smoke test",
            "content": "这是一篇 **Django** 测试文章。",
            "tags": ["技术"],
            "status": "published",
        }, ensure_ascii=False),
        content_type="application/json",
        **session_headers,
    )).get("post", {})
    record(results, "授权新建文章", created.get("slug") == "django-api-test", created.get("id"))

    updated = body(client.put(
        f"/api/posts/{created['id']}",
        data=json.dumps({**created, "title": "Django 自动测试文章已更新"}, ensure_ascii=False),
        content_type="application/json",
        **session_headers,
    )).get("post", {})
    record(results, "授权修改文章", updated.get("title", "").endswith("已更新"), updated.get("title"))

    chinese = body(client.post(
        "/api/posts",
        data=json.dumps({
            "title": "中文路径测试",
            "slug": "中文路径测试",
            "excerpt": "验证中文 slug",
            "content": "中文正文内容",
            "tags": ["技术"],
            "status": "published",
        }, ensure_ascii=False),
        content_type="application/json",
        **session_headers,
    )).get("post", {})
    chinese_detail = body(client.get(f"/api/posts/{quote(chinese['slug'])}")).get("post", {})
    record(results, "中文 slug 文章详情", chinese_detail.get("slug") == "中文路径测试", chinese_detail.get("title"))

    ai_answer = body(client.post(
        "/api/ai/ask",
        data=json.dumps({"question": "Django 测试文章讲了什么"}, ensure_ascii=False),
        content_type="application/json",
    ))
    ai_sources = ai_answer.get("sources", [])
    record(
        results,
        "本地 AI 博客问答",
        bool(ai_answer.get("answer")) and any(source.get("slug") == "django-api-test" for source in ai_sources),
        ai_sources[0].get("title") if ai_sources else ai_answer.get("answer"),
    )

    with override_settings(
        AI_API_KEY="fake-key",
        AI_API_URL="https://example.test/v1/chat/completions",
        AI_MODEL="test-rag-model",
    ), patch("blog.views.call_rag_model", return_value="模型根据博客片段生成的回答"):
        rag_answer = body(client.post(
            "/api/ai/ask",
            data=json.dumps({"question": "Django 测试文章讲了什么"}, ensure_ascii=False),
            content_type="application/json",
        ))
    record(
        results,
        "云端 RAG 模型问答",
        rag_answer.get("answer") == "模型根据博客片段生成的回答" and rag_answer.get("mode") == "rag-model",
        rag_answer.get("model"),
    )

    captcha = body(client.get("/api/captcha")).get("captcha", {})
    bad_comment = body(client.post(
        f"/api/posts/{created['slug']}/comments",
        data=json.dumps({"content": "测试评论", "captchaId": captcha.get("id"), "captchaAnswer": "999"}, ensure_ascii=False),
        content_type="application/json",
    ))
    record(results, "验证码错误拦截", bad_comment.get("error") == "Captcha verification failed", bad_comment.get("error"))

    png_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lkXc5QAAAABJRU5ErkJggg=="
    upload = body(client.post(
        "/api/uploads",
        data=json.dumps({"name": "test.png", "type": "image/png", "data": png_1x1}),
        content_type="application/json",
        **session_headers,
    )).get("image", {})
    record(results, "图片上传", upload.get("url", "").startswith("/assets/uploads/"), upload.get("url"))
    if upload.get("url"):
        uploaded_file = ROOT / upload["url"].lstrip("/")
        if uploaded_file.exists():
            uploaded_file.unlink()

    sitemap = client.get("/sitemap.xml").content.decode("utf-8")
    record(results, "sitemap", "<urlset" in sitemap and "/post/" in sitemap, "sitemap.xml")

    deleted = body(client.delete(f"/api/posts/{created['id']}", **session_headers))
    record(results, "授权删除文章", deleted.get("ok") is True, deleted.get("deletedPost", {}).get("slug"))
    if chinese.get("id"):
        client.delete(f"/api/posts/{chinese['id']}", **session_headers)

    failed = [item for item in results if not item["passed"]]
    for item in results:
        flag = "PASS" if item["passed"] else "FAIL"
        print(f"{flag} {item['name']}: {item['detail']}")
    if failed:
        raise SystemExit(f"Failed checks: {', '.join(item['name'] for item in failed)}")
    print(f"All {len(results)} Django checks passed.")
    connection.close()
    if TEST_DB.exists():
        TEST_DB.unlink()


if __name__ == "__main__":
    main()
