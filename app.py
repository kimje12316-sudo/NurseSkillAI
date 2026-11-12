
import streamlit as st
import tempfile
import os
import time
from pathlib import Path
from google import genai

# 1. 기본 설정
st.set_page_config(
    page_title="Nurse Skill AI",
    page_icon="🩺",
    layout="centered"
)

st.title("🩺 Nurse Skill AI")
st.subheader("AI 기반 간호술기 수행 분석 시스템")

st.write(
    "간호술기 영상을 업로드하고 "
    "AI를 활용해 수행 과정을 분석하는 학습 보조 프로그램입니다."
)

st.divider()

# 2. 간호술기 선택
st.header("1. 간호술기 선택")

skill = st.selectbox(
    "분석할 간호술기를 선택하세요.",
    ["손 위생", "활력징후 측정", "단순도뇨", "유치도뇨", "기관 내 흡인"]
)

st.success(f"선택한 술기: {skill}")

st.divider()

# 3. 영상 업로드
st.header("2. 간호술기 영상 업로드")

video = st.file_uploader(
    "촬영한 간호술기 영상을 선택하세요.",
    type=["mp4", "mov", "avi"]
)

if video is not None:
    st.success("영상이 업로드되었습니다.")
    st.video(video)
    st.write("파일 이름:", video.name)
    st.write(f"파일 크기: {video.size / (1024 * 1024):.2f} MB")

st.divider()

# 4. 손 위생 체크리스트
st.header("3. 간호술기 체크리스트")

checklist = [
    "손바닥을 서로 문지르기",
    "손등을 서로 문지르기",
    "손가락 사이 문지르기",
    "두 손의 손가락 등 문지르기",
    "엄지손가락 문지르기",
    "손끝과 손톱 밑 문지르기"
]

