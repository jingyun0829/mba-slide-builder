# 上线部署完整指南 (Deployment Guide)

把这个 app 放到公网,让别人通过链接和邀请码访问。一共 4 步,大概 30-45 分钟。

---

## 第一步:把代码推到 GitHub (10分钟)

Streamlit Community Cloud 只能从 GitHub 仓库部署。

### 1.1 注册 GitHub 账号

如果还没有,去 [github.com](https://github.com) 注册一个免费账号。

### 1.2 安装 git (如果电脑上还没装)

Mac: 打开终端 (Terminal),输入 `git --version`。如果提示要安装,跟着系统走就行。
Windows: 去 [git-scm.com](https://git-scm.com/download/win) 下载安装。

### 1.3 在 GitHub 上创建一个新仓库

1. 登录 GitHub,点右上角的 `+` → `New repository`。
2. **Repository name**: 比如 `mba-slide-builder`。
3. **Privacy**: 选 **Private** (推荐 — 你的代码不公开)。
4. 不要勾选 "Add README" / "Add .gitignore" — 我们已经有了。
5. 点 `Create repository`。
6. 复制页面上显示的仓库地址,形如 `https://github.com/YOUR_USERNAME/mba-slide-builder.git`。

### 1.4 在终端里把本地代码推上去

打开终端,`cd` 到项目目录:

```bash
cd "你的文件夹路径/mba-slide-builder"

# 初始化 git (只需要一次)
git init
git branch -M main

# 把所有非 ignore 的文件加进去
git add .
git status   # ← 检查一下,确认 .env 不在列表里!

# 第一次提交
git commit -m "Initial public deploy"

# 连到 GitHub 仓库
git remote add origin https://github.com/YOUR_USERNAME/mba-slide-builder.git

# 推上去
git push -u origin main
```

如果让你输入用户名密码:用 GitHub 用户名 + **Personal Access Token**(不是密码)。
没有 token 的话,去 [github.com/settings/tokens](https://github.com/settings/tokens) 生成一个,勾选 `repo` 权限。

### 1.5 验证

刷新 GitHub 仓库页面,应该能看到所有文件。**重点确认 `.env` 不在那里** — 如果在,立刻删除整个仓库重新弄。

---

## 第二步:部署到 Streamlit Community Cloud (10分钟)

### 2.1 注册 Streamlit Cloud

1. 去 [share.streamlit.io](https://share.streamlit.io)。
2. 点 `Sign in with GitHub` — 用刚才的 GitHub 账号登录。
3. 授权 Streamlit 读你的仓库。

### 2.2 创建 app

1. 点右上角 `New app` → `Deploy a public app from GitHub`。
2. **Repository**: 选 `YOUR_USERNAME/mba-slide-builder`。
3. **Branch**: `main`。
4. **Main file path**: `app.py`。
5. **App URL**: 自定义一段 (比如 `mba-slides`),最终 URL 是 `https://mba-slides.streamlit.app`。
6. **不要点 Deploy 还**,先点 `Advanced settings`。

### 2.3 配 Secrets (关键!)

在 Advanced settings 里有一个 **Secrets** 框。把这个粘进去 (替换成你自己的值):

```toml
ANTHROPIC_API_KEY = "sk-ant-你的真实key"
TAVILY_API_KEY = "tvly-你的真实key"
ELEVENLABS_API_KEY = "sk_你的真实key"

INVITE_CODE = "BETA2026"
MAX_DECKS_PER_USER = 3

# 可选:管理员后门,只有你知道
ADMIN_PASS = "dvora-secret-2026"
```

**重要**: 这些 secrets 只在 Streamlit Cloud 后台,不会出现在 GitHub 上。

### 2.4 Deploy

点 `Deploy!`。第一次部署需要 3-5 分钟 (装 Python 包)。完成后会自动跳转到你的 app URL。

### 2.5 测试

1. 打开你的 URL (比如 `https://mba-slides.streamlit.app`)。
2. 应该看到登录界面 — 输入 `BETA2026`。
3. 进去后应该看到 "📊 0/3 decks built · 3 remaining" 的 badge。
4. 试着完整跑一遍 (Stage 1 → Stage 4),看 deck 计数器有没有 +1。

---

## 第三步:发邀请链接 (5分钟)

### 简单办法:把链接 + 邀请码一起发

```
你好!

我做了一个 AI 生成商学院课件的工具,现在 beta 测试,想请你试一下:

链接: https://mba-slides.streamlit.app
邀请码: BETA2026

你可以生成最多 3 个完整的 deck。觉得好用想生成更多就回复我。

— Dvora
```

### 进阶办法:一键登录链接 (不用手动输码)

`?code=` 这个 URL 参数会自动登录。直接发:

```
https://mba-slides.streamlit.app/?code=BETA2026
```

用户点开就直接进去,不用输码。

⚠️ 缺点:链接被转发出去,任何拿到的人都能用。所以**只发给你信任的人**。

---

## 第四步 (可选):自定义域名 (15-20分钟)

Streamlit Cloud 免费版不直接支持自定义域名,但可以用 Cloudflare 免费代理实现。

### 4.1 买域名

去 [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/):

1. 注册 Cloudflare 账号 (免费)。
2. 在搜索框搜你想要的域名。推荐:
   - `mbaslides.com` / `profslides.com` / `coursebuilder.app`
   - 短而清晰的最好,大概 $10-15/年。
3. 买下来。

### 4.2 加到 Cloudflare

通常买完会自动加到你的 Cloudflare DNS 里。如果没有:在 Cloudflare 控制台 → `Add a Site`。

### 4.3 用 Cloudflare Worker 代理 Streamlit URL

在 Cloudflare 控制台:

1. 左边菜单 → `Workers & Pages` → `Create Worker`。
2. 名字随意,比如 `slides-proxy`。
3. 把默认代码替换成:

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = "mba-slides.streamlit.app";  // ← 你的 streamlit URL
    return fetch(new Request(url, request));
  }
};
```

4. 点 `Save and Deploy`。
5. 在 Worker 设置里 → `Settings` → `Triggers` → `Add Custom Domain`,填 `app.你的域名.com` (或者直接 `你的域名.com`)。

### 4.4 等 5-10 分钟 DNS 生效

打开 `https://app.你的域名.com` 应该看到你的 app。SSL 证书 Cloudflare 自动配好。

---

## 常见问题

### 修改代码后怎么更新线上版本?

```bash
git add .
git commit -m "改了 xxx"
git push
```

Streamlit Cloud 几秒后自动重新部署。

### 想换邀请码 / 提高额度?

Streamlit Cloud → 你的 app → `Settings` → `Secrets` → 改 `INVITE_CODE` 或 `MAX_DECKS_PER_USER` → `Save`。app 自动重启,新值生效。

### 某个用户用完了想给他续杯?

最简单:让他换个浏览器/无痕窗口访问。新浏览器 = 新 user_id = 重新 3 次。

正式办法:把 `MAX_DECKS_PER_USER` 调高 (比如 5),所有人都多 2 次。

### 怎么看谁在用?多少人用了?

Streamlit Cloud → app → `Manage app` → 右下 `Analytics` 能看流量趋势。

更详细的:看 app 容器里的 `usage_log.json` (但容器重启会清空,不是长期记录)。
要长期记录,以后可以接 Postgres / Google Sheets API。

### app 卡住了 / 慢

免费版 1GB RAM,同时 5+ 人用就会慢。
观察:Streamlit Cloud → `Manage app` → 看 logs。
解决:升级到付费版 ($20/月,16GB RAM),或者迁移到 Render/Railway。

### Secrets 改完不生效?

Streamlit Cloud → app → 右上 `⋮` → `Reboot app`。强制重启容器,secrets 一定会重新读。

---

## 成本预估

按当前设置 (3 decks/user, $0.25/deck):

| 用户数 | 最大成本 | 实际成本(约 30% 跑满) |
|--------|---------|----------------------|
| 10 人  | $7.5    | $2-3                  |
| 30 人  | $22.5   | $6-8                  |
| 100 人 | $75     | $20-25                |

加上 Streamlit Cloud (免费) + Cloudflare (免费) + 域名 ($10-15/年) = 总成本可控。

---

有问题随时打开 in-app 的 💬 Help 助手问,或者发邮件给我。

🚀 Have fun!
