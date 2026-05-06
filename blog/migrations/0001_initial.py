from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BlogUser",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("username", models.CharField(max_length=80, unique=True)),
                ("password_hash", models.CharField(max_length=256)),
                ("role", models.CharField(default="admin", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Captcha",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("answer_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("used", models.BooleanField(default=False)),
                ("failures", models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=240)),
                ("slug", models.SlugField(allow_unicode=True, max_length=120, unique=True)),
                ("excerpt", models.TextField(blank=True)),
                ("content", models.TextField(blank=True)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(default="published", max_length=20)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-published_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="RateLimit",
            fields=[
                ("key", models.CharField(max_length=160, primary_key=True, serialize=False)),
                ("count", models.IntegerField(default=0)),
                ("expires_at", models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name="Session",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("user_id", models.CharField(blank=True, max_length=80)),
                ("username", models.CharField(default="admin", max_length=80)),
                ("role", models.CharField(default="admin", max_length=40)),
                ("token_hash", models.CharField(db_index=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="SiteSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Turbo Blog", max_length=160)),
                ("description", models.TextField(default="记录代码、生活与灵感的个人博客。")),
                ("public_url", models.URLField(default="http://localhost:5173")),
            ],
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("author", models.CharField(default="匿名", max_length=40)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField()),
                ("approved", models.BooleanField(default=False)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="blog.post")),
            ],
        ),
    ]
