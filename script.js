const API_BASE_KEY = "turbo-blog-api-base";
const TOKEN_KEY = "turbo-blog-admin-token";
const defaultApiBase = window.location.origin;
const defaultLocalAdminToken = "dev-token";
const avatarPath = "/assets/avatar-blue-anime.png";

const state = {
  site: { title: "Turbo Blog", description: "记录代码、生活与灵感的个人博客。" },
  posts: [],
  currentPost: null,
  query: "",
  filter: "all",
  message: "",
  error: "",
  commentMessage: "",
  captcha: null,
  pendingComments: [],
  searchComposing: false,
  ai: {
    question: "",
    answer: "",
    sources: [],
    mode: "",
    model: "",
    loading: false,
    error: ""
  }
};

const app = document.querySelector("#app");

function apiBase() {
  const configured = window.TURBO_BLOG_CONFIG?.apiBase?.trim();
  if (configured) return configured.replace(/\/$/, "");

  const stored = localStorage.getItem(API_BASE_KEY);
  const staleLocalNodeApi =
    window.location.port === "5173" &&
    /^https?:\/\/(localhost|127\.0\.0\.1):4000$/i.test(stored || "");
  if (staleLocalNodeApi) {
    localStorage.removeItem(API_BASE_KEY);
    return defaultApiBase;
  }

  return stored || defaultApiBase;
}

function isLocalApiBase(value) {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(value);
}

function adminToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function apiHeaders() {
  const value = adminToken();
  return {
    "Content-Type": "application/json",
    ...(value ? { Authorization: `Bearer ${value}` } : {})
  };
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    ...options,
    headers: { ...apiHeaders(), ...(options.headers || {}) }
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

async function loginWithCredentials(payload) {
  const data = await request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  localStorage.setItem(TOKEN_KEY, data.token);
  return data;
}

async function logout() {
  await request("/api/auth/logout", { method: "POST", body: "{}" });
  localStorage.removeItem(TOKEN_KEY);
}

async function checkAdmin() {
  try {
    const data = await request("/api/auth/me");
    return Boolean(data.authenticated);
  } catch {
    return false;
  }
}

async function loadCaptcha() {
  const data = await request("/api/captcha");
  state.captcha = data.captcha;
}

async function loadPendingComments() {
  if (!adminToken()) {
    state.pendingComments = [];
    return;
  }
  try {
    const data = await request("/api/admin/comments?status=pending");
    state.pendingComments = data.comments;
  } catch {
    state.pendingComments = [];
  }
}

function syncEditorSettings(form) {
  const apiInput = form.querySelector("[data-setting='api-base']");
  const tokenInput = form.querySelector("[data-setting='token']");
  if (apiInput?.value.trim()) {
    localStorage.setItem(API_BASE_KEY, apiInput.value.trim().replace(/\/$/, ""));
  }
  if (tokenInput) {
    const value = tokenInput.value.trim();
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

function sanitizeMarkdownUrl(value) {
  const url = String(value || "").trim();
  if (!url) return "";
  if (/^(https?:|data:image\/(?:png|jpeg|jpg|gif|webp);base64,)/i.test(url)) return url;
  if (/^(\/|\.\/|\.\.\/|assets\/)/.test(url)) return url;
  return "";
}

function renderInlineMarkdown(text) {
  const codeTokens = [];
  let escaped = escapeHtml(text || "").replace(/`([^`]+)`/g, (_, code) => {
    const token = `@@CODE${codeTokens.length}@@`;
    codeTokens.push(`<code>${code}</code>`);
    return token;
  });

  escaped = escaped.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;)?\)/g, (_, alt, url, title) => {
    const safeUrl = sanitizeMarkdownUrl(url);
    if (!safeUrl) return _;
    const safeTitle = title ? ` title="${title}"` : "";
    return `<img src="${escapeHtml(safeUrl)}" alt="${alt}"${safeTitle} loading="lazy" />`;
  });

  escaped = escaped.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, url) => {
    const safeUrl = sanitizeMarkdownUrl(url);
    if (!safeUrl) return _;
    const target = /^https?:/i.test(safeUrl) ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a href="${escapeHtml(safeUrl)}"${target}>${label}</a>`;
  });

  escaped = escaped
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  codeTokens.forEach((html, index) => {
    escaped = escaped.replaceAll(`@@CODE${index}@@`, html);
  });

  return escaped;
}

function formatDate(value) {
  if (!value) return "未发布";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(new Date(value)).replaceAll("/", ".");
}

function categoryOf(post) {
  const tags = post.tags || [];
  if (tags.includes("技术")) return "tech";
  if (tags.includes("生活")) return "life";
  if (tags.includes("札记")) return "note";
  return "note";
}

function stripBlockquoteMarker(line) {
  return line.replace(/^>\s?/, "");
}

