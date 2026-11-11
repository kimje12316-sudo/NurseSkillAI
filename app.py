
import streamlit as st

st.set_page_config(
    page_title="Nurse Skill AI",
    page_icon="🩺",
    layout="centered"
)

st.title("🩺 Nurse Skill AI")
st.subheader("AI 기반 간호술기 수행 분석 시스템")

st.write(
    "간호술기 영상을 업로드하고 "
    "수행 과정을 체크리스트와 비교하는 학습 보조 프로그램입니다."
)

st.divider()

# 1. 간호술기 선택
st.header("1. 간호술기 선택")

skill = st.selectbox(
    "분석할 간호술기를 선택하세요.",
    ["손 위생", "활력징후 측정", "단순도뇨", "유치도뇨", "기관 내 흡인"]
)

st.success(f"선택한 술기: {skill}")

st.divider()

# 2. 영상 업로드
st.header("2. 간호술기 영상 업로드")

video = st.file_uploader(
    "촬영한 간호술기 영상을 선택하세요.",
    type=["mp4", "mov", "avi"]
)

if video is not None:
    st.success("영상이 업로드되었습니다.")
    st.video(video)
    st.write("파일 이름:", video.name)

st.divider()

# 3. 손 위생 체크리스트
st.header("3. 간호술기 체크리스트")

if skill == "손 위생":

    st.write("손 위생 수행 항목을 확인하세요.")

    checklist = [
        "손바닥을 서로 문지르기",
        "손등을 서로 문지르기",
        "손가락 사이 문지르기",
        "두 손의 손가락 등 문지르기",
        "엄지손가락 문지르기",
        "손끝과 손톱 밑 문지르기"
    ]

    for i, item in enumerate(checklist):
        st.checkbox(item, key=f"hand_{i}")

    st.caption(
        "※ 현재 체크리스트는 수동 확인용입니다. "
        "AI가 실제 수행 여부를 판정하는 기능은 아직 구현되지 않았습니다."
    )

else:
    st.info("선택한 술기의 체크리스트는 추후 추가할 예정입니다.")

st.divider()

# 4. AI 분석 기능 준비
st.header("4. AI 분석")

st.button(
    "AI 영상 분석 시작",
    disabled=True,
    help="AI 영상 분석 기능은 다음 개발 단계에서 연결할 예정입니다."
)

st.info(
    "현재는 웹 화면과 영상 업로드, 손 위생 체크리스트 기능을 "
    "구현한 초기 시제품입니다."
)

st.divider()

st.caption("Nurse Skill AI | Nursing Skills Practice Assistant")
