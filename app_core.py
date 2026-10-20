"""Thin wrapper around the materials-compass skill scripts.

The Streamlit app stays a *consumer* of the skill: it writes a profile JSON,
calls the skill's score.py / render_report.py, and reads the result. That way
the skill remains the single source of truth and the app does not fork the
data or the scoring logic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def _resolve_skill_dir() -> Path:
    candidates: list[Path] = []
    env = os.environ.get("MATERIALS_COMPASS_SKILL_DIR")
    if env:
        candidates.append(Path(env))

    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(
            Path(appdata) / "CherryStudio" / "Data" / "Skills" / "materials-compass"
        )

    home = Path.home()
    candidates.extend(
        [
            home / "AppData" / "Roaming" / "CherryStudio" / "Data" / "Skills" / "materials-compass",
            Path(__file__).resolve().parent / "materials-compass",
            Path(__file__).resolve().parent.parent / "materials-compass",
            Path(__file__).resolve().parent / "skill_snapshot",
        ]
    )
    for candidate in candidates:
        if (candidate / "scripts" / "score.py").exists():
            return candidate
    return Path(__file__).resolve().parent / "skill_snapshot"


DEFAULT_SKILL_DIR = _resolve_skill_dir()


class CompassError(RuntimeError):
    pass


def build_profile(
    school: str,
    major: str,
    grade: str,
    math: int,
    hands_on: int,
    theory: int,
    math_one_ok: bool,
    region: list[str],
    degree: str,
    risk: str,
    interests: list[str],
) -> dict:
    return {
        "school": school.strip() or "未填写",
        "major": major.strip() or "材料类",
        "grade": grade.strip() or "未填写",
        "math": int(math),
        "hands_on": int(hands_on),
        "theory": int(theory),
        "math_one_ok": bool(math_one_ok),
        "region": region or ["不限"],
        "degree": degree,
        "risk": risk,
        "interests": interests or [],
    }


def run_skill(profile: dict, skill_dir: Path | str | None = None) -> tuple[dict, str, Path]:
    """Run the skill's scoring and rendering scripts. Returns (score, report, work_dir)."""
    skill = Path(skill_dir) if skill_dir else DEFAULT_SKILL_DIR
    score_script = skill / "scripts" / "score.py"
    render_script = skill / "scripts" / "render_report.py"
    template = skill / "references" / "report-template.md"
    data_dir = skill / "references" / "data"

    for path in (score_script, render_script, template, data_dir):
        if not path.exists():
            raise CompassError(f"找不到 skill 文件：{path}")

    work_dir = Path(tempfile.mkdtemp(prefix="materials-compass-"))
    profile_path = work_dir / "profile.json"
    score_path = work_dir / "score.json"
    report_path = work_dir / "report.md"
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def run(command: list[str]):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(skill),
        )
        if result.returncode != 0:
            raise CompassError(
                "skill 脚本运行失败：\n"
                + (result.stderr or result.stdout or "未知错误")[-2000:]
            )

    run(
        [
            sys.executable,
            str(score_script),
            "--profile",
            str(profile_path),
            "--data-dir",
            str(data_dir),
            "--out",
            str(score_path),
        ]
    )
    run(
        [
            sys.executable,
            str(render_script),
            "--profile",
            str(profile_path),
            "--score",
            str(score_path),
            "--template",
            str(template),
            "--out",
            str(report_path),
        ]
    )

    score = json.loads(score_path.read_text(encoding="utf-8-sig"))
    report = report_path.read_text(encoding="utf-8-sig")
    return score, report, work_dir


def _selftest() -> int:
    profile = build_profile(
        school="中国矿业大学",
        major="材料科学与工程",
        grade="大二",
        math=3,
        hands_on=4,
        theory=3,
        math_one_ok=False,
        region=["长三角"],
        degree="硕士就业",
        risk="稳就业",
        interests=["表面工程", "半导体材料"],
    )
    score, report, work_dir = run_skill(profile)
    print("top track:", score["tracks"][0]["name"], score["tracks"][0]["score"])
    print("schools:", [f"{s['name']}({s['tier']})" for s in score["schools"]])
    print("jobs:", [f"{j['company']}/{j['role']}" for j in score["jobs"]])
    print("report chars:", len(report))
    print("work_dir:", work_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