function markdownToHtml(markdown) {
  const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let inList = false;
  let inCode = false;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.trim().startsWith("```")) {
      if (inCode) {
        html.push("</code></pre>");
      } else {
        const language = line.trim().slice(3).trim().replace(/[^a-z0-9_-]/gi, "");
        const languageClass = language ? ` class="language-${escapeHtml(language)}"` : "";
        html.push(`<pre><code${languageClass}>`);
      }
      inCode = !inCode;
      continue;
    }

    if (inCode) {
      html.push(`${escapeHtml(line)}\n`);
      continue;
    }

    if (/^>\s?/.test(line)) {
      if (inList) html.push("</ul>");
      inList = false;
      const quoteLines = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quoteLines.push(stripBlockquoteMarker(lines[index]));
        index += 1;
      }
      index -= 1;
      html.push(`<blockquote>${markdownToHtml(quoteLines.join("\n"))}</blockquote>`);
      continue;
    }

    if (line.startsWith("## ")) {
      if (inList) html.push("</ul>");
      inList = false;
      html.push(`<h2>${renderInlineMarkdown(line.slice(3))}</h2>`);
      continue;
    }

    if (line.startsWith("# ")) {
      if (inList) html.push("</ul>");
      inList = false;
      html.push(`<h2>${renderInlineMarkdown(line.slice(2))}</h2>`);
      continue;
    }

    if (line.startsWith("- ")) {
      if (!inList) html.push("<ul>");
      inList = true;
      html.push(`<li>${renderInlineMarkdown(line.slice(2))}</li>`);
      continue;
    }

    if (inList) html.push("</ul>");
    inList = false;
    if (line.trim()) html.push(`<p>${renderInlineMarkdown(line)}</p>`);
  }

  if (inList) html.push("</ul>");
  if (inCode) html.push("</code></pre>");
  return html.join("");
}

function go(route) {
  window.history.pushState({}, "", route);
  navigate();
}

async function loadSite() {
  try {
    state.site = await request("/api/site");
    document.title = state.site.title;
  } catch {
    state.site = { title: "Turbo Blog", description: "记录代码、生活与灵感的个人博客。" };
  }
}

async function loadPosts(includeDrafts = false) {
  const q = state.query ? `&q=${encodeURIComponent(state.query)}` : "";
  const status = includeDrafts ? "all" : "published";
  const data = await request(`/api/posts?status=${status}${q}`);
  state.posts = data.posts;
}

async function loadPost(slug) {
  const data = await request(`/api/posts/${encodeURIComponent(decodePathPart(slug))}`);
  state.currentPost = data.post;
  document.title = `${data.post.title} - ${state.site.title}`;
}

async function askAi(question) {
  const data = await request("/api/ai/ask", {
    method: "POST",
    body: JSON.stringify({ question })
  });
  state.ai.answer = data.answer || "";
  state.ai.sources = data.sources || [];
  state.ai.mode = data.mode || "";
  state.ai.model = data.model || "";
}

function decodePathPart(value) {
  try {
    return decodeURIComponent(String(value || ""));
  } catch {
    return String(value || "");
  }
}

function layout(content, active = "home") {
  return `
    <header class="site-header">
      <div class="site-header-inner">
        <button class="brand link-button" data-route="/" aria-label="Turbo Blog 首页">
          <img class="brand-avatar" src="${avatarPath}" alt="蓝色头发二次元女孩头像" />
          <span class="brand-text">${escapeHtml(state.site.title)}</span>
        </button>
        <nav class="nav-links" aria-label="主导航">
          <button class="link-button ${active === "home" ? "active" : ""}" data-route="/">文章</button>
          <button class="link-button ${active === "editor" ? "active" : ""}" data-route="/editor">写作</button>
          <a href="#about">关于</a>
        </nav>
      </div>
    </header>
    <main id="top">${content}</main>
    <footer class="site-footer">
      <span>© 2026 Turbo Blog</span>
      <button class="link-button" data-route="/">返回首页</button>
    </footer>
  `;
}

function hero() {
  return `
    <section class="hero" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Personal Blog</p>
        <h1 id="hero-title">写下正在发生的想法。</h1>
        <p class="hero-lead">这里可以放你的技术文章、读书笔记、项目复盘和生活片段。现在它已经融合为前后端分离博客，可以在网页端写作、编辑和接收评论。</p>
        <div class="hero-actions">
          <button class="button primary" data-scroll="#posts">阅读文章</button>
          <button class="button ghost" data-route="/editor">写新博客</button>
        </div>
      </div>
      <div class="profile-panel" aria-label="博客作者信息">
        <img class="profile-avatar" src="${avatarPath}" alt="蓝色头发二次元女孩头像" />
        <div>
          <p class="profile-name">Turbo</p>
          <p class="profile-line">Code / Notes / Life</p>
        </div>
      </div>
    </section>
  `;
}

