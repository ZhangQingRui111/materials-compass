#!/usr/bin/env python3
"""Score a materials-career profile against the bundled school/job data.

Usage:
    python scripts/score.py --profile profile.json --data-dir references/data --out score.json

Only the Python standard library is used, so the skill works without pip installs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def normalize_profile(raw: dict) -> dict:
    defaults = {
        "school": "未填写",
        "major": "材料类",
        "grade": "未填写",
        "math": 3,
        "hands_on": 3,
        "theory": 3,
        "math_one_ok": False,
        "region": ["不限"],
        "degree": "硕士就业",
        "risk": "稳就业",
        "interests": [],
        "notes": "",
    }
    profile = {**defaults, **raw}
    for key in ("math", "hands_on", "theory"):
        try:
            profile[key] = int(profile[key])
        except (TypeError, ValueError):
            profile[key] = defaults[key]
        profile[key] = max(1, min(5, profile[key]))
    if isinstance(profile.get("region"), str):
        profile["region"] = [profile["region"]]
    if not profile.get("region"):
        profile["region"] = ["不限"]
    if isinstance(profile.get("interests"), str):
        profile["interests"] = [profile["interests"]]
    profile["math_one_ok"] = bool(profile.get("math_one_ok", False))
    return profile


def track_scores(profile: dict) -> list[dict]:
    math = profile["math"] / 5
    hands = profile["hands_on"] / 5
    theory = profile["theory"] / 5
    degree = profile["degree"]
    degree_work = 1.0 if degree in ("本科就业", "硕士就业") else 0.5
    degree_phd = 1.0 if degree == "读博" else 0.5

    interests = " ".join(profile.get("interests", []))
    process_kw = ["增材", "焊接", "激光", "熔覆", "热喷涂", "涂层", "表面", "加工", "再制造", "封装", "成形"]
    physics_kw = ["半导体", "器件", "物理", "薄膜", "外延", "显示", "OLED", "Micro-LED", "计算", "磁性", "钙钛矿"]
    hybrid_kw = ["封装", "CMP", "功率器件", "显示", "交叉", "热管理", "互连", "靶材", "半导体材料", "电子材料", "SiC", "GaN"]

    def bonus(words: list[str]) -> float:
        hits = sum(1 for word in words if word in interests)
        return min(1.0, hits / 2)

    process_bonus = bonus(process_kw)
    physics_bonus = bonus(physics_kw)
    hybrid_bonus = bonus(hybrid_kw)

    process = 0.45 * hands + 0.20 * math + 0.20 * degree_work + 0.15 * process_bonus
    physics = 0.40 * theory + 0.35 * math + 0.15 * degree_phd + 0.10 * physics_bonus
    hybrid = 0.30 * hands + 0.30 * theory + 0.20 * math + 0.20 * hybrid_bonus

    if not profile["math_one_ok"]:
        physics *= 0.90
        hybrid *= 0.95

    reasons = {
        "process": f"动手 {profile['hands_on']}/5，数学 {profile['math']}/5；就业导向权重 {degree_work:.1f}；兴趣命中 {process_bonus:.1f}",
        "physics": f"理论 {profile['theory']}/5，数学 {profile['math']}/5；读博权重 {degree_phd:.1f}；兴趣命中 {physics_bonus:.1f}",
        "hybrid": f"动手 {profile['hands_on']}/5 + 理论 {profile['theory']}/5；数学 {profile['math']}/5；交叉关键词命中 {hybrid_bonus:.1f}",
    }
    risks = {
        "process": "容易经验化；不做深机理，天花板受限",
        "physics": "论文周期长；岗位更窄；产业落地需补工艺",
        "hybrid": "容易两边都不深；需要主动补一边的硬基础",
    }
    names = {"process": "工艺/工程", "physics": "物理/机理", "hybrid": "交叉"}

    return [
        {"id": key, "name": names[key], "score": round(100 * value), "reason": reasons[key], "risk": risks[key]}
        for key, value in (("process", process), ("physics", physics), ("hybrid", hybrid))
    ]


def risk_target(risk: str) -> float:
    return {"冲": 5.0, "冲名校": 5.0, "稳": 3.5, "稳就业": 3.5, "保": 2.5, "先保底": 2.5}.get(risk, 3.5)


def tier_for(difficulty: float) -> str:
    if difficulty >= 4.5:
        return "冲"
    if difficulty >= 3.0:
        return "稳"
    return "保"


def direction_overlap(interests: list[str], directions: list[str]) -> float:
    if not interests:
        return 0.5
    text = " ".join(directions)
    hits = sum(1 for item in interests if item and item in text)
    return clamp(hits / max(1, len(interests)))


def region_match(profile_regions: list[str], school_region: str) -> float:
    if "不限" in profile_regions:
        return 0.7
    if school_region in profile_regions:
        return 1.0
    return 0.2


def score_schools(profile: dict, schools: list[dict], top_track: str) -> list[dict]:
    school_name = (profile.get("school") or "").strip()

    def is_home_match(item: dict) -> bool:
        home = item.get("home_school", "")
        if not home:
            return False
        return home in school_name or ("矿大" in school_name and "矿业大学" in home)

    # The bundled dataset contains one example home school (CUMT). Only keep
    # such entries for the matching user; everyone else gets a dynamic home
    # school below, so the skill does not push one university onto everyone.
    schools = [item for item in schools if not item.get("home_school") or is_home_match(item)]

    if school_name and school_name not in ("未填写", "材料类") and not any(is_home_match(item) for item in schools):
        home_region = profile["region"][0] if profile.get("region") and profile["region"][0] != "不限" else "其他"
        schools = list(schools) + [
            {
                "id": "home-school",
                "name": school_name,
                "unit": "本校/同层次院校（保底）",
                "city": "你所在城市",
                "region": home_region,
                "tracks": ["process", "physics", "hybrid"],
                "directions": ["本校优势方向（需自行确认）"],
                "math_hint": "以本校当年目录为准",
                "exam_note": "以本校当年招生目录为准",
                "difficulty": 2,
                "why": "本校保底：信息成本低，导师可提前接触",
                "source": "",
                "last_verified": date.today().isoformat(),
                "home_school": school_name,
                "is_home": True,
            }
        ]

    target = risk_target(profile["risk"])
    scored = []
    for school in schools:
        tracks = school.get("tracks", [])
        if top_track in tracks:
            track_match = 1.0
        elif "hybrid" in tracks:
            track_match = 0.75
        else:
            track_match = 0.35

        overlap = direction_overlap(profile.get("interests", []), school.get("directions", []))
        direction = 0.4 + 0.6 * overlap
        region = region_match(profile["region"], school.get("region", "其他"))
        diff_fit = clamp(1 - abs(school.get("difficulty", 3) - target) / 4)
        strength = school.get("strength", 3) / 5
        score = 100 * (
            0.30 * track_match
            + 0.25 * direction
            + 0.15 * region
            + 0.10 * diff_fit
            + 0.20 * strength
        )

        # For a "稳/保" user, a top-difficulty school is a stretch, not a default.
        if target <= 3.5 and school.get("difficulty", 3) >= 4.5:
            score *= 0.90

        fit_note = ""
        if top_track not in tracks:
            score *= 0.9 if "hybrid" in tracks else 0.75
            fit_note = "跨方向选项，需补对应基础"

        reasons = []
        if track_match >= 0.75:
            reasons.append("方向匹配")
        if overlap > 0:
            reasons.append("兴趣命中")
        if region == 1.0:
            reasons.append("地区匹配")
        if diff_fit >= 0.8:
            reasons.append("难度合适")
        if school.get("strength", 3) >= 4:
            reasons.append("平台强度高")

        scored.append(
            {
                **school,
                "score": round(score),
                "tier": tier_for(school.get("difficulty", 3)),
                "reasons": reasons or ["可作备选"],
                "fit_note": fit_note,
                "is_home": bool(school.get("is_home") or is_home_match(school)),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    selected = scored[:5]

    # Keep the user's own school in the shortlist when it is known: it is the
    # lowest-cost option and the one they can verify by walking to the lab.
    home = next((item for item in scored if item.get("is_home")), None)
    if home and home not in selected:
        if len(selected) >= 5:
            counts: dict[str, int] = {}
            for item in selected:
                counts[item["tier"]] = counts.get(item["tier"], 0) + 1
            removable = [item for item in selected if counts[item["tier"]] > 1]
            if removable:
                selected.remove(min(removable, key=lambda item: item["score"]))
            else:
                selected.remove(min(selected, key=lambda item: item["score"]))
        selected.append(home)

    # Make sure the shortlist still has a 冲/稳/保 spread.
    for tier in ("冲", "稳", "保"):
        if any(item["tier"] == tier for item in selected):
            continue
        candidate = next((item for item in scored if item["tier"] == tier and item not in selected), None)
        if candidate is None:
            continue
        counts: dict[str, int] = {}
        for item in selected:
            counts[item["tier"]] = counts.get(item["tier"], 0) + 1
        removable = [
            item for item in selected if counts[item["tier"]] > 1
        ]
        if removable:
            selected.remove(min(removable, key=lambda item: item["score"]))
            selected.append(candidate)

    order = {"冲": 0, "稳": 1, "保": 2}
    selected.sort(key=lambda item: (order.get(item["tier"], 3), -item["score"]))
    return selected


def degree_match(profile_degree: str, job_degree: str) -> float:
    if profile_degree == "本科就业":
        return {"本科": 1.0, "不限": 0.9, "硕士": 0.4, "博士": 0.2}.get(job_degree, 0.7)
    if profile_degree == "读博":
        return 0.5
    return {"硕士": 1.0, "本科": 0.8, "不限": 0.8, "博士": 0.5}.get(job_degree, 0.7)


def score_jobs(profile: dict, jobs: list[dict], top_track: str) -> list[dict]:
    scored = []
    for job in jobs:
        track = job.get("track", "hybrid")
        track_match = 1.0 if track == top_track else (0.8 if track == "hybrid" or top_track == "hybrid" else 0.4)
        degree = degree_match(profile["degree"], job.get("degree", "不限"))
        region = region_match(profile["region"], job.get("region", "其他"))
        text = " ".join(job.get("skills", [])) + " " + job.get("role", "")
        interests = [item for item in profile.get("interests", []) if item]
        overlap = sum(1 for item in interests if item in text) / max(1, len(interests)) if interests else 0.4
        score = 100 * (0.45 * track_match + 0.20 * degree + 0.20 * region + 0.15 * overlap)
        scored.append({**job, "score": round(score)})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:5]


def build_summary(profile: dict, tracks: list[dict], schools: list[dict]) -> str:
    top = tracks[0]
    second = tracks[1]

    # Only use schools that actually match the top track, so a physics-heavy
    # school cannot hijack the summary for a process-oriented profile.
    candidates = [school for school in schools if top["id"] in school.get("tracks", [])]
    if not candidates:
        candidates = schools

    directions: list[str] = []
    for school in candidates:
        for direction in school.get("directions", []):
            if direction not in directions:
                directions.append(direction)

    interest_text = " ".join(profile.get("interests", []))
    directions.sort(key=lambda item: 0 if item in interest_text else 1)
    directions_text = "、".join(directions[:2]) if directions else "尚未确定"

    action_map = {
        "process": "先在本校找一个材料加工/表面工程组，做一学期真实工艺，再决定考研还是就业。",
        "physics": "先补固体物理/半导体物理，并找一个薄膜、器件或计算组做一段科研，验证自己能否接受长反馈周期。",
        "hybrid": "先找封装、CMP 或涂层方向的组，同时补半导体物理和材料加工，保留两条出口。",
    }

    bridge = ""
    if top["id"] == "process" and any(word in interest_text for word in ("半导体", "电子", "封装", "显示")):
        bridge = " 你对电子材料的兴趣可以通过交叉方向（先进封装/CMP/功率器件封装）保留，不必二选一。"

    return (
        f"你更像 **{top['name']}**（{top['score']} 分），其次是 {second['name']}（{second['score']} 分）。"
        f"主攻方向建议围绕 {directions_text}，但要先用一个学期验证。"
        f"{bridge}"
        f"最值得先做的一件事：{action_map.get(top['id'], action_map['hybrid'])}"
    )


def build_actions(profile: dict, top_track: str) -> list[dict]:
    if top_track == "process":
        rows = [
            ("未来 3 个月", "材料加工/焊接/表面工程/失效分析", "在本校进一个工艺组，跟一次完整实验", "查 2 所目标院校当年招生目录"),
            ("3–6 个月", "SEM/XRD/金相 + DOE/统计", "完成一个小课题或大创", "查导师近 3 年论文与横向项目"),
            ("6–12 个月", "英语 + 数学二/专业课", "暑期实习：激光/增材/涂层企业", "确认复试科目与报录比"),
        ]
    elif top_track == "physics":
        rows = [
            ("未来 3 个月", "固体物理/半导体物理/数学一（如需）", "进薄膜、器件或计算组", "确认目标专业考数一还是数二"),
            ("3–6 个月", "Python/DFT 或高级表征", "完成一段科研，争取署名/报告", "查导师近 3 年论文与项目"),
            ("6–12 个月", "英语 + 专业课", "暑期科研/夏令营", "准备 3 所冲、2 所稳的材料"),
        ]
    else:
        rows = [
            ("未来 3 个月", "半导体物理 + 材料加工基础", "进封装/CMP/涂层方向组", "确认目标专业考试科目"),
            ("3–6 个月", "可靠性/界面/表征", "做一个小型交叉课题", "查产业学院/企业联培项目"),
            ("6–12 个月", "英语 + 数学/专业课", "实习：长电/通富/安集/鼎龙等", "同时准备工艺岗与研发岗简历"),
        ]
    return [{"time": a, "course": b, "research": c, "verify": d} for a, b, c, d in rows]


def build_verification(profile: dict, schools: list[dict]) -> list[str]:
    items = [
        "去研招网/目标学院官网查最近一年的招生目录，确认数学一/数学二、专业课代码和复试科目。",
        "查导师近 3 年论文与在研项目，判断组里是做工艺、器件还是计算。",
        "找 2 位在读师兄师姐，问清组会频率、毕业要求、实习是否允许。",
        "查目标院校报录比与复试线，不要只看最低录取分。",
        "岗位样本：点开来源链接，确认岗位是否仍在招聘、薪资口径是月薪还是年薪。",
        "把本报告的 `last_verified` 与今天对比；超过 12 个月的数据要重新核验。",
    ]
    if profile["school"] != "未填写":
        items.append(f"如果考虑本校保底：找 {profile['school']} 材料/物理方向的导师聊一次，确认是否有联培或校内调剂机会。")
    return items


def collect_sources(schools: list[dict], jobs: list[dict]) -> list[dict]:
    seen = set()
    sources = []
    for item in list(schools) + list(jobs):
        source = item.get("source")
        if source and source.startswith("http") and source not in seen:
            seen.add(source)
            sources.append(
                {
                    "name": item.get("source_name") or item.get("name") or item.get("company"),
                    "url": source,
                    "last_verified": item.get("last_verified", ""),
                }
            )
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a materials career profile.")
    parser.add_argument("--profile", required=True, help="Path to profile JSON")
    parser.add_argument("--data-dir", default="references/data", help="Directory containing schools.json/jobs.json/tracks.json")
    parser.add_argument("--out", default="score.json", help="Path to output JSON")
    args = parser.parse_args()

    profile = normalize_profile(load_json(Path(args.profile)))
    data_dir = Path(args.data_dir)
    schools = load_json(data_dir / "schools.json")
    jobs = load_json(data_dir / "jobs.json")
    tracks_data = load_json(data_dir / "tracks.json")

    tracks = track_scores(profile)
    track_names = {item["id"]: item["name"] for item in tracks_data}
    for item in tracks:
        item["name"] = track_names.get(item["id"], item["name"])
    tracks.sort(key=lambda item: item["score"], reverse=True)

    top_track = tracks[0]["id"]
    selected_schools = score_schools(profile, schools, top_track)
    selected_jobs = score_jobs(profile, jobs, top_track)

    result = {
        "generated_on": date.today().isoformat(),
        "profile": profile,
        "tracks": tracks,
        "schools": selected_schools,
        "jobs": selected_jobs,
        "summary": build_summary(profile, tracks, selected_schools),
        "actions": build_actions(profile, top_track),
        "verification": build_verification(profile, selected_schools),
        "sources": collect_sources(selected_schools, selected_jobs),
    }

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
