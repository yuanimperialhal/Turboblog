import base64
import json
import mimetypes
import random
import re
import urllib.error
import urllib.request
import uuid
from datetime import timedelta
from datetime import timezone as datetime_timezone
from email.utils import format_datetime
from hashlib import sha256 as sha256_hash
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .models import BlogUser, Captcha, Comment, Post, RateLimit, Session, SiteSetting


def sha256(value):
    return sha256_hash(str(value).encode("utf-8")).hexdigest()


def iso(value):
    if not value:
        return None
    return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value, fallback=None):
    if not value:
        return fallback or timezone.now()
    parsed = parse_datetime(str(value))
    if parsed is None:
        return fallback or timezone.now()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return parsed


def json_ok(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False, "indent": 2})


def json_error(message, status=400):
    return json_ok({"error": message}, status=status)


def read_json(request):
    if len(request.body or b"") > settings.JSON_BODY_LIMIT:
        raise ValueError("Body is too large")
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON body")


def bearer_token(request):
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header.startswith("Bearer ") else ""


def ensure_defaults():
    site, _ = SiteSetting.objects.get_or_create(
        pk=1,
        defaults={
            "title": "Turbo Blog",
            "description": "记录代码、生活与灵感的个人博客。",
            "public_url": "http://localhost:5173",
        },
    )
    if not BlogUser.objects.filter(username="admin").exists():
        BlogUser.objects.create(
            id="user_admin",
            username="admin",
            password_hash=make_password(settings.ADMIN_PASSWORD),
            role="admin",
        )
    return site


def is_admin(request):
    token = bearer_token(request)
    if token and token == settings.ADMIN_TOKEN:
        return True
    if not token:
        return False
    now = timezone.now()
    return Session.objects.filter(
        token_hash=sha256(token),
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).exists()


def require_admin(request):
    if is_admin(request):
        return None
    return json_error("Unauthorized. Set Authorization: Bearer <ADMIN_TOKEN>.", status=401)


def request_ip(request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def has_sensitive_word(value):
    text = str(value or "").lower()
    return any(word and word in text for word in settings.SENSITIVE_WORDS)


def normalize_slug(value):
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "-", str(value or "").strip().lower())
    return slug.strip("-")[:80]


def make_slug(title, fallback):
    return normalize_slug(title) or f"post-{fallback}"


def post_to_dict(post, include_comments=True, public_only=True):
    comments = []
    if include_comments:
        queryset = post.comments.all().order_by("created_at")
        if public_only:
            queryset = queryset.filter(approved=True)
        comments = [comment_to_dict(comment) for comment in queryset]
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "content": post.content,
        "tags": post.tags or [],
        "status": post.status,
        "createdAt": iso(post.created_at),
        "updatedAt": iso(post.updated_at),
        "publishedAt": iso(post.published_at),
        "comments": comments,
    }


def post_summary(post, include_draft=False):
    if not include_draft and post.status != "published":
        return None
    public_count = post.comments.filter(approved=True).count()
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "tags": post.tags or [],
        "status": post.status,
        "createdAt": iso(post.created_at),
        "updatedAt": iso(post.updated_at),
        "publishedAt": iso(post.published_at),
        "commentCount": public_count,
    }


