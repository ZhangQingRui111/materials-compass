"""Copy the current materials-compass skill into a portable app snapshot.

Run after updating the skill:
    python sync_skill.py

If auto-detection fails, point it at the skill explicitly:
    python sync_skill.py --skill-dir "C:\\path\\to\\materials-compass"
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

DEST = Path(__file__).resolve().parent / "skill_snapshot"


def skill_candidates() -> list[Path]:
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
        ]
    )
    return candidates


def resolve_skill_dir(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if (path / "scripts" / "score.py").exists():
            return path
        raise SystemExit(f"指定的 skill 路径不存在或不完整：{path}")

    for candidate in skill_candidates():
        if (candidate / "scripts" / "score.py").exists() and (candidate / "SKILL.md").exists():
            return candidate

    tried = "\n".join(f"  - {candidate}" for candidate in skill_candidates())
    raise SystemExit(
        "找不到 materials-compass skill。已尝试：\n"
        f"{tried}\n\n"
        "请用 --skill-dir 指定，例如：\n"
        '  python sync_skill.py --skill-dir "C:\\Users\\你的用户名\\AppData\\Roaming\\'
        'CherryStudio\\Data\\Skills\\materials-compass"'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync the materials-compass skill.")
    parser.add_argument("--skill-dir", help="materials-compass skill 目录")
    args = parser.parse_args()

    skill = resolve_skill_dir(args.skill_dir)
    (DEST / "references" / "data").mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill / "scripts", DEST / "scripts", dirs_exist_ok=True)
    for name in ("schools.json", "jobs.json", "tracks.json"):
        shutil.copy2(skill / "references" / "data" / name, DEST / "references" / "data" / name)
    for name in ("report-template.md", "sources.md"):
        shutil.copy2(skill / "references" / name, DEST / "references" / name)
    shutil.copy2(skill / "SKILL.md", DEST / "SKILL.md")
    print(f"synced {skill} -> {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
