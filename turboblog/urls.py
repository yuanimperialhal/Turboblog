from django.urls import path, re_path

from blog import views


urlpatterns = [
    path("api/health", views.health),
    path("api/storage", views.storage),
    path("api/auth/login", views.auth_login),
    path("api/auth/me", views.auth_me),
    path("api/auth/logout", views.auth_logout),
    path("api/admin/users", views.admin_users),
    path("api/admin/comments", views.admin_comments),
    path("api/admin/comments/<str:comment_id>", views.admin_comment_detail),
    path("api/uploads", views.upload_image),
    path("api/captcha", views.captcha),
    path("api/site", views.site),
    path("api/ai/ask", views.ai_ask),
    path("api/posts", views.posts),
    path("api/posts/<str:post_key>", views.post_detail),
    path("api/posts/<str:post_key>/comments", views.post_comments),
    path("api/sitemap.xml", views.sitemap_xml),
    path("sitemap.xml", views.sitemap_xml),
    path("api/rss.xml", views.rss_xml),
    path("rss.xml", views.rss_xml),
    path("api/robots.txt", views.robots_txt),
    path("robots.txt", views.robots_txt),
    re_path(r"^(?P<path>.*)$", views.frontend),
]
