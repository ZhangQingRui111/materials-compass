# 材料罗盘 · Streamlit 版

把 `materials-compass` skill 包装成一个网页：同学填 6 个问题，就能拿到方向匹配、考研冲稳保、岗位样本和 12 个月行动表。

## 运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

默认打开 http://localhost:8501。

想让同学一起用？看 [DEPLOY.md](DEPLOY.md)：同一 Wi-Fi、Cloudflare 临时公网、Streamlit Community Cloud、Hugging Face Spaces、学校服务器五种方案。

## Skill 从哪里来

App 本身不复制打分逻辑，它调用 skill 里的 `scripts/score.py` 和 `scripts/render_report.py`。查找顺序：

1. 环境变量 `MATERIALS_COMPASS_SKILL_DIR`
2. Cherry Studio 默认路径：`...\Data\Skills\materials-compass`
3. 本目录下的 `skill_snapshot/`（便携快照）

如果要把网页发给没有 Cherry Studio 的同学，先运行：

```bash
python sync_skill.py --skill-dir "C:\path\to\materials-compass"
```

它会自动尝试 `%APPDATA%\CherryStudio\Data\Skills\materials-compass`、用户目录和 app 同级的 `materials-compass`；如果都找不到，就用 `--skill-dir` 显式指定。它会把当前 skill 的 `scripts/`、`references/data/`、`report-template.md`、`sources.md` 复制到 `skill_snapshot/`。之后整个 `materials-compass-app/` 文件夹可以单独打包/上传。

## 目录

```
materials-compass-app/
├── app.py              # Streamlit 页面
├── app_core.py         # 调用 skill 的薄封装
├── sync_skill.py       # 把 skill 同步成便携快照
├── requirements.txt
├── skill_snapshot/     # 运行 sync_skill.py 后生成
└── README.md
```

## 部署到 Streamlit Community Cloud

1. 把 `materials-compass-app/` 推到 GitHub。
2. 在 Streamlit Cloud 新建 app，入口选 `app.py`。
3. 先确保仓库里有 `skill_snapshot/`（本地运行一次 `python sync_skill.py` 再提交）。
4. 不需要额外 secrets。

## 已知边界

- 匹配分是相对匹配，不是录取概率。
- 招生科目、导师、岗位每年变化；页面会给官网/研招入口，请自己核验。
- 薪资是招聘页面样本，不是平均值。
- 数据快照会过期；更新 skill 后重新运行 `sync_skill.py`。
