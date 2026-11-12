
import streamlit as st

# 1. 웹사이트 기본 설정
st.set_page_config(
    page_title="Nurse Skill AI",
    page_icon="🩺",
    layout="centered"
)

# 2. 제목 및 소개
st.title("🩺 Nurse Skill AI")
st.subheader("AI 기반 간호술기 수행 분석 시스템")

st.write(
    "간호술기 영상을 업로드하고 "
    "수행 과정을 체크리스트와 비교하는 학습 보조 프로그램입니다."
)

st.divider()

# 3. 간호술기 선택
st.header("1. 간호술기 선택")

skill = st.selectbox(
    "분석할 간호술기를 선택하세요.",
    ["손 위생", "활력징후 측정", "단순도뇨", "유치도뇨", "기관 내 흡인"]
)

st.success(f"선택한 술기: {skill}")

st.divider()

# 4. 영상 업로드
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

# 5. 손 위생 체크리스트
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

    completed = 0

    # 체크박스 생성 및 수행 항목 계산
    for i, item in enumerate(checklist):
        checked = st.checkbox(item, key=f"hand_{i}")

        if checked:
            completed += 1

    total = len(checklist)
    remaining = total - completed
    progress = completed / total

    st.divider()

    # 수행률 표시
    st.subheader("손 위생 체크리스트 진행 상황")

    st.progress(progress)

    st.metric(
        label="수동 체크 기준 수행률",
        value=f"{progress * 100:.1f}%"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("완료 항목", f"{completed}개")
    col2.metric("전체 항목", f"{total}개")
    col3.metric("남은 항목", f"{remaining}개")

    # 결과 메시지
    if completed == total:
        st.success("모든 체크리스트 항목을 확인했습니다.")
    elif completed == 0:
        st.info("아직 체크한 항목이 없습니다.")
    else:
        st.warning(f"{remaining}개 항목이 아직 체크되지 않았습니다.")

    st.caption(
        "※ 이 수행률은 사용자가 직접 체크한 항목의 비율입니다. "
        "실제 영상 분석이나 간호술기 적절성에 대한 AI 판정 결과가 아닙니다."
    )

else:
    st.info("선택한 술기의 체크리스트는 추후 추가할 예정입니다.")

st.divider()

# 6. AI 분석 기능 준비
st.header("4. AI 분석")

st.button(
    "AI 영상 분석 시작",
    disabled=True,
    help="AI 영상 분석 기능은 다음 개발 단계에서 연결할 예정입니다."
)

st.info(
    "현재는 웹 화면, 영상 업로드, "
    "손 위생 체크리스트 및 수동 수행률 계산 기능을 구현한 시제품입니다."
)

st.divider()

# 7. 하단 안내
st.caption("Nurse Skill AI | Nursing Skills Practice Assistant")
