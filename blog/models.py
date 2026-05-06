from django.db import models


class SiteSetting(models.Model):
    title = models.CharField(max_length=160, default="Turbo Blog")
    description = models.TextField(default="记录代码、生活与灵感的个人博客。")
    public_url = models.URLField(default="http://localhost:5173")


class BlogUser(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    username = models.CharField(max_length=80, unique=True)
    password_hash = models.CharField(max_length=256)
    role = models.CharField(max_length=40, default="admin")
    created_at = models.DateTimeField(auto_now_add=True)


class Session(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    user_id = models.CharField(max_length=80, blank=True)
    username = models.CharField(max_length=80, default="admin")
    role = models.CharField(max_length=40, default="admin")
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)


class Post(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, default="published")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]


class Comment(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    author = models.CharField(max_length=40, default="匿名")
    content = models.TextField()
    created_at = models.DateTimeField()
    approved = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="pending")
    reviewed_at = models.DateTimeField(null=True, blank=True)


class Captcha(models.Model):
    id = models.CharField(primary_key=True, max_length=80)
    answer_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    failures = models.IntegerField(default=0)


class RateLimit(models.Model):
    key = models.CharField(primary_key=True, max_length=160)
    count = models.IntegerField(default=0)
    expires_at = models.DateTimeField()
