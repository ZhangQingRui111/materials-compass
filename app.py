"""材料罗盘 · Streamlit 前端

Run:
    streamlit run app.py

The app reads the materials-compass skill from MATERIALS_COMPASS_SKILL_DIR,
or from the default Cherry Studio path shown in the sidebar.
"""

from __future__ import annotations

import streamlit as st

from app_core import DEFAULT_SKILL_DIR, CompassError, build_profile, run_skill

st.set_page_config(
    page_title="材料罗盘",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧭 材料罗盘")
st.caption(
    "给材料类本科生的方向选择、考研择校与就业规划工具。"
    "它不替你做决定，而是把“迷茫”拆成一张可核验的表。"
)

with st.sidebar:
    st.header("设置")
    skill_dir = st.text_input(
        "materials-compass skill 目录",
        value=str(DEFAULT_SKILL_DIR),
        help="指向包含 SKILL.md、references/、scripts/ 的文件夹。",
    )
    st.caption("当前数据：47 个院校/平台 · 26 个岗位样本 · 2026-10-20")
    st.divider()
    st.markdown(
        "**使用边界**\n\n"
        "- 匹配分是相对匹配，不是录取概率。\n"
        "- 招生科目以目标院校当年目录为准。\n"
        "- 薪资是招聘页面样本，不是平均值。\n"
        "- 报告会给出官网/研招入口，请自己点开核验。"
    )

REGIONS = ["长三角", "北京", "西安", "成渝", "珠三角", "不限"]
DEGREES = ["硕士就业", "本科就业", "读博"]
RISKS = ["稳就业", "冲名校", "先保底"]
INTERESTS = [
    "表面工程",
    "增材制造",
    "焊接",
    "激光熔覆",
    "封装",
    "CMP",
    "半导体材料",
    "SiC/GaN",
    "显示",
    "薄膜",
    "器件",
    "计算材料",
    "新能源材料",
]

with st.form("profile_form"):
    st.subheader("1. 你的画像")
    col1, col2, col3 = st.columns(3)
    school = col1.text_input("学校", value="中国矿业大学")
    major = col2.text_input("专业", value="材料科学与工程")
    grade = col3.text_input("年级", value="大二")

    col1, col2 = st.columns(2)
    math = col1.slider("数学自评（1–5）", 1, 5, 3)
    math_one_ok = col2.checkbox("我能接受数学一", value=False)

    col1, col2 = st.columns(2)
    hands_on = col1.slider("喜欢动手做工艺（1–5）", 1, 5, 4)
    theory = col2.slider("喜欢推导机理（1–5）", 1, 5, 3)

    region = st.multiselect("目标地区", REGIONS, default=["长三角"])
    col1, col2 = st.columns(2)
    degree = col1.selectbox("学历目标", DEGREES, index=0)
    risk = col2.selectbox("风险偏好", RISKS, index=0)

    interests = st.multiselect(
        "感兴趣的关键词（选 2–4 个）",
        INTERESTS,
        default=["表面工程", "半导体材料"],
    )

    submitted = st.form_submit_button("生成报告", type="primary", use_container_width=True)

if submitted:
    profile = build_profile(
        school=school,
        major=major,
        grade=grade,
        math=math,
        hands_on=hands_on,
        theory=theory,
        math_one_ok=math_one_ok,
        region=region,
        degree=degree,
        risk=risk,
        interests=interests,
    )
    try:
        with st.spinner("正在计算方向匹配、择校与岗位样本……"):
            score, report, work_dir = run_skill(profile, skill_dir)
        st.session_state["compass_score"] = score
        st.session_state["compass_report"] = report
        st.session_state["compass_profile"] = profile
    except CompassError as error:
        st.error(str(error))
    except Exception as error:  # noqa: BLE001
        st.error(f"运行失败：{error}")

score = st.session_state.get("compass_score")
report = st.session_state.get("compass_report")
profile = st.session_state.get("compass_profile")

if not score or not report:
    st.info("填写左侧画像，然后点击“生成报告”。想先看看效果，可以直接用默认值。")
    st.stop()

top = score["tracks"][0]
st.subheader("2. 结果总览")
col1, col2, col3, col4 = st.columns(4)
col1.metric("最匹配的方向", top["name"], f"{top['score']} 分")
col2.metric("冲/稳/保院校", f"{len(score['schools'])} 所")
col3.metric("岗位样本", f"{len(score['jobs'])} 个")
col4.metric("数据日期", score.get("generated_on", "—"))

st.markdown(score.get("summary", ""))

tabs = st.tabs(["方向匹配", "考研冲稳保", "岗位样本", "行动表", "完整报告"])

with tabs[0]:
    st.markdown("### 三条 track 的匹配度")
    st.dataframe(
        [
            {
                "Track": item["name"],
                "匹配分": item["score"],
                "为什么": item["reason"],
                "风险": item["risk"],
            }
            for item in score["tracks"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Track": st.column_config.TextColumn(width="small"),
            "匹配分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "为什么": st.column_config.TextColumn(width="large"),
            "风险": st.column_config.TextColumn(width="medium"),
        },
    )

with tabs[1]:
    st.markdown("### 考研冲稳保")
    st.caption("官网 / 研招入口可以直接点开；初试科目只是提示，必须查当年招生目录。")
    st.dataframe(
        [
            {
                "档位": item.get("tier"),
                "学校": item.get("name"),
                "平台": item.get("unit"),
                "城市": item.get("city"),
                "方向": "、".join(item.get("directions", [])[:3]),
                "初试科目提示": item.get("exam_note", ""),
                "官网": item.get("official_url", ""),
                "研招": item.get("grad_url", ""),
            }
            for item in score["schools"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "档位": st.column_config.TextColumn(width="small"),
            "学校": st.column_config.TextColumn(width="medium"),
            "平台": st.column_config.TextColumn(width="large"),
            "方向": st.column_config.TextColumn(width="medium"),
            "初试科目提示": st.column_config.TextColumn(width="large"),
            "官网": st.column_config.LinkColumn(display_text="打开"),
            "研招": st.column_config.LinkColumn(display_text="打开"),
        },
    )

with tabs[2]:
    st.markdown("### 岗位样本")
    st.caption("薪资是招聘页面在采集时点的样本，不是平均值；“未公开”不代表低薪。")
    st.dataframe(
        [
            {
                "岗位": item.get("role"),
                "单位": item.get("company"),
                "城市": item.get("city"),
                "学历/专业/经验": f"{item.get('degree', '未明')} / {item.get('experience', '未明')}",
                "薪资样本": item.get("salary", "未公开"),
                "核心技能": "、".join(item.get("skills", [])[:5]),
                "来源": item.get("source", ""),
            }
            for item in score["jobs"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "岗位": st.column_config.TextColumn(width="medium"),
            "单位": st.column_config.TextColumn(width="medium"),
            "学历/专业/经验": st.column_config.TextColumn(width="medium"),
            "薪资样本": st.column_config.TextColumn(width="medium"),
            "核心技能": st.column_config.TextColumn(width="large"),
            "来源": st.column_config.LinkColumn(display_text="打开"),
        },
    )

with tabs[3]:
    st.markdown("### 未来 12 个月行动表")
    st.dataframe(
        [
            {
                "时间": item["time"],
                "课程/技能": item["course"],
                "科研/实习": item["research"],
                "信息核验": item["verify"],
            }
            for item in score["actions"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("### 核验清单")
    for item in score["verification"]:
        st.checkbox(item, key=f"verify-{hash(item)}")

with tabs[4]:
    st.markdown(report)
    st.download_button(
        "下载 Markdown 报告",
        data=report,
        file_name="materials-compass-report.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.divider()
st.caption(
    "数据与来源见 skill 的 references/sources.md。"
    "报告是决策辅助，不是录取承诺或薪资承诺。"
)
