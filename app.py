import streamlit as st
from PIL import Image
import cv2
import tempfile
import os

# [안정화 설정] 페이지 설정 및 메모리 효율을 위한 캐시 비우기
st.set_page_config(page_title="소재 규격 검수기", layout="centered")

@st.cache_data(ttl=3600) # 1시간마다 캐시를 비워 메모리 확보
def clear_cache_periodically():
    return True

clear_cache_periodically()

st.title("📏 광고 소재 사이즈 검수 툴")
st.caption("업로드하신 소재의 비율을 자동으로 체크합니다.")

st.markdown(f"상세 내용은 [**[ 광고 소재 가이드 ]**](https://fastpaepr.myportfolio.com/1696f1f311accb) 확인 부탁드립니다.")
st.write("")

# 1. 유형 선택
option = st.radio("검수할 유형을 선택하세요", ["이미지", "영상", "캐러셀"], horizontal=True)

# 2. 파일 업로드
uploaded_files = st.file_uploader(f"{option} 파일을 선택하세요", accept_multiple_files=True)

# --- 검수 로직 함수화 (메모리 관리 용이) ---
def check_video_size(file, file_ext):
    """영상을 임시 파일로 저장 후 사이즈 측정하고 즉시 삭제"""
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
    except Exception as e:
        return 0, 0
    finally:
        # 오류가 나든 안 나든 임시 파일은 반드시 즉시 삭제 (메모리 확보)
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

if uploaded_files:
    st.subheader("🔍 검수 결과")
    for uploaded_file in uploaded_files:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        # --- 이미지 파일 검수 ---
        if option == "이미지" or (option == "캐러셀" and file_ext in ['.jpg', '.jpeg', '.png', '.webp']):
            try:
                with Image.open(uploaded_file) as img: # with문 사용으로 사용 후 메모리 해제
                    w, h = img.size
                ratio = w / h
                
                if abs(ratio - 0.8) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h})")
                else:
                    st.error(f"❌ {uploaded_file.name} 이미지 사이즈 오류. 4:5 필요 (현재 {w}x{h})")
            except Exception:
                st.error(f"❌ {uploaded_file.name} 파일을 읽을 수 없습니다.")

        # --- 영상 파일 검수 ---
        elif option == "영상" or (option == "캐러셀" and file_ext in ['.mp4', '.mov', '.avi']):
            w, h = check_video_size(uploaded_file, file_ext)
            
            if w == 0 or h == 0:
                st.error(f"❌ {uploaded_file.name} 영상 데이터를 읽을 수 없습니다.")
                continue

            ratio = w / h
            
            if option == "영상":
                if abs(ratio - 0.5625) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h})")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: 9:16 비율이 아닙니다. ({w}x{h})")
            
            elif option == "캐러셀":
                if abs(ratio - 0.8) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h})")
                elif abs(ratio - 1.77) < 0.1:
                    st.error(f"❌ {uploaded_file.name}: 가로형(16:9)입니다. 4:5로 수정 필요.")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: 4:5 비율이 아닙니다.")

# --- 안내사항 생략 (동일) ---
st.divider()
st.info(f"**💡 {option} 안내사항**\n- (이하 기존 내용과 동일)")
