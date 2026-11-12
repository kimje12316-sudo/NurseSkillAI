import json
import time

import streamlit as st
from google import genai
from google.genai import types

# ------------------------------------------
# 1. 기본 설정
# ------------------------------------------

st.set_page_config(
    page_title="Nurse Skill AI",
    page_icon="🩺",
    layout="centered",
)

# 앞에서부터 순서대로 시도합니다. 503/429/404가 나면 다음 모델로 넘어갑니다.
# 모델명은 Google AI Studio에서 현재 사용 가능한지 확인하세요.
MODEL_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
]

# 인라인 전송은 요청 전체 크기 제한이 있습니다(20MB 안팎으로 알고 있음).
# 최신 문서를 확인하고, 더 큰 영상이 필요하면 Files API로 바꾸세요.
MAX_VIDEO_MB = 20

CHECKLIST = [
    "손바닥을 서로 문지르기",
    "손등을 서로 문지르기",
    "손가락 사이 문지르기",
    "두 손의 손가락 등 문지르기",
    "엄지손가락 문지르기",
    "손끝과 손톱 밑 문지르기",
]

STATUS_ICON = {"관찰됨": "✅", "관찰되지 않음": "❌", "확인 불가": "❔"}

PROMPT = """
당신은 간호술기 교육을 보조하는 영상 관찰 AI입니다.

업로드된 영상은 손 위생 수행 영상입니다.
아래 6개 항목을 영상에서 관찰하고, 항목마다 판정하세요.

1. 손바닥을 서로 문지르기
2. 손등을 서로 문지르기
3. 손가락 사이 문지르기
4. 두 손의 손가락 등 문지르기
5. 엄지손가락 문지르기
6. 손끝과 손톱 밑 문지르기

판정은 다음 중 하나만 사용하세요.
- 관찰됨
- 관찰되지 않음
- 확인 불가

규칙:
- 보이지 않는 행동을 추측하지 마세요.
- 미생물 제거 여부를 판단하지 마세요.
- 소독제 사용량이나 성분을 단정하지 마세요.
- '관찰되지 않음'(보였는데 하지 않음)과 '확인 불가'(가려지거나 화질 때문에 판단 불가)를 구분하세요.
- 시간은 영상의 타임스탬프 구간(mm:ss~mm:ss)으로 적으세요. 확인할 수 없으면 "해당 없음"이라고 적으세요.
- 빠른 동작은 영상 샘플링 과정에서 놓칠 수 있습니다.
- 최종 평가는 교수자가 합니다.

반드시 아래 JSON 형식으로만 한국어로 답하세요. JSON 이외의 글은 쓰지 마세요.
{
  "items": [
    {
      "name": "항목 이름(위 6개 중 하나, 그대로)",
      "status": "관찰됨 | 관찰되지 않음 | 확인 불가",
      "time_range": "00:05~00:12 또는 해당 없음",
      "evidence": "영상에서 실제로 보인 근거 한 줄"
    }
  ],
  "order_note": "수행 순서와 전체 소요 시간에 대해 영상에서 확인된 내용",
  "feedback": ["영상에서 확인된 내용에 근거한 개선점"],
  "limitations": "영상만으로 판단할 수 없는 내용"
}
"""

# ------------------------------------------
# 2. 세션 상태 초기화
# ------------------------------------------

for key, default in {
    "result": None,
    "used_model": None,
    "result_video_key": None,
    "pending_prefill": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# AI 결과를 체크박스에 반영 (체크박스가 만들어지기 전에 적용해야 함)
if st.session_state.pending_prefill is not None:
    for i, checked in st.session_state.pending_prefill.items():
        st.session_state[f"hand_{i}"] = checked
    st.session_state.pending_prefill = None

# ------------------------------------------
# 3. 함수
# ------------------------------------------


def is_retryable_busy(text: str) -> bool:
    return "503" in text or "UNAVAILABLE" in text


def should_try_next_model(text: str) -> bool:
    return (
        "429" in text
        or "RESOURCE_EXHAUSTED" in text
        or "404" in text
        or "NOT_FOUND" in text
    )


def analyze_with_fallback(client, video_part, status=None):
    """모델 후보를 순서대로 시도하고 (응답, 사용한 모델명)을 돌려줍니다."""
    last_error = None
    busy_error = None  # 503 오류는 원인 파악에 더 유용하므로 따로 보관

    for model in MODEL_CANDIDATES:
        for attempt in range(3):
            try:
                if status is not None:
                    status.write(f"Gemini 분석 요청 중... ({model}, 시도 {attempt + 1}/3)")

                response = client.models.generate_content(
                    model=model,
                    contents=[video_part, PROMPT],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=8000,
                        response_mime_type="application/json",
                    ),
                )
                return response, model

            except Exception as e:
                last_error = e
                text = str(e)

                if is_retryable_busy(text):
                    busy_error = e
                    time.sleep(5 * (attempt + 1))  # 5초, 10초, 15초
                    continue

                if should_try_next_model(text):
                    break  # 이 모델은 건너뛰고 다음 모델로

                raise  # 그 외 오류는 바로 중단

        if status is not None:
            status.write(f"{model} 사용 불가 → 다음 모델로 전환합니다.")

    raise busy_error or last_error