function aiAssistantPanel() {
  const sources = state.ai.sources.length
    ? state.ai.sources.map((source) => `
      <button class="ai-source" type="button" data-route="/post/${escapeHtml(source.slug)}">
        <span>${escapeHtml(source.title)}</span>
        <small>${escapeHtml(source.passages?.[0]?.label || "相关片段")}</small>
      </button>
    `).join("")
    : `<div class="ai-empty-source">等待引用博客</div>`;
  const output = state.ai.loading
    ? "正在从你的博客里查找相关内容..."
    : state.ai.error || state.ai.answer || "你问一个问题后，我会在你的已发布博客里找答案，并把来源列出来。";
  const aiStatus = state.ai.model
    ? `RAG · ${state.ai.model}`
    : state.ai.mode === "local-search" ? "本地检索" : "来自已发布博客";
  return `
    <section class="ai-assistant" aria-labelledby="ai-title">
      <div class="ai-companion-icon" aria-hidden="true">
        <img src="${avatarPath}" alt="蓝色头发二次元女孩头像" />
        <span>AI</span>
      </div>
      <div class="ai-panel-main">
        <div class="ai-copy">
          <p class="eyebrow">Local AI</p>
          <h3 id="ai-title">博客知识小助手</h3>
          <div class="ai-pills" aria-label="AI 写作能力">
            <span>本地检索</span>
            <span>引用来源</span>
            <span>轻量部署</span>
          </div>
        </div>
        <div class="ai-chat-grid">
          <form class="ai-box" data-action="ai-ask">
            <label class="field">
              <span>你的问题</span>
              <textarea name="question" rows="3" maxlength="300" placeholder="例如：ROS2 参数怎么动态修改？">${escapeHtml(state.ai.question)}</textarea>
            </label>
            <button class="button primary" type="submit" ${state.ai.loading ? "disabled" : ""}>询问</button>
          </form>
          <section class="ai-output" aria-live="polite">
            <div class="ai-output-head">
              <span>回答</span>
              <small>${escapeHtml(aiStatus)}</small>
            </div>
            <p>${escapeHtml(output)}</p>
            <div class="ai-sources">${sources}</div>
          </section>
        </div>
      </div>
    </section>
  `;
}

function renderHome() {
  const filtered = state.posts.filter((post) => {
    const filterMatches = state.filter === "all" || categoryOf(post) === state.filter;
    const text = `${post.title} ${post.slug} ${post.excerpt} ${(post.tags || []).join(" ")}`.toLowerCase();
    return filterMatches && text.includes(state.query.toLowerCase());
  });

  const cards = filtered.length
    ? filtered.map((post) => `
      <article class="post-card" data-category="${categoryOf(post)}" data-route="/post/${escapeHtml(post.slug)}" tabindex="0" role="link" aria-label="阅读 ${escapeHtml(post.title)}">
        <div class="post-meta">
          <span>${escapeHtml((post.tags || [])[0] || "札记")}</span>
          <time datetime="${escapeHtml(post.publishedAt || post.createdAt)}">${formatDate(post.publishedAt || post.createdAt)}</time>
        </div>
        <h3><button class="card-title" data-route="/post/${escapeHtml(post.slug)}">${escapeHtml(post.title)}</button></h3>
        <p>${escapeHtml(post.excerpt || "没有摘要")}</p>
        <div class="card-bottom">
          <span>${post.commentCount} 条评论</span>
        </div>
      </article>
    `).join("")
    : `<div class="empty">还没有匹配的文章。</div>`;
  const countText = state.query || state.filter !== "all"
    ? `匹配 ${filtered.length} / ${state.posts.length} 篇`
    : `共 ${state.posts.length} 篇文章`;

  app.innerHTML = layout(`
    ${hero()}
    <section class="section rag-section" id="rag" aria-labelledby="rag-title">
      <div class="module-heading">
        <div>
          <p class="eyebrow">RAG Assistant</p>
          <h2 id="rag-title">博客知识问答</h2>
        </div>
      </div>
      ${aiAssistantPanel()}
      <p class="rag-note">先检索你的已发布博客，再用模型或本地检索生成回答，并给出来源文章。</p>
    </section>
    <section class="section posts-section" id="posts" aria-labelledby="posts-title">
      <div class="posts-head">
        <div class="section-heading">
          <p class="eyebrow">Latest Posts</p>
          <h2 id="posts-title">近期文章</h2>
        </div>
        <span class="post-count">${escapeHtml(countText)}</span>
      </div>
      <section class="posts-toolbar" aria-label="文章筛选">
        <label class="post-search">
          <span class="search-label">搜索文章</span>
          <span class="search-box">
            <input id="post-search" type="text" placeholder="标题、摘要、标签" value="${escapeHtml(state.query)}" />
            <button class="search-clear" type="button" data-action="clear-search" aria-label="清空搜索" ${state.query ? "" : "hidden"}>×</button>
          </span>
        </label>
        <div class="tag-filters" aria-label="分类">
          <button class="tag ${state.filter === "all" ? "active" : ""}" type="button" data-filter="all">全部</button>
          <button class="tag ${state.filter === "tech" ? "active" : ""}" type="button" data-filter="tech">技术</button>
          <button class="tag ${state.filter === "life" ? "active" : ""}" type="button" data-filter="life">生活</button>
          <button class="tag ${state.filter === "note" ? "active" : ""}" type="button" data-filter="note">札记</button>
        </div>
      </section>
      <div class="post-grid">${cards}</div>
    </section>
    <section class="section note-band" id="notes" aria-labelledby="notes-title">
      <div>
        <p class="eyebrow">Notes</p>
        <h2 id="notes-title">短札</h2>
      </div>
      <ul class="note-list">
        <li>网页端已经可以写新博客和修改已有博客。</li>
        <li>每篇文章都支持访客评论。</li>
        <li>上线后可提交 sitemap，让搜索引擎发现文章。</li>
      </ul>
    </section>
    <section class="section about" id="about" aria-labelledby="about-title">
      <div>
        <p class="eyebrow">About</p>
        <h2 id="about-title">关于这个博客</h2>
      </div>
      <p>这是融合后的 Turbo Blog：保留原静态站的视觉风格和头像，同时加入独立后端 API、文章写作编辑、评论、RSS 与 sitemap。</p>
    </section>
  `);
}