if skill == "손 위생":

    st.write("손 위생 수행 항목을 확인하세요.")

    completed = 0

    for i, item in enumerate(checklist):
        if st.checkbox(item, key=f"hand_{i}"):
            completed += 1

    total = len(checklist)
    remaining = total - completed
    progress = completed / total

    st.divider()
    st.subheader("수동 체크리스트 진행 상황")

    st.progress(progress)

    st.metric(
        "수동 체크 기준 수행률",
        f"{progress * 100:.1f}%"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("완료", f"{completed}개")
    col2.metric("전체", f"{total}개")
    col3.metric("남음", f"{remaining}개")

    if completed == total:
        st.success("모든 항목을 체크했습니다.")
    elif completed == 0:
        st.info("아직 체크한 항목이 없습니다.")
    else:
        st.warning(f"{remaining}개 항목이 남았습니다.")

else:
    st.info("선택한 술기의 체크리스트는 추후 추가할 예정입니다.")

st.caption(
    "※ 위 체크리스트 수행률은 사용자가 직접 체크한 결과입니다."
)

st.divider()

# 5. Gemini AI 영상 분석
st.header("4. AI 영상 분석")

st.warning(
    "주의: 실제 환자 영상이나 이름, 얼굴, 병원 정보 등 "
    "개인정보가 포함된 영상은 업로드하지 마세요. "
    "동의를 받은 교육용 모의 촬영 영상을 사용하세요."
)

if skill != "손 위생":
    st.info("현재 AI 영상 분석은 손 위생만 지원합니다.")

elif video is None:
    st.info("먼저 손 위생 영상을 업로드하세요.")

else:
    if st.button("🤖 AI 영상 분석 시작", type="primary"):

        temp_path = None
        uploaded_file = None
        client = None

        try:
            # API 키 확인
            api_key = st.secrets["GEMINI_API_KEY"]

            client = genai.Client(api_key=api_key)

            # 업로드 영상을 임시 파일로 저장
            suffix = Path(video.name).suffix

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix
            ) as temp_file:

                temp_file.write(video.getbuffer())
                temp_path = temp_file.name

            # Gemini에 영상 업로드
            with st.spinner("영상을 Gemini에 업로드하고 있습니다..."):

                uploaded_file = client.files.upload(
                    file=temp_path
                )

            # 영상 처리 완료 대기
            with st.spinner("AI가 영상을 준비하고 있습니다..."):

                start_time = time.time()

                while (
                    not uploaded_file.state
                    or uploaded_file.state.name != "ACTIVE"
                ):

                    if time.time() - start_time > 240:
                        raise TimeoutError(
                            "영상 처리 시간이 초과되었습니다. "
                            "짧은 영상으로 다시 시도하세요."
                        )

                    time.sleep(5)

                    uploaded_file = client.files.get(
                        name=uploaded_file.name
                    )

            # 손 위생 분석 요청
            prompt = """
당신은 간호술기 교육을 보조하는 영상 관찰 AI입니다.

업로드된 영상은 손 위생 수행 영상입니다.

다음 6개 항목을 중심으로 영상을 관찰하세요.

1. 손바닥을 서로 문지르기
2. 손등을 서로 문지르기
3. 손가락 사이 문지르기
4. 두 손의 손가락 등 문지르기
5. 엄지손가락 문지르기
6. 손끝과 손톱 밑 문지르기

각 항목은 다음 세 가지 중 하나로 구분하세요.

- 관찰됨: 해당 동작을 영상에서 확인할 수 있음
- 관찰되지 않음: 영상에서 손이 충분히 보이는 상황인데도
  해당 동작이 수행되는 장면을 확인하지 못함
- 확인 불가: 손이 가려지거나 화면 밖에 있어 판단할 수 없음

다음 형식으로 한국어 결과를 작성하세요.

[영상 전체 관찰]
영상에서 확인되는 손 위생 수행 과정을 간략하게 설명하세요.

[항목별 분석]
각 6개 항목에 대해 다음을 작성하세요.
- 항목명
- 판정
- 판단 근거
- 해당 장면의 대략적인 시간(확인 가능한 경우)

[개선 피드백]
영상에서 실제로 확인된 부분에 대해서만 개선점을 제시하세요.

[분석의 한계]
영상만으로 판단할 수 없는 내용과 불확실한 내용을 설명하세요.

중요한 주의사항:
- 영상에 보이지 않는 행동을 임의로 추측하지 마세요.
- 미생물이 제거되었는지 판단하지 마세요.
- 소독제 사용량이나 성분을 영상만으로 단정하지 마세요.
- 관찰되지 않음과 확인 불가를 구분하세요.
- 이 결과는 교육용 보조 분석이며 최종 평가는 교수자가 해야 합니다.
"""

            with st.spinner("Gemini AI가 손 위생 영상을 분석하고 있습니다..."):

                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[uploaded_file, prompt]
                )

            # 분석 결과 출력
            st.success("AI 영상 분석이 완료되었습니다.")

            st.subheader("AI 영상 분석 결과")

            if response.text:
                st.markdown(response.text)
            else:
                st.warning("AI가 텍스트 결과를 반환하지 않았습니다.")

        except KeyError:
            st.error(
                "Gemini API 키를 찾을 수 없습니다. "
                "Streamlit Cloud의 Secrets 설정을 확인하세요."
            )

        except Exception as e:
            st.error("영상 분석 중 오류가 발생했습니다.")
            st.code(str(e))

        finally:
            # Gemini에 업로드한 파일 삭제 시도
            if uploaded_file is not None and client is not None:
                try:
                    client.files.delete(
                        name=uploaded_file.name
                    )
                except Exception:
                    st.warning(
                        "Gemini에 업로드한 임시 파일의 삭제 상태를 "
                        "확인해야 합니다."
                    )

            # PC 임시 파일 삭제
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

            if client is not None:
                client.close()

st.divider()

st.info(
    "Nurse Skill AI는 간호술기 연습을 돕는 교육용 시제품입니다. "
    "AI 결과만으로 실제 임상역량을 판정하지 않습니다."
)

st.caption("Nurse Skill AI | Nursing Skills Practice Assistant")
