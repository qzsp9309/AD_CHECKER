import streamlit as st
from PIL import Image
import cv2
import tempfile
import os
from io import BytesIO

# [안정화 설정] 페이지 설정 및 메모리 효율을 위한 캐시 관리
st.set_page_config(page_title="소재 규격 검수기", layout="centered")

@st.cache_data(ttl=3600)
def clear_cache_periodically():
    """1시간마다 캐시를 비워 메모리 누적 방지"""
    return True

clear_cache_periodically()

st.title("📏 광고 소재 사이즈 검수 툴")
st.caption("업로드하신 소재의 비율을 자동으로 체크합니다.")

# --- [하이퍼링크 추가 섹션] ---
st.markdown(f"상세 내용은 [**[ 광고 소재 가이드 ]**](https://fastpaepr.myportfolio.com/1696f1f311accb) 확인 부탁드립니다.")
st.write("")

# 1. 유형 선택
option = st.radio("검수할 유형을 선택하세요", ["이미지", "영상", "캐러셀"], horizontal=True)

# 2. 파일 업로드
uploaded_files = st.file_uploader(f"{option} 파일을 선택하세요", accept_multiple_files=True)

# --- 영상 처리 함수 (메모리 해제 최적화) ---
def get_video_dimensions(file, file_ext):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tfile:
            tfile.write(file.read())
            temp_path = tfile.name

        vf = cv2.VideoCapture(temp_path)
        w = int(vf.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(vf.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vf.release()
        return w, h
    except Exception:
        return 0, 0
    finally:
        # 파일 처리가 끝나면 즉시 삭제하여 서버 용량 확보
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# --- 검수 로직 시작 ---
if uploaded_files:
    st.subheader("🔍 검수 결과")
    for uploaded_file in uploaded_files:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        # 비율 계산 함수
        def get_ratio_str(w, h):
            r = w / h
            if abs(r - 0.8) < 0.05: return "4:5"
            if abs(r - 0.5625) < 0.05: return "9:16"
            if abs(r - 1.0) < 0.05: return "1:1"
            if abs(r - 1.77) < 0.1: return "16:9"
            return f"{w/h:.2f}:1"

        # --- 이미지 및 캐러셀 이미지 검수 ---
        if option == "이미지" or (option == "캐러셀" and file_ext in ['.jpg', '.jpeg', '.png', '.webp']):
            try:
                with Image.open(uploaded_file) as img:
                    w, h = img.size
                r_str = get_ratio_str(w, h)
                if abs((w/h) - 0.8) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h}, {r_str})")
                else:
                    # 줄바꿈 없이 문구 유지
                    st.error(f"❌ {uploaded_file.name}: 이미지 사이즈가 틀립니다. 4:5 사이즈로 수정이 필요합니다. (현재 {w}x{h}, {r_str})")
            except Exception:
                st.error(f"❌ {uploaded_file.name}: 파일을 읽는 중 오류가 발생했습니다.")

        # --- 영상 및 캐러셀 영상 검수 ---
        elif option == "영상" or (option == "캐러셀" and file_ext in ['.mp4', '.mov', '.avi']):
            w, h = get_video_dimensions(uploaded_file, file_ext)
            if w == 0 or h == 0:
                st.error(f"❌ {uploaded_file.name}: 영상 데이터를 읽을 수 없습니다.")
                continue
            
            r_str = get_ratio_str(w, h)
            ratio = w / h
            
            if option == "영상": # 9:16 기준
                if abs(ratio - 0.5625) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h}, {r_str})")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: 현재 사이즈가 {w}x{h}({r_str})입니다. 9:16 사이즈가 아니므로, 그대로 진행 시 위아래가 잘려 업로드됩니다.")
            
            elif option == "캐러셀": # 4:5 기준
                if abs(ratio - 0.8) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h}, {r_str})")
                elif abs(ratio - 1.77) < 0.1:
                    st.error(f"❌ {uploaded_file.name}: 가로형(16:9) 영상입니다. 위아래 검은색 바를 추가하여 4:5 비율로 수정 후 전달 부탁드립니다. (패스트페이퍼 수정 불가, 현재 {w}x{h})")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: 4:5 비율이 아닙니다. 그대로 진행 시 위아래가 잘릴 수 있습니다. (현재 {w}x{h}, {r_str})")

# --- 안내사항 영역 ---
st.divider()

st.info(f"""
**💡 {option} 안내사항**
- 다른 사이즈로 전달 주신 경우 위아래가 잘릴 수 있습니다.
- 소재 위아래가 잘려 업로드 되더라도 이상이 없다면 진행하셔도 무관합니다.
- **캐러셀 내 영상이 가로형(16:9)일 경우**: 위아래 검은색 바를 추가하여 4:5로 업로드 가능합니다.
- **주의**: 패스트페이퍼에서 별도 영상을 수정할 수 없습니다. 브랜드 측에서 수정하여 전달 필요합니다.
""")