function renderHomeWithSearchFocus(cursor) {
  renderHome();
  const searchInput = document.querySelector("#post-search");
  if (!searchInput) return;
  searchInput.focus();
  const nextCursor = Math.min(cursor ?? searchInput.value.length, searchInput.value.length);
  searchInput.setSelectionRange(nextCursor, nextCursor);
}

function renderPost() {
  const post = state.currentPost;
  const captcha = state.captcha;
  const comments = (post.comments || []).length
    ? post.comments.map((comment) => `
      <article class="comment">
        <div class="comment-head">
          <strong>${escapeHtml(comment.author)} · ${formatDate(comment.createdAt)}</strong>
        </div>
        <p>${escapeHtml(comment.content)}</p>
      </article>
    `).join("")
    : `<div class="empty">还没有评论。</div>`;

  app.innerHTML = layout(`
    <section class="section article-list">
      <article class="article article-detail">
        <button class="mini-button" data-route="/">返回首页</button>
        <p class="post-meta single">
          <span>${escapeHtml((post.tags || [])[0] || "札记")}</span>
          <time datetime="${escapeHtml(post.publishedAt || post.createdAt)}">${formatDate(post.publishedAt || post.createdAt)}</time>
        </p>
        <h1>${escapeHtml(post.title)}</h1>
        <div class="article-body">${markdownToHtml(post.content)}</div>
        <div class="article-actions">
          <button class="button ghost" data-scroll="#comments">查看评论（${(post.comments || []).length}）</button>
        </div>
      </article>
      <section class="comments-panel" id="comments">
        <div class="section-heading">
          <p class="eyebrow">Comments</p>
          <h2>评论</h2>
        </div>
        <div class="comments">${comments}</div>
        <p class="status-line">${escapeHtml(state.commentMessage)}</p>
        <form class="comment-form" data-action="comment">
          <label class="field">
            <span>昵称</span>
            <input name="author" maxlength="40" placeholder="匿名" />
          </label>
          <label class="field">
            <span>评论</span>
            <textarea name="content" required minlength="2" placeholder="写下你的想法"></textarea>
          </label>
          <input type="hidden" name="captchaId" value="${escapeHtml(captcha?.id || "")}" />
          <label class="field">
            <span>验证码：${escapeHtml(captcha?.question || "正在生成")}</span>
            <input name="captchaAnswer" required inputmode="numeric" placeholder="输入计算结果" />
          </label>
          <button class="button primary" type="submit">提交评论</button>
        </form>
      </section>
    </section>
  `);
}

function emptyPost() {
  return { id: "", title: "", slug: "", excerpt: "", content: "", tags: ["技术"], status: "published" };
}

function adminLoginModal(route = "/editor", message = "") {
  return `
    <div class="admin-modal-backdrop" role="presentation">
      <section class="admin-modal" role="dialog" aria-modal="true" aria-labelledby="admin-login-title">
        <button class="modal-close" type="button" data-action="close-admin-modal" aria-label="关闭登录窗口">×</button>
        <div class="section-heading">
          <p class="eyebrow">Admin Only</p>
          <h2 id="admin-login-title">管理员登录</h2>
        </div>
        <p class="auth-copy">通过管理员认证后，才能进入写作页面进行写文章、编辑文章和删除内容。</p>
        <form class="editor-form" data-action="admin-login" data-pending-route="${escapeHtml(route)}">
          <label class="field">
            <span>用户名</span>
            <input name="username" required placeholder="admin" autocomplete="username" />
          </label>
          <label class="field">
            <span>密码</span>
            <input name="password" required type="password" placeholder="输入管理员密码" autocomplete="current-password" />
          </label>
          <p class="status-line modal-status">${escapeHtml(message)}</p>
          <button class="button primary" type="submit">进入写作后台</button>
        </form>
      </section>
    </div>
  `;
}