def parse_result(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    data = json.loads(text.strip())
    if "items" not in data or not isinstance(data["items"], list):
        raise ValueError("분석 결과 형식이 올바르지 않습니다.")
    return data


def build_prefill(data: dict) -> dict:
    """AI 판정 '관찰됨'인 항목만 체크 상태로 만듭니다."""
    by_name = {item.get("name"): item for item in data["items"]}
    prefill = {}
    for i, name in enumerate(CHECKLIST):
        item = by_name.get(name)
        if item is None and i < len(data["items"]):
            item = data["items"][i]  # 이름이 달라도 순서로 대응
        prefill[i] = bool(item and item.get("status") == "관찰됨")
    return prefill


def show_error(e: Exception):
    text = str(e)
    if is_retryable_busy(text):
        st.error(
            "Google Gemini 서버가 일시적으로 혼잡합니다. "
            "1~2분 뒤 다시 시도하세요. (영상은 다시 올리지 않아도 됩니다.)"
        )
    elif "429" in text or "RESOURCE_EXHAUSTED" in text:
        st.error(
            "Gemini API 사용량 한도에 도달했을 수 있습니다. "
            "Google AI Studio에서 사용량과 할당량을 확인하세요."
        )
    elif "404" in text or "NOT_FOUND" in text:
        st.error(
            "요청한 모델을 찾을 수 없습니다. "
            "MODEL_CANDIDATES의 모델명을 확인하세요."
        )
    elif isinstance(e, (json.JSONDecodeError, ValueError)):
        st.error(
            "AI 응답을 해석하지 못했습니다. 다시 시도해 주세요. "
            "계속되면 영상 길이를 줄여 보세요."
        )
    else:
        st.error("영상 분석 중 오류가 발생했습니다.")
    with st.expander("오류 상세"):
        st.code(text)


# ------------------------------------------
# 4. 화면: 제목, 술기 선택
# ------------------------------------------

st.title("🩺 Nurse Skill AI")
st.subheader("AI 기반 간호술기 수행 분석 시스템")
st.write(
    "간호술기 영상을 업로드하고 "
    "AI를 활용해 수행 과정을 분석하는 학습 보조 프로그램입니다."
)

st.divider()

st.header("1. 간호술기 선택")

skill = st.selectbox(
    "분석할 간호술기를 선택하세요.",
    ["손 위생", "활력징후 측정", "단순도뇨", "유치도뇨", "기관 내 흡인"],
)
st.success(f"선택한 술기: {skill}")

st.divider()

# ------------------------------------------
# 5. 영상 업로드
# ------------------------------------------

st.header("2. 간호술기 영상 업로드")

video = st.file_uploader(
    "촬영한 간호술기 영상을 선택하세요.",
    type=["mp4", "mov", "avi"],
)

video_ok = False
video_key = None

if video is not None:
    st.video(video)
    st.write("파일 이름:", video.name)
    st.write(f"파일 크기: {video.size / (1024 * 1024):.2f} MB")

    if video.size == 0:
        st.error("영상 파일이 비어 있습니다.")
    elif video.size > MAX_VIDEO_MB * 1024 * 1024:
        st.error(f"현재 시제품은 {MAX_VIDEO_MB}MB 이하의 영상만 지원합니다.")
    else:
        st.success("영상이 업로드되었습니다.")
        video_ok = True
        video_key = (video.name, video.size)

st.divider()

# ------------------------------------------
# 6. 체크리스트
# ------------------------------------------

st.header("3. 간호술기 체크리스트")

if skill == "손 위생":
    st.write(
        "손 위생 수행 항목을 확인하세요. "
        "AI 분석을 실행하면 '관찰됨' 항목이 자동으로 체크되며, 직접 수정할 수 있습니다."
    )

    completed = 0
    for i, item in enumerate(CHECKLIST):
        if st.checkbox(item, key=f"hand_{i}"):
            completed += 1

    total = len(CHECKLIST)
    remaining = total - completed
    progress = completed / total

    st.subheader("체크리스트 진행 상황")
    st.progress(progress)
    st.metric("수행률", f"{progress * 100:.1f}%")

    col1, col2, col3 = st.columns(3)
    col1.metric("완료", f"{completed}개")
    col2.metric("전체", f"{total}개")
    col3.metric("남음", f"{remaining}개")

    if completed == total:
        st.success("모든 항목이 체크되었습니다.")
    elif completed == 0:
        st.info("아직 체크한 항목이 없습니다.")
    else:
        st.warning(f"{remaining}개 항목이 남았습니다.")
else:
    st.info("선택한 술기의 체크리스트는 추후 추가할 예정입니다.")

st.caption("※ 체크 상태는 AI 판정을 바탕으로 하되 사용자가 수정한 결과일 수 있습니다.")

st.divider()

# ------------------------------------------
# 7. AI 영상 분석
# ------------------------------------------

st.header("4. AI 영상 분석")

st.warning(
    "주의: 실제 환자 영상이나 이름, 얼굴, 병원 정보 등 "
    "개인정보가 포함된 영상은 업로드하지 마세요. "
    "동의를 받은 교육용 모의 촬영 영상을 사용하세요. "
    "업로드한 영상은 분석을 위해 Google Gemini 서버로 전송됩니다."
)

rerun_after = False

if skill != "손 위생":
    st.info("현재 AI 영상 분석은 손 위생만 지원합니다.")

elif video is None:
    st.info("먼저 손 위생 영상을 업로드하세요.")

elif not video_ok:
    st.error("정상적인 영상 파일(용량 제한 이내)을 업로드하세요.")

else:
    if st.button("🤖 AI 영상 분석 시작", type="primary"):
        client = None
        try:
            api_key = st.secrets["GEMINI_API_KEY"]

            # SDK 재시도는 짧게, 모델 전환은 analyze_with_fallback에서 처리
            retry_options = types.HttpRetryOptions(
                attempts=2,
                initial_delay=2.0,
                max_delay=10.0,
                exp_base=2.0,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            )
            http_options = types.HttpOptions(
                timeout=120000,
                retry_options=retry_options,
            )
            client = genai.Client(api_key=api_key, http_options=http_options)

            status = st.status("Gemini AI 분석을 준비하고 있습니다.", expanded=True)

            video_part = types.Part.from_bytes(
                data=video.getvalue(),
                mime_type=video.type or "video/mp4",
            )
            # 빠른 동작 인식을 높이려면 SDK 문서를 확인해
            # 영상 fps(프레임 샘플링) 설정을 추가하세요.

            response, used_model = analyze_with_fallback(client, video_part, status)

            if not (response.text or "").strip():
                raise RuntimeError("Gemini가 분석 결과를 반환하지 않았습니다.")

            data = parse_result(response.text)

            st.session_state.result = data
            st.session_state.used_model = used_model
            st.session_state.result_video_key = video_key
            st.session_state.pending_prefill = build_prefill(data)

            status.update(label="Gemini AI 영상 분석 완료!", state="complete")
            rerun_after = True

        except KeyError:
            st.error(
                "Gemini API 키를 찾을 수 없습니다. "
                "Streamlit Secrets에 GEMINI_API_KEY를 설정하세요."
            )
        except Exception as e:
            show_error(e)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

# 분석 성공 시 체크리스트에 결과를 반영하기 위해 다시 실행
if rerun_after:
    st.rerun()

# ------------------------------------------
# 8. 결과 표시 (버튼 바깥: 체크박스를 눌러도 사라지지 않음)
# ------------------------------------------

result = st.session_state.result
if (
    result
    and video_ok
    and st.session_state.result_video_key == video_key
    and skill == "손 위생"
):
    st.subheader("AI 영상 분석 결과")
    st.caption(f"사용 모델: {st.session_state.used_model}")

    for item in result["items"]:
        status_text = item.get("status", "확인 불가")
        icon = STATUS_ICON.get(status_text, "❔")
        st.markdown(
            f"{icon} **{item.get('name', '')}** — {status_text} "
            f"({item.get('time_range', '해당 없음')})"
        )
        st.caption(item.get("evidence", ""))

    if result.get("order_note"):
        st.markdown("**수행 순서·시간**")
        st.write(result["order_note"])

    if result.get("feedback"):
        st.markdown("**개선 피드백**")
        for fb in result["feedback"]:
            st.write(f"- {fb}")

    if result.get("limitations"):
        st.markdown("**분석의 한계**")
        st.write(result["limitations"])

    st.warning(
        "이 분석은 교육용 참고 결과입니다. "
        "실제 간호술기 수행의 최종 평가는 교수자가 확인해야 합니다."
    )

# ------------------------------------------
# 9. 프로그램 안내
# ------------------------------------------

st.divider()

st.info(
    "Nurse Skill AI는 간호술기 연습을 돕는 교육용 시제품입니다. "
    "AI 결과만으로 실제 임상역량을 판정하지 않습니다."
)

st.caption("Nurse Skill AI | Nursing Skills Practice Assistant")