st.warning("""
**📢 공통 안내사항**
1. 메타 가이드 상 해시태그는 **'#광고'를 포함한 5개까지** 가능합니다.  
   (추가적인 해시태그는 댓글로 작성이 가능합니다.)
2. 릴스 소재로 여러 미디어에 노출 시, 메타에서 "추천하지 않는 게시글"로 분류할 가능성이 있습니다.  
   이미지 에셋과 함께 **캐러셀 형태를 권장**드립니다.  
   * 이 내용은 매체 가이드가 아닌 메타 가이드인 점 참고 부탁드립니다.
""")

# =========================================================
# 4:5 이미지 자동 크롭
# =========================================================

st.divider()

st.header("✂️ 4:5 이미지 크롭")
st.caption(
    "이미지를 업로드하면 원본 해상도를 확대하지 않고 "
    "4:5 비율로 자동 크롭합니다."
)


# --- 4:5 크롭 함수 ---
def crop_image_to_4_5(img, crop_position="중앙"):

    target_ratio = 4 / 5

    w, h = img.size
    current_ratio = w / h

    # 이미 4:5인 경우
    if abs(current_ratio - target_ratio) < 0.001:
        return img.copy()

    # -----------------------------------------
    # 가로가 넓은 이미지
    # 좌우를 잘라서 4:5 생성
    # -----------------------------------------
    if current_ratio > target_ratio:

        new_width = int(h * target_ratio)

        # 좌우는 중앙 기준으로 크롭
        left = (w - new_width) // 2

        crop_box = (
            left,
            0,
            left + new_width,
            h
        )

    # -----------------------------------------
    # 세로가 긴 이미지
    # 위/아래를 잘라서 4:5 생성
    # -----------------------------------------
    else:

        new_height = int(w / target_ratio)

        if crop_position == "상단":

            top = 0

        elif crop_position == "하단":

            top = h - new_height

        else:
            # 중앙
            top = (h - new_height) // 2

        crop_box = (
            0,
            top,
            w,
            top + new_height
        )

    return img.crop(crop_box)


# --- 이미지 업로드 ---
crop_files = st.file_uploader(
    "크롭할 이미지를 선택하세요",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    key="crop_uploader"
)


# --- 크롭 위치 선택 ---
crop_position = st.radio(
    "크롭 기준",
    ["중앙", "상단", "하단"],
    horizontal=True,
    key="crop_position"
)


# --- 이미지 처리 ---
if crop_files:

    st.subheader("🖼️ 크롭 결과")

    for crop_file in crop_files:

        try:

            file_ext = os.path.splitext(
                crop_file.name
            )[1].lower()

            # 이미지 열기
            img = Image.open(crop_file)

            original_w, original_h = img.size

            # EXIF 회전 정보 적용
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)

            # 실제 회전 적용 후 사이즈 다시 확인
            original_w, original_h = img.size

            # 4:5 크롭
            cropped_img = crop_image_to_4_5(
                img,
                crop_position
            )

            new_w, new_h = cropped_img.size

            # 파일 정보 표시
            st.write(
                f"**{crop_file.name}**"
            )

            st.caption(
                f"원본: {original_w} × {original_h}  →  "
                f"크롭: {new_w} × {new_h}"
            )

            # 미리보기
            st.image(
                cropped_img,
                caption=f"{crop_position} 기준 4:5 크롭",
                use_container_width=True
            )

            # -----------------------------------------
            # 다운로드 파일 생성
            # -----------------------------------------

            buffer = BytesIO()

            original_name = os.path.splitext(
                crop_file.name
            )[0]

            # PNG
            if file_ext == ".png":

                cropped_img.save(
                    buffer,
                    format="PNG",
                    optimize=False
                )

                download_ext = ".png"
                mime_type = "image/png"


            # WEBP
            elif file_ext == ".webp":

                cropped_img.save(
                    buffer,
                    format="WEBP",
                    lossless=True,
                    quality=100,
                    method=6
                )

                download_ext = ".webp"
                mime_type = "image/webp"


            # JPG / JPEG
            else:

                # JPEG은 RGB 필요
                if cropped_img.mode not in ("RGB", "L"):
                    cropped_img = cropped_img.convert("RGB")

                cropped_img.save(
                    buffer,
                    format="JPEG",
                    quality=100,
                    subsampling=0,
                    optimize=False
                )

                download_ext = ".jpg"
                mime_type = "image/jpeg"


            buffer.seek(0)

            # 다운로드 버튼
            st.download_button(
                label=f"⬇️ {crop_file.name} 다운로드",
                data=buffer.getvalue(),
                file_name=f"{original_name}_4x5{download_ext}",
                mime=mime_type,
                key=f"download_{crop_file.name}"
            )

            st.divider()


        except Exception as e:

            st.error(
                f"❌ {crop_file.name}: "
                f"이미지 처리 중 오류가 발생했습니다."
            )

            st.caption(str(e))
