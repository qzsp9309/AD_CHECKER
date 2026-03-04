import streamlit as st
from PIL import Image
import cv2
import tempfile
import os

st.set_page_config(page_title="소재 규격 검수기", layout="centered")

st.title("📏 광고 소재 사이즈 검수 툴")
st.caption("업로드하신 소재의 비율을 자동으로 체크합니다.")

# 1. 유형 선택
option = st.radio("검수할 유형을 선택하세요", ["이미지", "영상", "캐러셀"], horizontal=True)

# 2. 파일 업로드
uploaded_files = st.file_uploader(f"{option} 파일을 선택하세요", accept_multiple_files=True)

# --- [유형별 안내사항] ---
st.info(f"""
**💡 {option} 안내사항**
- 다른 사이즈로 전달 주신 경우 위아래가 잘릴 수 있습니다.
- 소재 위아래가 잘려 업로드 되더라도 이상이 없다면 진행하셔도 무관합니다.
- **캐러셀 내 영상이 가로형(16:9)일 경우**: 위아래 검은색 바를 추가하여 4:5로 업로드 가능합니다.
- **주의**: 패스트페이퍼에서 별도 영상을 수정할 수 없습니다. 브랜드 측에서 수정하여 전달 필요합니다.
""")

# --- [공통 안내사항] ---
# 여기에 공통으로 들어갈 내용을 적으시면 됩니다.
st.warning("""
**📢 공통 안내사항**
1. 메타가이드 상 해시태그는 '#광고'를 포함한 4개까지 가능합니다.  
           (추가적인 해시태그는 댓글로 작성이 가능합니다.)
2. 릴스 소재로 여러 미디어에 노출시, 메타에서 "추천하지 않는 게시글"로 분류할 가능성이 있습니다.   
           이미지 에셋과 함께 케러셀 형태를 권장드드립니다.  
           * 이 내용은 매체 가이드가 아닌 메타 가이드인점 참고 부탁드립니다.
3. (추가하실 내용을 여기에 작성하세요)
""")

if uploaded_files:
    st.divider()
    for uploaded_file in uploaded_files:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        # --- 이미지 파일 검수 (이미지 메뉴 혹은 캐러셀 내 이미지) ---
        if option == "이미지" or (option == "캐러셀" and file_ext in ['.jpg', '.jpeg', '.png', '.webp']):
            try:
                img = Image.open(uploaded_file)
                w, h = img.size
                ratio = w / h
                
                if abs(ratio - 0.8) < 0.05: # 4:5 비율 (0.8)
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h})")
                else:
                    st.error(f"❌ {uploaded_file.name} 이미지의 사이즈가 틀립니다. 4:5 사이즈로 수정이 필요합니다. (현재 {w}x{h})")
            except Exception as e:
                st.error(f"❌ {uploaded_file.name} 파일을 읽는 중 오류가 발생했습니다.")

        # --- 영상 파일 검수 (영상 메뉴 혹은 캐러셀 내 영상) ---
        elif option == "영상" or (option == "캐러셀" and file_ext in ['.mp4', '.mov', '.avi']):
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tfile:
                tfile.write(uploaded_file.read())
                temp_path = tfile.name

            vf = cv2.VideoCapture(temp_path)
            w = int(vf.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(vf.get(cv2.CAP_PROP_FRAME_HEIGHT))
            vf.release()
            if os.path.exists(temp_path): os.remove(temp_path)

            if w == 0 or h == 0:
                st.error(f"❌ {uploaded_file.name} 영상 데이터를 읽을 수 없습니다.")
                continue

            ratio = w / h
            
            if option == "영상": # 일반 영상 메뉴 (9:16 기준)
                if abs(ratio - 0.5625) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h})")
                else:
                    st.warning(f"⚠️ {uploaded_file.name} 사이즈가 {w}:{h}입니다. 9:16 사이즈가 아니므로, 캐러셀은 4:5로 수정해서 전달 부탁드리며, 그대로 진행 시 위아래가 잘려 업로드됩니다.")
            
            elif option == "캐러셀": # 캐러셀 메뉴 내 영상 (4:5 기준)
                if abs(ratio - 0.8) < 0.05:
                    st.success(f"✅ {uploaded_file.name}: 이상없음 ({w}x{h})")
                elif abs(ratio - 1.77) < 0.1: # 16:9 가로형 영상일 때
                    st.error(f"❌ {uploaded_file.name}: 가로형(16:9) 영상입니다. 위아래 검은색 바를 추가하여 4:5 비율로 수정 후 전달 부탁드립니다. (패스트페이퍼 수정 불가)")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: 4:5 비율이 아닙니다. 그대로 진행 시 위아래가 잘릴 수 있습니다.")