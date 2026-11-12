
import streamlit as st
import tempfile
import os
import time
from pathlib import Path
from google import genai
from google.genai import types

# ------------------------------------------
# 1. 기본 설정
# ------------------------------------------

st.set_page_config(
    page_title="Nurse Skill AI",
    page_icon="🩺",
    layout="centered"
)

MODEL_NAME = "gemini-3.8-flash"

st.title("🩺 Nurse Skill AI")
st.subheader("AI 기반 간호술기 수행 분석 시스템")

st.write(
    "간호술기 영상을 업로드하고 "
    "AI를 활용해 수행 과정을 분석하는 학습 보조 프로그램입니다."
)

st.divider()

# ------------------------------------------
# 2. 간호술기 선택
# ------------------------------------------

st.header("1. 간호술기 선택")

skill = st.selectbox(
    "분석할 간호술기를 선택하세요.",
    ["손 위생", "활력징후 측정", "단순도뇨", "유치도뇨", "기관 내 흡인"]
)

st.success(f"선택한 술기: {skill}")

st.divider()

# ------------------------------------------
# 3. 영상 업로드
# ------------------------------------------

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

    if video.size == 0:
        st.error("영상 파일이 비어 있습니다.")

    elif video.size > 100 * 1024 * 1024:
        st.error("현재 시제품은 100MB 이하의 영상을 권장합니다.")

st.divider()

# ------------------------------------------
# 4. 손 위생 체크리스트
# ------------------------------------------

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

# ------------------------------------------
# 5. Gemini AI 영상 분석
# ------------------------------------------

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

elif video.size == 0:

    st.error("정상적인 영상 파일을 업로드하세요.")

elif video.size > 100 * 1024 * 1024:

    st.error("100MB 이하의 영상을 업로드하세요.")