function showAdminLoginModal(route = "/editor", message = "") {
  document.querySelector(".admin-modal-backdrop")?.remove();
  app.insertAdjacentHTML("beforeend", adminLoginModal(route, message));
  requestAnimationFrame(() => {
    document.querySelector(".admin-modal input[name='username']")?.focus();
  });
}

function closeAdminLoginModal() {
  document.querySelector(".admin-modal-backdrop")?.remove();
}

function renderEditor(post = emptyPost()) {
  const postComments = post.id
    ? (post.comments || []).length
      ? post.comments.map((comment) => `
        <article class="review-item">
          <strong>${escapeHtml(comment.author)} · ${formatDate(comment.createdAt)}</strong>
          <p>${escapeHtml(comment.content)}</p>
          <div class="review-actions">
            <span class="review-status">${comment.approved ? "已展示" : "待审核"}</span>
            <button class="mini-button danger" data-delete-comment="${escapeHtml(comment.id)}">删除评论</button>
          </div>
        </article>
      `).join("")
      : `<div class="empty">这篇文章暂无评论。</div>`
    : `<div class="empty">选择一篇已有文章后，可管理该文章下的评论。</div>`;
  const pending = state.pendingComments.length
    ? state.pendingComments.map((comment) => `
      <article class="review-item">
        <strong>${escapeHtml(comment.author)} · ${escapeHtml(comment.postTitle)}</strong>
        <p>${escapeHtml(comment.content)}</p>
        <div class="review-actions">
          <button class="mini-button" data-comment-action="approved" data-comment-id="${escapeHtml(comment.id)}">通过</button>
          <button class="mini-button" data-comment-action="rejected" data-comment-id="${escapeHtml(comment.id)}">拒绝</button>
          <button class="mini-button danger" data-delete-comment="${escapeHtml(comment.id)}">删除</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty">暂无待审核评论。</div>`;

  const side = state.posts.length
    ? state.posts.map((item) => `
      <div class="draft-item-wrap">
        <button class="draft-item" data-route="/editor/${escapeHtml(item.slug)}">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.status)} · ${formatDate(item.updatedAt)}</span>
        </button>
        <button class="comment-delete" data-delete-post="${escapeHtml(item.id)}" data-title="${escapeHtml(item.title)}">删除</button>
      </div>
    `).join("")
    : `<div class="empty">输入管理员令牌后可加载草稿。</div>`;

  app.innerHTML = layout(`
    <section class="section editor-layout">
      <div class="editor-panel">
        <div class="section-heading">
          <p class="eyebrow">Write</p>
          <h1>${post.id ? "编辑博客" : "写新博客"}</h1>
        </div>
        <form class="editor-form" data-action="save-post" data-id="${escapeHtml(post.id || post.slug || "")}">
          <div class="form-grid">
            <label class="field">
              <span>用户名</span>
              <input name="username" placeholder="admin" autocomplete="username" />
            </label>
            <label class="field">
              <span>密码</span>
              <input name="password" type="password" placeholder="本地默认 dev-token" autocomplete="current-password" />
            </label>
            <label class="field">
      <span>管理员令牌</span>
              <input value="${escapeHtml(adminToken())}" placeholder="本地默认 dev-token" data-setting="token" autocomplete="off" />
            </label>
            <label class="field">
              <span>API 地址</span>
              <input value="${escapeHtml(apiBase())}" data-setting="api-base" />
            </label>
          </div>
          <label class="field">
            <span>标题</span>
            <input name="title" required value="${escapeHtml(post.title)}" />
          </label>
          <label class="field">
            <span>摘要</span>
            <input name="excerpt" value="${escapeHtml(post.excerpt)}" />
          </label>
          <div class="form-grid">
            <label class="field">
              <span>URL Slug</span>
              <input name="slug" value="${escapeHtml(post.slug)}" />
            </label>
            <label class="field">
              <span>状态</span>
              <select name="status">
                <option value="published" ${post.status === "published" ? "selected" : ""}>发布</option>
                <option value="draft" ${post.status === "draft" ? "selected" : ""}>草稿</option>
              </select>
            </label>
          </div>
          <label class="field">
            <span>标签</span>
            <input name="tags" value="${escapeHtml((post.tags || []).join(", "))}" placeholder="技术, 札记" />
          </label>
          <label class="field">
            <span>正文 Markdown</span>
            <div class="markdown-toolbar" aria-label="Markdown 工具栏">
              <button class="mini-button" type="button" data-markdown-action="bold">加粗</button>
              <button class="mini-button" type="button" data-markdown-action="quote">引用</button>
              <button class="mini-button" type="button" data-markdown-action="code">代码块</button>
              <button class="mini-button" type="button" data-markdown-action="image-url">图片链接</button>
              <button class="mini-button" type="button" data-markdown-action="image-file">上传图片</button>
              <input class="image-upload-input" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden />
            </div>
            <textarea class="content-input" name="content" required>${escapeHtml(post.content)}</textarea>
          </label>
          <p class="status-line">${escapeHtml(state.message || state.error)}</p>
          <button class="button ghost" type="button" data-action="login">登录会话</button>
          <button class="button ghost" type="button" data-action="logout">退出登录</button>
          <button class="button primary" type="submit">保存文章</button>
        </form>
      </div>
      <aside class="draft-list">
        <button class="button primary" data-route="/editor">新文章</button>
        ${side}
        <section class="review-panel">
          <h2>当前文章评论</h2>
          ${postComments}
        </section>
        <section class="review-panel">
          <h2>评论审核</h2>
          ${pending}
        </section>
      </aside>
    </section>
  `, "editor");
}

function contentTextarea() {
  return document.querySelector(".content-input");
}

function insertIntoTextarea(textarea, value, selectStartOffset = 0, selectEndOffset = 0) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  textarea.value = `${before}${value}${after}`;
  const nextStart = start + selectStartOffset;
  const nextEnd = start + (selectEndOffset || value.length);
  textarea.focus();
  textarea.setSelectionRange(nextStart, nextEnd);
}

