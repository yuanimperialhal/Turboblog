import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from blog.models import BlogUser, Comment, Post, SiteSetting
from blog.views import parse_iso


class Command(BaseCommand):
    help = "Seed the Django database from backend/data/db.json when it is empty."

    def handle(self, *args, **options):
        db_json = settings.BASE_DIR / "backend" / "data" / "db.json"
        site, _ = SiteSetting.objects.get_or_create(pk=1)
        if db_json.exists():
            data = json.loads(Path(db_json).read_text(encoding="utf-8"))
            site_data = data.get("site") or {}
            site.title = site_data.get("title") or site.title
            site.description = site_data.get("description") or site.description
            site.public_url = site_data.get("publicUrl") or site.public_url
            site.save()
        else:
            data = {"posts": []}

        if not BlogUser.objects.filter(username="admin").exists():
            BlogUser.objects.create(
                id="user_admin",
                username="admin",
                password_hash=make_password(settings.ADMIN_PASSWORD),
                role="admin",
            )

        created_count = 0
        for item in data.get("posts", []):
            if Post.objects.filter(id=item.get("id")).exists() or Post.objects.filter(slug=item.get("slug")).exists():
                continue
            post = Post.objects.create(
                id=item.get("id") or f"post_{item.get('slug')}",
                title=item.get("title") or "未命名文章",
                slug=item.get("slug") or item.get("id"),
                excerpt=item.get("excerpt") or "",
                content=item.get("content") or "",
                tags=item.get("tags") or [],
                status=item.get("status") or "published",
                created_at=parse_iso(item.get("createdAt")),
                updated_at=parse_iso(item.get("updatedAt")),
                published_at=parse_iso(item.get("publishedAt"), None) if item.get("publishedAt") else None,
            )
            for comment in item.get("comments") or []:
                Comment.objects.create(
                    id=comment.get("id"),
                    post=post,
                    author=comment.get("author") or "匿名",
                    content=comment.get("content") or "",
                    created_at=parse_iso(comment.get("createdAt")),
                    approved=bool(comment.get("approved")),
                    status=comment.get("status") or ("approved" if comment.get("approved") else "pending"),
                    reviewed_at=parse_iso(comment.get("reviewedAt"), None) if comment.get("reviewedAt") else None,
                )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} missing posts into Django database."))