else:

    if st.button("🤖 AI 영상 분석 시작", type="primary"):

        temp_path = None
        uploaded_file = None
        client = None
        analysis_status = None

        try:

            # 1) API 키 확인
            api_key = st.secrets["GEMINI_API_KEY"]

            # 2) Gemini 클라이언트 생성
            # 요청당 120초 제한
            # 일시적인 서버 오류는 SDK가 자동 재시도
            retry_options = types.HttpRetryOptions(
                attempts=3,
                initial_delay=2.0,
                max_delay=8.0,
                exp_base=2.0,
                http_status_codes=[
                    408, 429, 500, 502, 503, 504
                ]
            )

            http_options = types.HttpOptions(
                timeout=120000,
                retry_options=retry_options
            )

            client = genai.Client(
                api_key=api_key,
                http_options=http_options
            )


            # 3) 작은 MP4 영상을 인라인 방식으로 준비
            analysis_status = st.status(
                "Gemini AI 분석을 준비하고 있습니다.",
                expanded=True
            )

            analysis_status.write("① 영상 데이터 확인 중...")

            video_bytes = video.getvalue()

            video_part = types.Part.from_bytes(
                data=video_bytes,
                mime_type="video/mp4"
            )

            analysis_status.write("② 영상 데이터 준비 완료.")
            analysis_status.write("③ Gemini AI 분석 요청 중...")

            # 4) 분석 프롬프트
            prompt = """
당신은 간호술기 교육을 보조하는 영상 관찰 AI입니다.

업로드된 영상은 손 위생 수행 영상입니다.

다음 6개 항목을 관찰하세요.

1. 손바닥을 서로 문지르기
2. 손등을 서로 문지르기
3. 손가락 사이 문지르기
4. 두 손의 손가락 등 문지르기
5. 엄지손가락 문지르기
6. 손끝과 손톱 밑 문지르기

각 항목은 다음 중 하나로 구분하세요.

- 관찰됨
- 관찰되지 않음
- 확인 불가

다음 형식으로 한국어 결과를 작성하세요.

[영상 전체 관찰]
확인 가능한 손 위생 수행 과정

[항목별 분석]
각 항목의 판정, 판단 근거, 대략적인 시간

[개선 피드백]
실제 영상에서 확인된 내용에 한해 개선점 제시

[분석의 한계]
영상만으로 판단할 수 없는 내용 설명

주의사항:
- 보이지 않는 행동을 추측하지 마세요.
- 미생물 제거 여부를 판단하지 마세요.
- 소독제 사용량이나 성분을 단정하지 마세요.
- 관찰되지 않음과 확인 불가를 구분하세요.
- 빠른 동작은 영상 샘플링 과정에서 놓칠 수 있습니다.
- 최종 평가는 교수자가 해야 합니다.
"""

            # 5) Gemini 스트리밍 분석
            analysis_status.write(
                "④ Gemini가 영상을 분석하고 있습니다."
            )

            result_placeholder = st.empty()
            full_text = ""

            response_stream = client.models.generate_content_stream(
                model=MODEL_NAME,
                contents=[
                    video_part,
                    prompt
                ],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1800
                )
            )

            for chunk in response_stream:
                if chunk.text:
                    full_text += chunk.text
                    result_placeholder.markdown(full_text)

            if not full_text.strip():
                raise RuntimeError(
                    "Gemini가 분석 결과를 반환하지 않았습니다."
                )

            analysis_status.update(
                label="Gemini AI 영상 분석 완료!",
                state="complete"
            )

            st.success("AI 영상 분석이 완료되었습니다.")
            st.subheader("AI 영상 분석 결과")
            st.markdown(full_text)


            for chunk in response_stream:

                if chunk.text:
                    full_text += chunk.text
                    result_placeholder.markdown(full_text)

            if not full_text.strip():
                raise RuntimeError(
                    "Gemini가 분석 텍스트를 반환하지 않았습니다."
                )

            analysis_status.update(
                label="Gemini AI 영상 분석 완료!",
                state="complete"
            )

            st.success("AI 영상 분석이 완료되었습니다.")

            st.subheader("AI 영상 분석 결과")

            st.markdown(full_text)

            st.warning(
                "이 분석은 교육용 참고 결과입니다. "
                "실제 간호술기 수행의 최종 평가는 교수자가 확인해야 합니다."
            )

        except KeyError:

            st.error(
                "Gemini API 키를 찾을 수 없습니다. "
                "Streamlit Cloud의 Secrets 설정을 확인하세요."
            )

        except TimeoutError as e:

            if analysis_status is not None:
                analysis_status.update(
                    label="분석 시간 초과",
                    state="error"
                )

            st.error(str(e))

        except Exception as e:

            if analysis_status is not None:
                analysis_status.update(
                    label="AI 분석 실패",
                    state="error"
                )

            error_text = str(e)

            if "503" in error_text or "UNAVAILABLE" in error_text:

                st.error(
                    "Google Gemini 서버가 일시적으로 혼잡합니다. "
                    "잠시 후 다시 시도하세요."
                )

            elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:

                st.error(
                    "Gemini API 사용량 한도에 도달했을 수 있습니다. "
                    "Google AI Studio에서 사용량과 할당량을 확인하세요."
                )

            elif "404" in error_text or "NOT_FOUND" in error_text:

                st.error(
                    "요청한 모델 또는 파일을 찾을 수 없습니다. "
                    "모델 이름과 API 설정을 확인해야 합니다."
                )

            else:

                st.error("영상 분석 중 오류가 발생했습니다.")

            st.code(error_text)

                finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

            # 9) PC 임시 파일 삭제
            if temp_path and os.path.exists(temp_path):

                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            # 10) Gemini 클라이언트 종료
            if client is not None:

                try:
                    client.close()
                except Exception:
                    pass

# ------------------------------------------
# 6. 프로그램 안내
# ------------------------------------------

st.divider()

st.info(
    "Nurse Skill AI는 간호술기 연습을 돕는 교육용 시제품입니다. "
    "AI 결과만으로 실제 임상역량을 판정하지 않습니다."
)

st.caption(
    "Nurse Skill AI | Nursing Skills Practice Assistant"
)
