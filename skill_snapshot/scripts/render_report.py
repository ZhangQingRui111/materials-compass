#!/usr/bin/env python3
"""Render a Markdown report from score.json and the report template.

Usage:
    python scripts/render_report.py --profile profile.json --score score.json \
        --template references/report-template.md --out report.md
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def md_escape(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def is_stale(last_verified: str, generated_on: str) -> bool:
    try:
        then = datetime.strptime(last_verified, "%Y-%m-%d").date()
        now = datetime.strptime(generated_on, "%Y-%m-%d").date()
        return (now - then).days > 365
    except (TypeError, ValueError):
        return True


def track_table(tracks: list[dict]) -> str:
    lines = ["| Track | 匹配分 | 为什么 | 风险 |", "|---|---:|---|---|"]
    for item in tracks:
        lines.append(
            f"| {md_escape(item['name'])} | {item['score']} | {md_escape(item['reason'])} | {md_escape(item['risk'])} |"
        )
    return "\n".join(lines)


def school_table(schools: list[dict], generated_on: str) -> str:
    lines = [
        "| 档位 | 学校/平台 | 城市 | 方向 | 初试科目提示 | 官方入口 | 核验动作 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in schools:
        directions = "、".join(item.get("directions", [])[:3])
        if item.get("fit_note"):
            directions += f"（{item['fit_note']}）"
        note = item.get("exam_note", "以当年招生目录为准")
        if is_stale(item.get("last_verified", ""), generated_on):
            note += "（数据需重新核验）"
        links = []
        if item.get("official_url"):
            links.append(f"[官网]({item['official_url']})")
        if item.get("grad_url"):
            links.append(f"[研招]({item['grad_url']})")
        links_text = " / ".join(links) if links else "—"
        verify = "查当年目录；查导师近3年论文；找师兄师姐"
        lines.append(
            f"| {item.get('tier', '')} | {md_escape(item.get('name', ''))}·{md_escape(item.get('unit', ''))} | "
            f"{md_escape(item.get('city', ''))} | {md_escape(directions)} | {md_escape(note)} | "
            f"{links_text} | {md_escape(verify)} |"
        )
    return "\n".join(lines)


def job_table(jobs: list[dict], generated_on: str) -> str:
    lines = ["| 岗位 | 单位/城市 | 学历/专业/经验 | 薪资样本 | 核心技能 |", "|---|---|---|---|---|"]
    for item in jobs:
        salary = item.get("salary", "未公开")
        if is_stale(item.get("last_verified", ""), generated_on):
            salary += "（需重新核验）"
        skills = "、".join(item.get("skills", [])[:4])
        lines.append(
            f"| {md_escape(item.get('role', ''))} | {md_escape(item.get('company', ''))}·{md_escape(item.get('city', ''))} | "
            f"{md_escape(item.get('degree', '未明'))}/{md_escape(item.get('experience', '未明'))} | {md_escape(salary)} | {md_escape(skills)} |"
        )
    return "\n".join(lines)


def action_table(actions: list[dict]) -> str:
    lines = ["| 时间 | 课程/技能 | 科研/实习 | 信息核验 |", "|---|---|---|---|"]
    for item in actions:
        lines.append(
            f"| {md_escape(item['time'])} | {md_escape(item['course'])} | {md_escape(item['research'])} | {md_escape(item['verify'])} |"
        )
    return "\n".join(lines)


def verification_list(items: list[str]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items)


def sources_list(sources: list[dict], generated_on: str) -> str:
    lines = []
    for item in sources:
        stale = "（需重新核验）" if is_stale(item.get("last_verified", ""), generated_on) else ""
        lines.append(f"- [{item.get('name', '来源')}]({item.get('url', '')}) — `{item.get('last_verified', '')}`{stale}")
    lines.append("- 完整来源与可信度说明见 `references/sources.md`。")
    return "\n".join(lines)


def render_report_text(profile: dict, score: dict, template_path: str | Path) -> str:
    template = Path(template_path).read_text(encoding="utf-8-sig")
    generated_on = score.get("generated_on", date.today().isoformat())

    assumptions = (
        "动手/理论为自评；未填写的信息按 skill 默认值处理；"
        "匹配分是相对匹配，不是录取概率；招生科目以当年目录为准。"
    )

    job_section = job_table(score.get("jobs", []), generated_on)
    if profile.get("degree") == "读博":
        job_section += (
            "\n\n**读博提醒**：岗位样本只用于了解产业出口；读博应优先看导师、平台、"
            "博士点与方向，而不是起薪。"
        )

    path_note = (
        "> **路径提醒**：以下为考研备选；最终择校前，先用岗位样本和实验室体验校正方向。"
    )
    if profile.get("degree") == "本科就业":
        path_note = (
            "> **路径提醒**：你选择本科就业，下面的院校表只作为“如果改变主意考研”的备选；"
            "优先用岗位样本反推实习、技能和城市。"
        )
    elif profile.get("degree") == "读博":
        path_note = (
            "> **路径提醒**：读博优先看导师、平台、博士点和方向；学校名气只是其中一项。"
        )

    top_track = (score.get("tracks") or [{}])[0].get("id", "")
    if not profile.get("math_one_ok") and top_track in ("physics", "hybrid"):
        path_note += (
            "\n>\n> **数学一提醒**：你暂不接受数学一。表中部分电子/微电子方向可能要求数一；"
            "优先看材料学院下的“材料物理与化学/材料科学与工程”专业，避开明确要求数一的微电子/集成电路专业。"
        )

    replacements = {
        "{{GENERATED_ON}}": generated_on,
        "{{ASSUMPTIONS}}": assumptions,
        "{{SUMMARY}}": score.get("summary", ""),
        "{{TRACK_TABLE}}": track_table(score.get("tracks", [])),
        "{{PATH_NOTE}}": path_note,
        "{{SCHOOL_TABLE}}": school_table(score.get("schools", []), generated_on),
        "{{JOB_TABLE}}": job_section,
        "{{ACTIONS}}": action_table(score.get("actions", [])),
        "{{VERIFY}}": verification_list(score.get("verification", [])),
        "{{SOURCES}}": sources_list(score.get("sources", []), generated_on),
    }
    report = template
    for key, value in replacements.items():
        report = report.replace(key, value)

    header = (
        f"> 画像：{profile.get('school', '未填写')} / {profile.get('major', '材料类')} / "
        f"{profile.get('grade', '未填写')} ｜ 数学 {profile.get('math', 3)}/5 ｜ "
        f"动手 {profile.get('hands_on', 3)}/5 ｜ 理论 {profile.get('theory', 3)}/5 ｜ "
        f"地区 {', '.join(profile.get('region', ['不限']))} ｜ {profile.get('degree', '硕士就业')} ｜ {profile.get('risk', '稳就业')}\n\n"
    )
    return report.replace("# 你的材料方向罗盘\n", "# 你的材料方向罗盘\n\n" + header, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a materials-compass report.")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--template", default="references/report-template.md")
    parser.add_argument("--out", default="report.md")
    args = parser.parse_args()

    profile = load_json(Path(args.profile))
    score = load_json(Path(args.score))
    report = render_report_text(profile, score, args.template)

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