function wrapTextareaSelection(textarea, before, after, placeholder) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selected = textarea.value.slice(start, end) || placeholder;
  const value = `${before}${selected}${after}`;
  insertIntoTextarea(textarea, value, before.length, before.length + selected.length);
}

function quoteTextareaSelection(textarea) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selected = textarea.value.slice(start, end) || "引用内容";
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  const leadingBreak = before && !before.endsWith("\n") ? "\n" : "";
  const trailingBreak = after && !after.startsWith("\n") ? "\n" : "";
  const quote = selected
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line ? `> ${line}` : ">")
    .join("\n");
  const value = `${leadingBreak}${quote}${trailingBreak}`;
  const placeholderAt = value.indexOf("引用内容");
  const selectStart = placeholderAt >= 0 ? placeholderAt : leadingBreak.length;
  const selectEnd = placeholderAt >= 0 ? placeholderAt + "引用内容".length : leadingBreak.length + quote.length;
  insertIntoTextarea(textarea, value, selectStart, selectEnd);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("图片读取失败"));
    reader.readAsDataURL(file);
  });
}

async function uploadImageFile(file) {
  if (!file || !file.type.startsWith("image/")) throw new Error("请选择图片文件");
  const data = await readFileAsDataUrl(file);
  return request("/api/uploads", {
    method: "POST",
    body: JSON.stringify({
      name: file.name,
      type: file.type,
      data
    })
  });
}

