# 让同学用上网页版：四种方案

按“从快到正式”排序。先选一种，不要同时折腾。

## 方案 A：同一 Wi-Fi / 热点（最快，5 分钟）

适合：同一个教室、宿舍、社团活动。

1. 查你的局域网 IP：

```powershell
ipconfig
```

找到“IPv4 地址”，例如 `192.168.1.23`。

2. 启动时监听所有网卡：

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

3. 允许 Windows 防火墙放行 8501（管理员 PowerShell 执行一次）：

```powershell
netsh advfirewall firewall add rule name="Streamlit 8501" dir=in action=allow protocol=TCP localport=8501
```

4. 同学连同一个 Wi-Fi，浏览器打开：

```
http://192.168.1.23:8501
```

**注意**：不少校园 Wi-Fi 开了“客户端隔离”，同学可能打不开。这时用手机热点，或换方案 B/C。

---

## 方案 B：临时公网链接（Cloudflare Tunnel，10 分钟）

适合：想让不在同一网络的同学临时用一下，但不想部署云服务器。

1. 安装 cloudflared：

```powershell
winget install --id Cloudflare.cloudflared
```

2. 先按方案 A 启动 Streamlit（或只在本机 `streamlit run app.py`）。

3. 开一个终端：

```powershell
cloudflared tunnel --url http://localhost:8501
```

它会输出一个 `https://xxxx.trycloudflare.com` 的地址，直接发给同学。

**注意**：

- 你的电脑必须一直开着，关掉终端链接就失效。
- 每次重启地址会变。
- 免费隧道不适合长期公开服务。

替代：`ngrok http 8501`，需要注册账号，但地址更稳定。

---

## 方案 C：Streamlit Community Cloud（推荐，长期公开）

适合：想让同学随时打开一个固定网址，不用你的电脑在线。

### 1. 准备可独立运行的文件夹

先进入 app 文件夹。下面两行是**示例**，`...` 不要原样复制，换成你电脑上的实际路径：

```powershell
$app = "C:\...\materials-compass-app"
$skill = "C:\Users\张清蕊\AppData\Roaming\CherryStudio\Data\Skills\materials-compass"
cd $app
python sync_skill.py --skill-dir $skill
```

如果自动检测能正常工作，也可以直接：

```powershell
cd $app
python sync_skill.py
```

确认目录里有 `skill_snapshot/`、`app.py`、`app_core.py`、`requirements.txt`。

### 2. 推到 GitHub

先创建一个空仓库，然后：

```powershell
git init
git add .
git commit -m "materials compass streamlit app"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 3. 部署

1. 打开 https://share.streamlit.io/
2. 用 GitHub 登录
3. New app → “Deploy a public app from GitHub”
4. 选择仓库、分支 `main`、主文件 `app.py`
5. Deploy

几分钟后得到一个 `https://<app-name>.streamlit.app` 的公开地址。

**注意**：

- 仓库必须是 public（免费版）。
- 不需要填 secrets。
- 免费实例长时间无人访问会休眠，同学第一次打开可能等几秒。
- 更新数据后：本地 `python sync_skill.py` → `git add/commit/push`，云端会自动重新部署。

---

## 方案 D：Hugging Face Spaces（备选，免费）

适合：GitHub/Streamlit Cloud 不方便时。

1. 打开 https://huggingface.co/new-space
2. SDK 选 **Streamlit**
3. 上传：
   - `app.py`
   - `app_core.py`
   - `requirements.txt`
   - `skill_snapshot/`
   - `.streamlit/config.toml`
4. Space 会自动构建，得到 `https://<user>-<space>.hf.space`。

---

## 方案 E：学校服务器 / VPS（长期、可控）

适合：学院/社团有服务器，想长期维护。

```bash
docker build -t materials-compass .
docker run -d --name materials-compass -p 8501:8501 materials-compass
```

然后用 Nginx 反代：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

再用 certbot 配 HTTPS。适合有运维基础的情况。

---

## 怎么发给同学

部署好之后，建议一次发三样东西：

1. **链接**：`https://...`
2. **一句话说明**：填 6 个问题，生成方向/择校/岗位报告，可下载 Markdown。
3. **二维码**：用草料二维码/微信自带工具把链接转成二维码，贴在群里或社团海报上。

第一次使用时可以补一句：

> 报告是决策辅助，不是录取承诺；学校/岗位的官网入口都在表里，记得点开核验。

---

## 隐私与维护

- App 不保存用户画像到数据库；每次生成用临时目录，进程结束即丢弃。
- 不要把姓名、学号、手机号填进去。
- 公开部署时，访问日志可能记录 IP；如果介意，用学校服务器自建。
- 更新 skill 数据后，务必重新运行 `python sync_skill.py`，否则网页用的还是旧快照。
- 每 6–12 个月检查一次 `last_verified`，尤其是招生目录和岗位。

---

## 常见问题

**`sync_skill.py` 报“该路径不存在”**
→ 先确认你在 app 文件夹里：

```powershell
Get-Location
Get-ChildItem
```

→ 再找 skill 文件夹：

```powershell
Get-ChildItem "$env:APPDATA\CherryStudio\Data\Skills" -Directory
```

→ 看到 `materials-compass` 后，用 `--skill-dir` 显式指定：

```powershell
python sync_skill.py --skill-dir "$env:APPDATA\CherryStudio\Data\Skills\materials-compass"
```

→ 如果 skill 被移动过，把上面的路径换成实际位置。脚本现在会自动尝试 `%APPDATA%`、用户目录和 app 同级的 `materials-compass`，但仍以 `--skill-dir` 为准。

**`ModuleNotFoundError: streamlit`**
→ `pip install -r requirements.txt`。

**页面提示“找不到 skill 文件”**
→ 在 app 目录运行 `python sync_skill.py`，或设置 `MATERIALS_COMPASS_SKILL_DIR`。

**局域网打不开**
→ 检查防火墙 8501、是否同一网段、校园 Wi-Fi 是否隔离客户端。

**Streamlit Cloud 构建失败**
→ 看构建日志；确认 `requirements.txt` 在根目录、`app.py` 是入口、`skill_snapshot/` 已提交。

**同学打开很慢**
→ 免费实例休眠后首次访问会慢；升级或换 VPS。
