# Railway Free Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Turbo Blog on Railway Free with Neon PostgreSQL and a private Railway Bucket while ensuring usage stops at the free allowance instead of upgrading to a paid plan.

**Architecture:** Django remains the same-origin frontend and API service. Business data uses the existing Neon `DATABASE_URL`; uploads use an S3-compatible private Railway Bucket and stable `/assets/uploads/<key>` URLs that redirect to short-lived signed object URLs. Local development keeps the existing SQLite and filesystem fallbacks.

**Tech Stack:** Django 5.2, PostgreSQL/Neon, boto3 S3 API, Railway Free, Gunicorn

## Global Constraints

- Do not enable Railway Hobby or any paid Cloudflare R2 subscription.
- Keep frontend and backend same-origin.
- Do not store secrets in Git.
- Use a hard usage limit so workloads stop instead of creating payable overage.
- Preserve the existing R2-compatible public URL path as a backward-compatible option.

---

### Task 1: Support private S3-compatible upload storage

**Files:**
- Modify: `blog/tests.py`
- Modify: `blog/storage.py`
- Modify: `blog/views.py`
- Modify: `turboblog/settings.py`

**Interfaces:**
- Consumes: Railway's `AWS_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`, and `AWS_DEFAULT_REGION` variables.
- Produces: `store_uploaded_image(filename, payload, content_type) -> str` and `create_uploaded_image_download_url(filename) -> str`.

- [ ] **Step 1: Write the failing test**

  Add a Django test that enables private object storage, uploads an image, expects a stable `/assets/uploads/<key>` response URL, then requests that URL and expects an HTTP redirect to a generated presigned S3 URL.

- [ ] **Step 2: Run the focused test and verify RED**

  Run `python manage.py test blog.tests.RailwayBucketUploadTests -v 2` and expect failure because private bucket redirects are not implemented.

- [ ] **Step 3: Implement the minimal storage adapter**

  Add generic `OBJECT_STORAGE_*` settings with backward-compatible `R2_*` aliases, one S3 client factory, stable upload URLs for private buckets, and a signed GET URL helper. Update `frontend()` to redirect private upload requests while retaining local file serving and R2 public URLs.

- [ ] **Step 4: Verify GREEN**

  Re-run the focused test and then `python manage.py test blog -v 2`; both must pass.

### Task 2: Seed the Railway public URL

**Files:**
- Modify: `blog/tests.py`
- Modify: `blog/management/commands/seed_initial_data.py`

**Interfaces:**
- Consumes: `RAILWAY_PUBLIC_DOMAIN` or the existing `RENDER_EXTERNAL_HOSTNAME`.
- Produces: the production `SiteSetting.public_url` used by RSS, sitemap, and robots.

- [ ] **Step 1: Write the failing test**

  Add a test that sets `RAILWAY_PUBLIC_DOMAIN` and expects a fresh localhost site URL to become `https://<domain>`.

- [ ] **Step 2: Run the focused test and verify RED**

  Run `python manage.py test blog.tests.PublicUrlTests.test_seed_uses_railway_public_domain -v 2` and expect the localhost URL assertion to fail.

- [ ] **Step 3: Implement the minimal hostname fallback**

  Prefer `RAILWAY_PUBLIC_DOMAIN`, then `RENDER_EXTERNAL_HOSTNAME`, only when the stored URL is still the localhost default.

- [ ] **Step 4: Verify GREEN**

  Re-run the focused test and the complete Django test suite.

### Task 3: Document, deploy, and verify the zero-cost topology

**Files:**
- Modify: `README.md`
- Modify: `DEPLOYMENT.md`
- Verify: `railway.json`

**Interfaces:**
- Consumes: pushed GitHub commit, Neon connection string, generated Railway Bucket variables, generated Django secrets.
- Produces: a Railway deployment with `/`, `/api/health`, `/api/storage`, admin login, and upload persistence checks.

- [ ] **Step 1: Update deployment documentation**

  Make Railway Free + Neon + Railway Bucket the recommended path, list the exact variables, and document that private bucket objects are served through signed redirects.

- [ ] **Step 2: Run local verification**

  Run `python manage.py check`, `python manage.py test blog -v 2`, and `python scripts/test_django_backend.py`.

- [ ] **Step 3: Commit and push**

  Review `git diff`, commit only the scoped deployment changes, and push `master` to the existing `origin`.

- [ ] **Step 4: Create only Free Railway resources**

  Reuse the logged-in Free workspace, create the Django service from the GitHub repository and one Bucket, attach Neon and generated object-storage variables, generate a Railway domain, enable Serverless where available, and set the workspace hard usage limit to the free grant.

- [ ] **Step 5: Verify production behavior**

  Confirm `/api/health`, the homepage, `/api/storage` PostgreSQL status, admin login with the generated token, and an uploaded image request after deployment.