def clean_ai_text(value):
    text = re.sub(r"```[\s\S]*?```", " ", str(value or ""))
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`~-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def ai_terms(value):
    stop_words = {
        "一下", "这个", "那个", "什么", "怎么", "如何", "可以", "博客", "文章",
        "里面", "关于", "帮我", "告诉", "请问", "the", "and", "with", "from",
    }
    terms = []
    for chunk in re.findall(r"[a-zA-Z0-9_+#.-]+|[\u4e00-\u9fff]+", str(value or "").lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
            if len(chunk) <= 2:
                terms.append(chunk)
            else:
                terms.append(chunk)
                terms.extend(chunk[index:index + 2] for index in range(len(chunk) - 1))
        elif len(chunk) >= 2:
            terms.append(chunk)
    return [term for term in dict.fromkeys(terms) if term not in stop_words]


def ai_score(text, terms):
    lowered = text.lower()
    return sum(1 for term in terms if term and term in lowered)


def best_post_passages(post, terms):
    blocks = [
        ("标题", post.title, 6),
        ("摘要", post.excerpt, 4),
    ]
    content = clean_ai_text(post.content)
    for paragraph in re.split(r"(?:\n\s*){2,}|。|；|;|\n", content):
        paragraph = paragraph.strip()
        if len(paragraph) >= 12:
            blocks.append(("正文", paragraph, 1))

    matches = []
    for label, text, weight in blocks:
        score = ai_score(text, terms)
        if score:
            snippet = text[:180] + ("..." if len(text) > 180 else "")
            matches.append({"label": label, "snippet": snippet, "score": score * weight})
    return sorted(matches, key=lambda item: item["score"], reverse=True)[:2]


def public_sources_for_response(sources):
    return [{
        "title": source["title"],
        "slug": source["slug"],
        "url": source["url"],
        "excerpt": source["excerpt"],
        "passages": source["passages"],
    } for source in sources]


def local_ai_answer(sources):
    lead = "我从你的博客里找到了这些相关内容："
    parts = []
    for source in sources[:2]:
        first = source["passages"][0]
        parts.append(f"《{source['title']}》的{first['label']}提到：{first['snippet']}")
    return f"{lead}\n\n" + "\n\n".join(parts)


def rag_context(sources):
    chunks = []
    used = 0
    limit = settings.AI_MAX_CONTEXT_CHARS
    for index, source in enumerate(sources, start=1):
        passage_text = "\n".join(
            f"- {passage['label']}：{passage['snippet']}"
            for passage in source["passages"]
        )
        item = f"[{index}] 标题：{source['title']}\n链接：{source['url']}\n相关片段：\n{passage_text}"
        if used + len(item) > limit:
            break
        chunks.append(item)
        used += len(item)
    return "\n\n".join(chunks)


def rag_messages(question, sources):
    return [
        {
            "role": "system",
            "content": (
                "你是 Turbo Blog 的博客知识问答助手。只能依据用户博客片段回答，"
                "不要编造博客里没有的信息。回答要简洁、中文、像在帮助博客读者。"
                "最后必须列出参考来源，格式为：来源：1.《标题》。"
            ),
        },
        {
            "role": "user",
            "content": f"问题：{question}\n\n可用博客片段：\n{rag_context(sources)}",
        },
    ]


def call_rag_model(question, sources):
    if not settings.AI_API_KEY or not settings.AI_API_URL or not settings.AI_MODEL:
        return ""

    payload = {
        "model": settings.AI_MODEL,
        "messages": rag_messages(question, sources),
        "temperature": 0.2,
        "max_tokens": 700,
    }
    request = urllib.request.Request(
        settings.AI_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.AI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.AI_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
        raise ValueError("AI API 暂时不可用") from error

    return str(data["choices"][0]["message"]["content"]).strip()


@csrf_exempt
def ai_ask(request):
    if request.method != "POST":
        return json_error("Route not found", 404)
    try:
        body = read_json(request)
    except ValueError as error:
        return json_error(str(error))

    question = clean_ai_text(body.get("question"))[:300]
    if len(question) < 2:
        return json_error("Question is too short")

    terms = ai_terms(question)
    sources = []
    for post in public_posts():
        passages = best_post_passages(post, terms)
        if not passages:
            continue
        sources.append({
            "title": post.title,
            "slug": post.slug,
            "url": f"/post/{post.slug}",
            "excerpt": post.excerpt,
            "score": sum(item["score"] for item in passages),
            "passages": passages,
        })

    sources = sorted(sources, key=lambda item: item["score"], reverse=True)[:3]
    if not sources:
        return json_ok({
            "answer": "我还没有在已发布博客里找到直接相关的内容。你可以换一个更具体的关键词，或者先写一篇相关博客让我学习。",
            "sources": [],
            "mode": "local-search",
        })

    answer = local_ai_answer(sources)
    mode = "local-search"
    model = ""
    if settings.AI_API_KEY and settings.AI_API_URL and settings.AI_MODEL:
        try:
            answer = call_rag_model(question, sources) or answer
            mode = "rag-model"
            model = settings.AI_MODEL
        except ValueError:
            answer = f"{answer}\n\n（云端 AI 暂时不可用，已先用本地检索结果回答。）"

    return json_ok({
        "answer": answer,
        "sources": public_sources_for_response(sources),
        "mode": mode,
        "model": model,
    })


def comment_to_dict(comment, include_post=False):
    data = {
        "id": comment.id,
        "author": comment.author,
        "content": comment.content,
        "createdAt": iso(comment.created_at),
        "approved": comment.approved,
        "status": comment.status,
        "reviewedAt": iso(comment.reviewed_at),
    }
    if include_post:
        data.update({
            "postId": comment.post_id,
            "postSlug": comment.post.slug,
            "postTitle": comment.post.title,
        })
    return data


def verify_captcha(captcha_id, answer):
    try:
        captcha = Captcha.objects.get(pk=captcha_id)
    except Captcha.DoesNotExist:
        return False
    if captcha.used or captcha.expires_at <= timezone.now():
        return False
    passed = captcha.answer_hash == sha256(f"{captcha.id}:{str(answer or '').strip()}")
    if passed:
        captcha.used = True
    else:
        captcha.failures += 1
        if captcha.failures >= settings.CAPTCHA_FAILURE_LIMIT:
            captcha.used = True
    captcha.save(update_fields=["used", "failures"])
    return passed


def is_rate_limited(key, limit=None, window_ms=None):
    limit = limit or settings.COMMENT_RATE_LIMIT_MAX
    window_ms = window_ms or settings.COMMENT_RATE_LIMIT_WINDOW_MS
    now = timezone.now()
    RateLimit.objects.filter(expires_at__lte=now).delete()
    bucket, _ = RateLimit.objects.get_or_create(
        key=key,
        defaults={"count": 0, "expires_at": now + timedelta(milliseconds=window_ms)},
    )
    bucket.count += 1
    bucket.save(update_fields=["count"])
    return bucket.count > limit


@csrf_exempt
def health(request):
    return json_ok({"ok": True, "service": "study-blog-api"})


@csrf_exempt
def storage(request):
    return json_ok({
        "ok": True,
        "adapter": "django-sqlite",
        "file": settings.DATABASES["default"]["NAME"],
        "upgradeTargets": ["SQLite", "PostgreSQL"],
        "postgresReady": False,
    })


@csrf_exempt
def auth_login(request):
    if request.method != "POST":
        return json_error("Route not found", 404)
    ensure_defaults()
    try:
        body = read_json(request)
    except ValueError as error:
        return json_error(str(error))

    user = None
    username = str(body.get("username") or "")
    password = str(body.get("password") or "")
    token = str(body.get("token") or "")
    if username and password:
        user = BlogUser.objects.filter(username=username).first()
        if user and not check_password(password, user.password_hash):
            user = None
    if not user and token == settings.ADMIN_TOKEN:
        user = BlogUser.objects.filter(username="admin").first()
    if not user:
        return json_error("Invalid admin token", 401)

    raw_token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = timezone.now() + timedelta(days=7)
    Session.objects.create(
        id=f"session_{uuid.uuid4()}",
        user_id=user.id,
        username=user.username,
        role=user.role,
        token_hash=sha256(raw_token),
        expires_at=expires_at,
    )
    return json_ok({
        "token": raw_token,
        "user": {"username": user.username, "role": user.role},
        "expiresAt": iso(expires_at),
    })


@csrf_exempt
def auth_me(request):
    ensure_defaults()
    return json_ok({"authenticated": is_admin(request)})


@csrf_exempt
def auth_logout(request):
    token_hash = sha256(bearer_token(request))
    Session.objects.filter(token_hash=token_hash).update(revoked_at=timezone.now())
    return json_ok({"ok": True})


@csrf_exempt
def admin_users(request):
    admin_error = require_admin(request)
    if admin_error:
        return admin_error
    if request.method != "POST":
        return json_error("Route not found", 404)
    try:
        body = read_json(request)
    except ValueError as error:
        return json_error(str(error))
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or len(password) < 8:
        return json_error("Username is required and password must be at least 8 characters.")
    if BlogUser.objects.filter(username=username).exists():
        return json_error("User already exists", 409)
    role = body.get("role") if body.get("role") in ["reviewer", "author"] else "admin"
    user = BlogUser.objects.create(
        id=f"user_{uuid.uuid4()}",
        username=username,
        password_hash=make_password(password),
        role=role,
    )
    return json_ok({"user": {"id": user.id, "username": user.username, "role": user.role}}, 201)


@csrf_exempt
def captcha(request):
    left = random.randint(2, 9)
    right = random.randint(2, 9)
    captcha_id = f"captcha_{uuid.uuid4()}"
    answer = str(left + right)
    Captcha.objects.filter(expires_at__lte=timezone.now()).delete()
    Captcha.objects.create(
        id=captcha_id,
        answer_hash=sha256(f"{captcha_id}:{answer}"),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    return json_ok({"captcha": {"id": captcha_id, "question": f"{left} + {right} = ?"}})


@csrf_exempt
def site(request):
    site_setting = ensure_defaults()
    return json_ok({
        "title": site_setting.title,
        "description": site_setting.description,
        "publicUrl": site_setting.public_url,
    })


@csrf_exempt
def posts(request):
    ensure_defaults()
    admin = is_admin(request)
    if request.method == "GET":
        q = str(request.GET.get("q") or "").lower()
        include_draft = admin and request.GET.get("status", "published") == "all"
        queryset = Post.objects.all().prefetch_related("comments")
        result = []
        for post in queryset:
            item = post_summary(post, include_draft)
            if not item:
                continue
            search_text = " ".join([
                post.title,
                post.slug,
                post.excerpt,
                post.content,
                " ".join(post.tags or []),
            ]).lower()
            if q and q not in search_text:
                continue
            result.append(item)
        return json_ok({"posts": result})

    if request.method == "POST":
        admin_error = require_admin(request)
        if admin_error:
            return admin_error
        try:
            body = read_json(request)
        except ValueError as error:
            return json_error(str(error))
        now = timezone.now()
        status = "draft" if body.get("status") == "draft" else "published"
        post = Post.objects.create(
            id=f"post_{uuid.uuid4()}",
            title=str(body.get("title") or "未命名文章").strip(),
            slug=make_slug(body.get("slug") or body.get("title"), int(now.timestamp())),
            excerpt=str(body.get("excerpt") or "").strip(),
            content=str(body.get("content") or "").strip(),
            tags=[str(tag) for tag in body.get("tags", []) if str(tag).strip()],
            status=status,
            created_at=now,
            updated_at=now,
            published_at=None if status == "draft" else now,
        )
        return json_ok({"post": post_to_dict(post, public_only=False)}, 201)
    return json_error("Route not found", 404)


@csrf_exempt
def post_detail(request, post_key):
    ensure_defaults()
    admin = is_admin(request)
    post = Post.objects.filter(slug=post_key).first() or Post.objects.filter(id=post_key).first()
    if not post or (post.status != "published" and not admin):
        return json_error("Post not found", 404)

    if request.method == "GET":
        return json_ok({"post": post_to_dict(post, public_only=not admin)})

    admin_error = require_admin(request)
    if admin_error:
        return admin_error

    if request.method == "PUT":
        try:
            body = read_json(request)
        except ValueError as error:
            return json_error(str(error))
        status = "draft" if body.get("status") == "draft" else "published"
        post.title = str(body.get("title") or post.title).strip()
        post.slug = make_slug(body.get("slug") or post.slug or post.title, post.id)
        post.excerpt = str(body.get("excerpt") or "").strip()
        post.content = str(body.get("content") or "").strip()
        post.tags = [str(tag) for tag in body.get("tags", post.tags or []) if str(tag).strip()]
        post.status = status
        post.updated_at = timezone.now()
        if status == "published" and not post.published_at:
            post.published_at = post.updated_at
        post.save()
        return json_ok({"post": post_to_dict(post, public_only=False)})

    if request.method == "DELETE":
        deleted = {"id": post.id, "slug": post.slug, "title": post.title}
        post.delete()
        return json_ok({"ok": True, "deletedPost": deleted})

    return json_error("Route not found", 404)


@csrf_exempt
def post_comments(request, post_key):
    if request.method != "POST":
        return json_error("Route not found", 404)
    post = Post.objects.filter(slug=post_key).first() or Post.objects.filter(id=post_key).first()
    if not post or post.status != "published":
        return json_error("Post not found", 404)
    try:
        body = read_json(request)
    except ValueError as error:
        return json_error(str(error))
    if not verify_captcha(body.get("captchaId"), body.get("captchaAnswer")):
        return json_error("Captcha verification failed")
    content = str(body.get("content") or "").strip()
    author = str(body.get("author") or "匿名").strip()[:40] or "匿名"
    if len(content) < 2:
        return json_error("Comment is too short")
    if has_sensitive_word(content) or has_sensitive_word(author):
        return json_error("Comment contains sensitive words")
    if is_rate_limited(f"comment:{request_ip(request)}"):
        return json_error("Too many comments. Please try again later.", 429)
    comment = Comment.objects.create(
        id=f"comment_{uuid.uuid4()}",
        post=post,
        author=author,
        content=content[:2000],
        created_at=timezone.now(),
        approved=False,
        status="pending",
    )
    return json_ok({"comment": comment_to_dict(comment), "message": "评论已提交，等待审核后展示。"}, 201)


@csrf_exempt
def admin_comments(request):
    admin_error = require_admin(request)
    if admin_error:
        return admin_error
    status = request.GET.get("status", "pending")
    queryset = Comment.objects.select_related("post").all().order_by("-created_at")
    if status == "approved":
        queryset = queryset.filter(approved=True)
    elif status == "pending":
        queryset = queryset.filter(approved=False).exclude(status="rejected")
    elif status == "rejected":
        queryset = queryset.filter(status="rejected")
    return json_ok({"comments": [comment_to_dict(comment, include_post=True) for comment in queryset]})


@csrf_exempt
def admin_comment_detail(request, comment_id):
    admin_error = require_admin(request)
    if admin_error:
        return admin_error
    comment = get_object_or_404(Comment.objects.select_related("post"), pk=comment_id)
    if request.method == "PUT":
        try:
            body = read_json(request)
        except ValueError as error:
            return json_error(str(error))
        if body.get("status") == "approved":
            comment.approved = True
            comment.status = "approved"
        elif body.get("status") == "rejected":
            comment.approved = False
            comment.status = "rejected"
        else:
            return json_error("Unsupported comment status")
        comment.reviewed_at = timezone.now()
        comment.save()
        return json_ok({"comment": comment_to_dict(comment)})
    if request.method == "DELETE":
        deleted = {"id": comment.id, "postId": comment.post_id, "postSlug": comment.post.slug}
        comment.delete()
        return json_ok({"ok": True, "deletedComment": deleted})
    return json_error("Route not found", 404)


def extension_for_image_type(content_type):
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(str(content_type or "").lower(), "")


@csrf_exempt
def upload_image(request):
    admin_error = require_admin(request)
    if admin_error:
        return admin_error
    if request.method != "POST":
        return json_error("Route not found", 404)
    try:
        body = read_json(request)
    except ValueError as error:
        return json_error(str(error))
    content_type = str(body.get("type") or "").lower()
    ext = extension_for_image_type(content_type)
    if not ext:
        return json_error("Only PNG, JPG, WEBP and GIF images are supported.")
    raw_data = str(body.get("data") or "")
    if "," in raw_data:
        raw_data = raw_data.split(",", 1)[1]
    try:
        payload = base64.b64decode(raw_data, validate=True)
    except Exception:
        return json_error("Invalid image data")
    if not payload or len(payload) > settings.IMAGE_UPLOAD_LIMIT:
        return json_error("Image is empty or larger than the configured upload limit.")
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9_-]+", "-", Path(str(body.get("name") or "image")).stem, flags=re.I).strip("-")[:48] or "image"
    filename = f"{int(timezone.now().timestamp() * 1000)}-{uuid.uuid4().hex[:8]}-{safe_name}{ext}"
    target = settings.UPLOAD_DIR / filename
    target.write_bytes(payload)
    return json_ok({
        "image": {
            "url": f"/assets/uploads/{filename}",
            "filename": filename,
            "size": len(payload),
            "type": content_type,
        }
    }, 201)


def public_posts():
    return Post.objects.filter(status="published").order_by("-published_at", "-created_at")


@csrf_exempt
def sitemap_xml(request):
    site_setting = ensure_defaults()
    public_url = site_setting.public_url.rstrip("/")
    post_urls = "".join(
        f"<url><loc>{xml_escape(public_url + '/post/' + post.slug)}</loc><lastmod>{xml_escape(iso(post.updated_at) or '')}</lastmod></url>"
        for post in public_posts()
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{xml_escape(public_url)}</loc></url>{post_urls}</urlset>'
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


@csrf_exempt
def rss_xml(request):
    site_setting = ensure_defaults()
    public_url = site_setting.public_url.rstrip("/")
    items = "".join(
        "<item>"
        f"<title>{xml_escape(post.title)}</title>"
        f"<link>{xml_escape(public_url + '/post/' + post.slug)}</link>"
        f"<description>{xml_escape(post.excerpt)}</description>"
        f"<pubDate>{format_datetime((post.published_at or post.created_at).astimezone(datetime_timezone.utc), usegmt=True)}</pubDate>"
        "</item>"
        for post in public_posts()
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{xml_escape(site_setting.title)}</title><link>{xml_escape(public_url)}</link><description>{xml_escape(site_setting.description)}</description>{items}</channel></rss>'
    return HttpResponse(xml, content_type="application/rss+xml; charset=utf-8")


@csrf_exempt
def robots_txt(request):
    site_setting = ensure_defaults()
    public_url = site_setting.public_url.rstrip("/")
    return HttpResponse(f"User-agent: *\nAllow: /\nSitemap: {public_url}/sitemap.xml\n", content_type="text/plain; charset=utf-8")


def frontend(request, path=""):
    requested = path or "index.html"
    root = settings.STATIC_ROOT_DIR.resolve()
    target = (root / requested).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise Http404("Forbidden")

    if target.is_file():
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        return FileResponse(target.open("rb"), content_type=content_type)

    if Path(requested).suffix:
        raise Http404("Not found")
    index = root / "index.html"
    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