function bindEvents() {
  app.addEventListener("click", async (event) => {
    const markdownButton = event.target.closest("[data-markdown-action]");
    if (markdownButton) {
      const textarea = contentTextarea();
      const action = markdownButton.dataset.markdownAction;
      if (action === "bold") {
        wrapTextareaSelection(textarea, "**", "**", "核心");
      } else if (action === "quote") {
        quoteTextareaSelection(textarea);
      } else if (action === "code") {
        wrapTextareaSelection(textarea, "\n```python\n", "\n```\n", "print(\"hello\")");
      } else if (action === "image-url") {
        const url = window.prompt("输入图片地址，例如 /assets/avatar-blue-anime.png 或 https://example.com/image.png");
        if (url) insertIntoTextarea(textarea, `\n![图片说明](${url.trim()})\n`, 3, 7);
      } else if (action === "image-file") {
        markdownButton.closest(".field")?.querySelector(".image-upload-input")?.click();
      }
      return;
    }

    const deletePost = event.target.closest("[data-delete-post]");
    if (deletePost) {
      event.stopPropagation();
      const title = deletePost.dataset.title || "这篇文章";
      if (!window.confirm(`确定删除「${title}」吗？这会同时删除文章下的评论。`)) return;
      try {
        await request(`/api/posts/${deletePost.dataset.deletePost}`, { method: "DELETE" });
        state.message = "文章已删除。";
        state.error = "";
        state.currentPost = null;
        if (window.location.pathname.startsWith("/editor")) {
          await loadPosts(true);
          await loadPendingComments();
          renderEditor();
        } else {
          await loadPosts(false);
          go("/");
        }
      } catch (error) {
        state.error = error.message;
        state.message = "";
        if (window.location.pathname.startsWith("/editor")) renderEditor(state.currentPost || emptyPost());
        else if (state.currentPost) renderPost();
        else renderEditor();
      }
      return;
    }

    const deleteComment = event.target.closest("[data-delete-comment]");
    if (deleteComment) {
      event.stopPropagation();
      if (!window.confirm("确定删除这条评论吗？")) return;
      try {
        await request(`/api/admin/comments/${deleteComment.dataset.deleteComment}`, { method: "DELETE" });
        state.message = "评论已删除。";
        state.error = "";
        if (state.currentPost?.slug && window.location.pathname.startsWith("/editor")) {
          await loadPost(state.currentPost.slug);
          await loadPendingComments();
          renderEditor(state.currentPost);
        } else if (state.currentPost?.slug && window.location.pathname.startsWith("/post/")) {
          state.commentMessage = "评论已删除。";
          await loadPost(state.currentPost.slug);
          await loadCaptcha();
          renderPost();
        } else {
          await loadPendingComments();
          renderEditor();
        }
      } catch (error) {
        state.error = error.message;
        state.message = "";
        if (state.currentPost?.slug && window.location.pathname.startsWith("/editor")) {
          renderEditor(state.currentPost);
        } else if (state.currentPost?.slug && window.location.pathname.startsWith("/post/")) {
          state.commentMessage = `删除失败：${error.message}`;
          renderPost();
        } else {
          renderEditor();
        }
      }
      return;
    }

    const login = event.target.closest("[data-action='login']");
    if (login) {
      const form = login.closest("form");
      const formData = form ? Object.fromEntries(new FormData(form).entries()) : {};
      const tokenInput = form?.querySelector("[data-setting='token']");
      const tokenValue = tokenInput?.value.trim() || adminToken();
      const payload = formData.username && formData.password
        ? { username: formData.username, password: formData.password }
        : { token: tokenValue };
      try {
        const data = await loginWithCredentials(payload);
        state.message = `登录成功：${data.user?.username || "admin"}，会话有效期至 ${formatDate(data.expiresAt)}。`;
        state.error = "";
        await loadPosts(true);
        await loadPendingComments();
        const slug = decodePathPart(window.location.pathname.split("/")[2]);
        if (window.location.pathname.startsWith("/editor") && slug) {
          await loadPost(slug);
          renderEditor(state.currentPost);
        } else {
          state.currentPost = null;
          renderEditor();
        }
      } catch (error) {
        state.error = error.message;
        state.message = "";
        showAdminLoginModal(window.location.pathname.startsWith("/editor") ? window.location.pathname : "/editor", "登录失败：用户名或密码不正确。");
      }
      return;
    }

    const closeAdminModal = event.target.closest("[data-action='close-admin-modal']");
    if (closeAdminModal) {
      closeAdminLoginModal();
      if (window.location.pathname.startsWith("/editor")) go("/");
      return;
    }

    const logoutButton = event.target.closest("[data-action='logout']");
    if (logoutButton) {
      try {
        await logout();
        state.message = "已退出登录。";
        state.error = "";
        state.pendingComments = [];
        state.currentPost = null;
      } catch (error) {
        state.error = error.message;
        state.message = "";
      }
      await loadPosts(false);
      renderHome();
      showAdminLoginModal("/editor");
      return;
    }

    const review = event.target.closest("[data-comment-action]");
    if (review) {
      await request(`/api/admin/comments/${review.dataset.commentId}`, {
        method: "PUT",
        body: JSON.stringify({ status: review.dataset.commentAction })
      });
      state.message = review.dataset.commentAction === "approved" ? "评论已通过。" : "评论已拒绝。";
      await loadPendingComments();
      if (state.currentPost?.slug) {
        await loadPost(state.currentPost.slug);
        renderEditor(state.currentPost);
      } else {
        renderEditor();
      }
      return;
    }

    const route = event.target.closest("[data-route]");
    if (route) {
      if (route.dataset.route?.startsWith("/editor") && !(await checkAdmin())) {
        showAdminLoginModal(route.dataset.route);
        return;
      }
      go(route.dataset.route);
      return;
    }

    const scroll = event.target.closest("[data-scroll]");
    if (scroll) {
      document.querySelector(scroll.dataset.scroll)?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    const clearSearch = event.target.closest("[data-action='clear-search']");
    if (clearSearch) {
      state.query = "";
      renderHomeWithSearchFocus(0);
      return;
    }

    const filter = event.target.closest("[data-filter]");
    if (filter) {
      state.filter = filter.dataset.filter;
      renderHome();
    }
  });

  app.addEventListener("change", async (event) => {
    if (!event.target.matches(".image-upload-input")) return;
    const input = event.target;
    const file = input.files?.[0];
    const textarea = contentTextarea();
    const form = input.closest("form");
    const status = form?.querySelector(".status-line");

    try {
      if (form) syncEditorSettings(form);
      if (status) status.textContent = "图片上传中...";
      const data = await uploadImageFile(file);
      insertIntoTextarea(textarea, `\n![${file.name.replace(/\.[^.]+$/, "")}](${data.image.url})\n`);
      if (status) status.textContent = "图片已上传并插入正文。";
    } catch (error) {
      if (status) status.textContent = `图片上传失败：${error.message}`;
    } finally {
      input.value = "";
    }
  });

  app.addEventListener("keydown", (event) => {
    const card = event.target.closest(".post-card[data-route]");
    if (!card || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    go(card.dataset.route);
  });

  app.addEventListener("compositionstart", (event) => {
    if (event.target.id === "post-search") {
      state.searchComposing = true;
    }
  });

  app.addEventListener("compositionend", (event) => {
    if (event.target.id === "post-search") {
      state.searchComposing = false;
      state.query = event.target.value;
      renderHomeWithSearchFocus(event.target.value.length);
    }
  });

  app.addEventListener("input", async (event) => {
    if (event.target.id === "post-search") {
      const cursor = event.target.selectionStart ?? event.target.value.length;
      state.query = event.target.value;
      if (!state.searchComposing) {
        renderHomeWithSearchFocus(cursor);
      }
    }

    if (event.target.matches("[data-setting='token']")) {
      localStorage.setItem(TOKEN_KEY, event.target.value);
    }

    if (event.target.matches("[data-setting='api-base']")) {
      localStorage.setItem(API_BASE_KEY, event.target.value.replace(/\/$/, ""));
    }
  });

  app.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;

    if (form.matches("[data-action='admin-login']")) {
      const data = Object.fromEntries(new FormData(form).entries());
      const pendingRoute = form.dataset.pendingRoute || "/editor";
      const status = form.querySelector(".modal-status");
      try {
        if (status) status.textContent = "正在验证管理员身份...";
        await loginWithCredentials({
          username: String(data.username || "").trim(),
          password: String(data.password || "")
        });
        closeAdminLoginModal();
        state.message = "登录成功。";
        state.error = "";
        window.history.pushState({}, "", pendingRoute);
        await navigate();
      } catch (error) {
        if (status) status.textContent = "登录失败：用户名或密码不正确。";
      }
      return;
    }

    if (form.matches("[data-action='ai-ask']")) {
      const question = String(new FormData(form).get("question") || "").trim();
      if (!question) {
        state.ai = { question: "", answer: "", sources: [], mode: "", model: "", loading: false, error: "先写一个问题。" };
        renderHome();
        return;
      }
      state.ai = { question, answer: "", sources: [], mode: "", model: "", loading: true, error: "" };
      renderHome();
      try {
        await askAi(question);
        state.ai.loading = false;
        state.ai.error = "";
      } catch (error) {
        state.ai.loading = false;
        state.ai.answer = "";
        state.ai.sources = [];
        state.ai.mode = "";
        state.ai.model = "";
        state.ai.error = `回答失败：${error.message}`;
      }
      renderHome();
      return;
    }

    if (form.matches("[data-action='comment']")) {
      try {
        const body = Object.fromEntries(new FormData(form).entries());
        const data = await request(`/api/posts/${state.currentPost.slug}/comments`, {
          method: "POST",
          body: JSON.stringify(body)
        });
        state.commentMessage = data.message || "评论已提交。";
        await loadPost(state.currentPost.slug);
        await loadCaptcha();
        renderPost();
      } catch (error) {
        state.commentMessage = error.message;
        await loadCaptcha();
        renderPost();
      }
    }

    if (form.matches("[data-action='save-post']")) {
      try {
        syncEditorSettings(form);
        const data = Object.fromEntries(new FormData(form).entries());
        data.tags = String(data.tags || "").split(",").map((tag) => tag.trim()).filter(Boolean);
        const id = form.dataset.id;
        const result = await request(id ? `/api/posts/${id}` : "/api/posts", {
          method: id ? "PUT" : "POST",
          body: JSON.stringify(data)
        });
        state.message = "已保存。";
        state.error = "";
        await loadPosts(true);
        state.currentPost = result.post;
        renderEditor(result.post);
      } catch (error) {
        state.error = error.message.includes("Unauthorized")
          ? "保存失败：管理员令牌不正确。本地开发默认填写 dev-token；上线后请填写后端 ADMIN_TOKEN。"
          : error.message;
        state.message = "";
        renderEditor();
      }
    }
  });
}

async function navigate() {
  const route = window.location.pathname || "/";
  state.message = "";
  state.error = "";

  try {
    if (route.startsWith("/post/")) {
      await loadPost(decodePathPart(route.split("/").pop()));
      await loadCaptcha();
      renderPost();
      return;
    }

    if (route.startsWith("/editor")) {
      if (!(await checkAdmin())) {
        state.currentPost = null;
        state.pendingComments = [];
        document.title = state.site.title;
        await loadPosts(false);
        renderHome();
        showAdminLoginModal(route);
        return;
      }
      await loadPosts(Boolean(adminToken()));
      await loadPendingComments();
      const slug = decodePathPart(route.split("/")[2]);
      if (slug) {
        await loadPost(slug);
        renderEditor(state.currentPost);
      } else {
        state.currentPost = null;
        renderEditor();
      }
      return;
    }

    document.title = state.site.title;
    await loadPosts(false);
    renderHome();
  } catch (error) {
    app.innerHTML = layout(`<section class="section"><div class="empty">${escapeHtml(error.message)}</div></section>`);
  }
}

window.addEventListener("popstate", navigate);

loadSite().then(() => {
  bindEvents();
  navigate();
});
