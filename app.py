import os
import json
import shutil
import hashlib
import zipfile
import tempfile
import subprocess
from io import BytesIO

import cv2
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

st.set_page_config(page_title="소재 규격 검수기", layout="centered")

IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]
VIDEO_TYPES = ["mp4", "mov", "avi"]
PREVIEW_MAX = (720, 900)


def ratio_label(w, h):
    if not h:
        return "-"
    r = w / h
    for label, value, tolerance in [("3:4", .75, .03), ("4:5", .8, .03), ("9:16", 9/16, .03), ("1:1", 1, .03), ("16:9", 16/9, .05)]:
        if abs(r-value) < tolerance:
            return label
    return f"{r:.2f}:1"


def target_ratio(fmt):
    return 4/5 if fmt == "4:5" else 9/16


def file_identity(upload):
    # Streamlit 업로드 객체에서 추가적인 전체 바이트 복사를 하지 않음
    return (upload.name, upload.size, hashlib.sha256(upload.getbuffer()).hexdigest())


def temp_upload(upload):
    suffix = os.path.splitext(upload.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as out:
        upload.seek(0)
        shutil.copyfileobj(upload, out, length=1024*1024)
        return out.name


def get_video_info(upload):
    # 동일 파일의 메타데이터는 세션 내에서 재사용. 큰 파일을 캐시로 복제하지 않음.
    key = f"meta:{file_identity(upload)}"
    if key in st.session_state:
        return st.session_state[key]
    path = None
    try:
        path = temp_upload(upload)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            result = (0, 0, 0.0, 0.0)
        else:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            result = (w, h, fps, frames/fps if fps > 0 else 0.0)
        st.session_state[key] = result
        return result
    except Exception:
        return 0, 0, 0.0, 0.0
    finally:
        if path and os.path.exists(path):
            os.remove(path)


def load_image(upload):
    upload.seek(0)
    with Image.open(upload) as original:
        return ImageOps.exif_transpose(original).copy()


def preview_image(img):
    small = img.copy()
    small.thumbnail(PREVIEW_MAX, Image.Resampling.LANCZOS)
    return small


def crop_image(img, fmt, position):
    w, h = img.size
    ratio = target_ratio(fmt)
    if abs(w/h - ratio) < .001:
        return img.copy()
    if w/h > ratio:
        new_w = round(h * ratio)
        x = 0 if position == "좌측" else w-new_w if position == "우측" else (w-new_w)//2
        return img.crop((x, 0, x+new_w, h))
    new_h = round(w/ratio)
    y = 0 if position == "상단" else h-new_h if position == "하단" else (h-new_h)//2
    return img.crop((0, y, w, y+new_h))


def pad_image(img, fmt):
    w, h = img.size
    ratio = target_ratio(fmt)
    if abs(w/h - ratio) < .001:
        return img.copy(), "여백 추가 불필요"
    if w/h > ratio:
        new_w, new_h, label = w, round(w/ratio), "상하 여백"
    else:
        new_w, new_h, label = round(h*ratio), h, "좌우 여백"
    canvas = Image.new("RGB", (new_w, new_h), "black")
    x, y = (new_w-w)//2, (new_h-h)//2
    if img.mode == "RGBA":
        canvas.paste(img, (x, y), img)
    else:
        canvas.paste(img.convert("RGB"), (x, y))
    return canvas, label


def image_bytes(img, extension):
    out = BytesIO()
    if extension == ".png":
        img.save(out, "PNG", optimize=False)
        return out.getvalue(), ".png", "image/png"
    if extension == ".webp":
        img.save(out, "WEBP", lossless=True, quality=100, method=6)
        return out.getvalue(), ".webp", "image/webp"
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(out, "JPEG", quality=100, subsampling=0, optimize=False)
    return out.getvalue(), ".jpg", "image/jpeg"


def video_filter(w, h, fmt, mode, position="중앙"):
    ratio = target_ratio(fmt)
    if mode == "crop":
        if abs(w/h-ratio) < .001:
            return None
        if w/h > ratio:
            cw = max(2, int(h*ratio)//2*2)
            x = 0 if position == "좌측" else w-cw if position == "우측" else (w-cw)//2
            return f"crop={cw}:{h}:{max(0,x//2*2)}:0"
        ch = max(2, int(w/ratio)//2*2)
        y = 0 if position == "상단" else h-ch if position == "하단" else (h-ch)//2
        return f"crop={w}:{ch}:0:{max(0,y//2*2)}"
    if abs(w/h-ratio) < .001:
        return None
    if w/h > ratio:
        nh = max(h, int(w/ratio + .999999))
        nh += nh % 2
        return f"pad={w}:{nh}:0:(oh-ih)/2:black"
    nw = max(w, int(h*ratio + .999999))
    nw += nw % 2
    return f"pad={nw}:{h}:(ow-iw)/2:0:black"


def transform_video(upload, fmt, mode, position):
    src = dst = None
    try:
        src = temp_upload(upload)
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise RuntimeError("영상을 열 수 없습니다.")
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if not w or not h:
            raise RuntimeError("영상 해상도를 확인할 수 없습니다.")
        filt = video_filter(w, h, fmt, mode, position)
        if filt is None:
            # 비율이 이미 일치하면 재인코딩 없이 MP4로 remux
            filt = None
        fd, dst = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
        if filt:
            cmd += ["-vf", filt, "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-threads", "2", "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-c:v", "copy"]
        cmd += ["-c:a", "copy", "-movflags", "+faststart", dst]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError("영상 변환 시간이 5분을 초과했습니다.")
        if result.returncode:
            raise RuntimeError((result.stderr or "FFmpeg 오류")[-1800:])
        cap = cv2.VideoCapture(dst)
        rw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        rh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        with open(dst, "rb") as f:
            data = f.read()
        return data, (w, h), (rw, rh)
    finally:
        for path in (src, dst):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def copy_button(value):
    data = json.dumps(value, ensure_ascii=False)
    components.html(f'''<button id="copy" style="width:100%;padding:11px;border:1px solid #ddd;border-radius:8px;background:white;cursor:pointer" onclick="copyText()">📋 검수 결과 복사</button>
    <script>async function copyText(){{let t={data};try{{await navigator.clipboard.writeText(t)}}catch(e){{let a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}}let b=document.getElementById('copy');b.innerText='✅ 복사 완료';setTimeout(()=>b.innerText='📋 검수 결과 복사',1500)}}</script>''', height=55)


@st.fragment
def validation_section():
    st.header("🔍 소재 검수")
    option = st.radio("검수할 유형을 선택하세요", ["이미지", "영상", "캐러셀"], horizontal=True, key="check_type")
    files = st.file_uploader(f"{option} 파일을 선택하세요", accept_multiple_files=True, key="check_uploader")
    if not files:
        return
    results = []
    for upload in files:
        ext = os.path.splitext(upload.name)[1].lower()
        if option == "이미지" or (option == "캐러셀" and ext in (".jpg", ".jpeg", ".png", ".webp")):
            try:
                img = load_image(upload)
                w, h = img.size
                label = ratio_label(w, h)
                if abs(w/h-.8) < .05:
                    results.append(f"✅ {upload.name}: 이상없음 ({w}x{h}, {label})")
                else:
                    results.append(f"❌ {upload.name}: 이미지 사이즈가 틀립니다. 4:5 사이즈로 수정이 필요합니다. (현재 {w}x{h}, {label})")
                img.close()
            except Exception:
                results.append(f"❌ {upload.name}: 파일을 읽는 중 오류가 발생했습니다.")
        elif option == "영상" or (option == "캐러셀" and ext in (".mp4", ".mov", ".avi")):
            w, h, _, _ = get_video_info(upload)
            if not w or not h:
                results.append(f"❌ {upload.name}: 영상 데이터를 읽을 수 없습니다.")
                continue
            label = ratio_label(w, h)
            r = w/h
            if option == "영상":
                results.append(f"✅ {upload.name}: 이상없음 ({w}x{h}, {label})" if abs(r-9/16)<.05 else f"⚠️ {upload.name}: 현재 사이즈가 {w}x{h} ({label})입니다. 9:16 사이즈가 아니므로, 그대로 진행 시 위아래가 잘려 업로드됩니다.")
            elif abs(r-.8)<.05:
                results.append(f"✅ {upload.name}: 이상없음 ({w}x{h}, {label})")
            elif abs(r-16/9)<.1:
                results.append(f"❌ {upload.name}: 가로형(16:9) 영상입니다. 위아래 검은색 바를 추가하여 4:5 비율로 수정 후 전달 부탁드립니다. (패스트페이퍼 수정 불가, 현재 {w}x{h})")
            else:
                results.append(f"⚠️ {upload.name}: 4:5 비율이 아닙니다. 그대로 진행 시 위아래가 잘릴 수 있습니다. (현재 {w}x{h}, {label})")
        else:
            results.append(f"❌ {upload.name}: 지원하지 않는 파일 형식입니다.")
    text = "\n".join(results)
    st.code(text, language=None, wrap_lines=True)
    copy_button(text)


@st.fragment
def image_section(mode):
    crop = mode == "crop"
    prefix = "crop" if crop else "padding"
    st.header("✂️ 이미지 크롭" if crop else "⬛ 이미지 여백 추가")
    st.caption("원본 이미지를 확대/축소하지 않고 선택한 비율로 크롭합니다." if crop else "원본 이미지를 확대/축소하지 않고 검은색 RGB(0,0,0) 여백을 추가합니다.")
    fmt = st.radio("변환할 이미지 비율", ["4:5", "9:16"], horizontal=True, key=f"{prefix}_format")
    files = st.file_uploader("크롭할 이미지를 선택하세요" if crop else "여백을 추가할 이미지를 선택하세요", type=IMAGE_TYPES, accept_multiple_files=True, key=f"{prefix}_uploader")
    hpos = vpos = "중앙"
    if crop:
        hpos = st.radio("좌우 크롭 기준", ["좌측", "중앙", "우측"], horizontal=True, key="image_crop_horizontal")
        vpos = st.radio("상하 크롭 기준", ["상단", "중앙", "하단"], horizontal=True, key="image_crop_vertical")
    if not files:
        return
    st.subheader("🖼️ 크롭 결과" if crop else "🖼️ 여백 추가 결과")
    for i, upload in enumerate(files):
        try:
            img = load_image(upload)
            w, h = img.size
            if crop:
                pos = hpos if w/h > target_ratio(fmt) else vpos
                out = crop_image(img, fmt, pos)
                direction = pos
            else:
                out, direction = pad_image(img, fmt)
            nw, nh = out.size
            st.write(f"**{upload.name}**")
            st.caption(f"원본: {w} × {h} → 결과: {nw} × {nh} / {fmt} / {direction}")
            st.image(preview_image(out), use_container_width=True)
            ext = os.path.splitext(upload.name)[1].lower()
            # 개별 파일은 클릭 시 원본 해상도 그대로 저장
            data, output_ext, mime = image_bytes(out, ext)
            name = os.path.splitext(upload.name)[0]
            suffix = "" if crop else "_black_padding"
            st.download_button(f"⬇️ {upload.name} 다운로드", data, file_name=f"{name}_{fmt.replace(':','x')}{suffix}{output_ext}", mime=mime, key=f"{prefix}_download_{i}")
            img.close()
            out.close()
            st.divider()
        except Exception as e:
            st.error(f"❌ {upload.name}: 이미지 처리 중 오류가 발생했습니다.")
            st.caption(str(e))
    # ZIP은 요청할 때만 생성하고 설정/파일이 바뀌면 이전 결과를 숨김
    signature = (fmt, hpos, vpos, tuple(file_identity(f) for f in files))
    key = f"{prefix}_zip"
    if st.button("📦 전체 다운로드 준비", key=f"{prefix}_prepare", use_container_width=True):
        zbuf = BytesIO()
        count = 0
        with st.spinner("ZIP 파일 생성 중..."):
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as archive:
                for upload in files:
                    try:
                        img = load_image(upload)
                        w, h = img.size
                        if crop:
                            out = crop_image(img, fmt, hpos if w/h > target_ratio(fmt) else vpos)
                        else:
                            out, _ = pad_image(img, fmt)
                        data, output_ext, _ = image_bytes(out, os.path.splitext(upload.name)[1].lower())
                        name = os.path.splitext(upload.name)[0]
                        suffix = "" if crop else "_black_padding"
                        archive.writestr(f"{name}_{fmt.replace(':','x')}{suffix}{output_ext}", data)
                        count += 1
                        img.close()
                        out.close()
                    except Exception as e:
                        st.warning(f"{upload.name}: ZIP 추가 실패 ({e})")
        st.session_state[key] = (signature, zbuf.getvalue(), count)
    result = st.session_state.get(key)
    if result and result[0] == signature and result[2] > 0:
        suffix = "cropped_images" if crop else "black_padding_images"
        st.download_button(f"⬇️ 전체 {fmt} 이미지 다운로드 ({result[2]}개)", result[1], file_name=f"{fmt.replace(':','x')}_{suffix}.zip", mime="application/zip", use_container_width=True, key=f"{prefix}_zip_download")


@st.fragment
def video_section(mode):
    crop = mode == "crop"
    prefix = "video_crop" if crop else "video_padding"
    st.header("🎬 영상 크롭" if crop else "🎬 영상 여백 추가")
    st.caption("원본 영상을 확대/축소하지 않고 선택한 비율의 영역만 크롭합니다. 영상은 한 번에 1개씩 처리합니다." if crop else "원본 영상을 확대/축소하지 않고 검은색 여백을 추가하여 선택한 비율로 만듭니다. 영상은 한 번에 1개씩 처리합니다.")
    fmt = st.radio("변환할 영상 비율", ["4:5", "9:16"], horizontal=True, key=f"{prefix}_format")
    if not shutil.which("ffmpeg"):
        st.error("FFmpeg가 설치되어 있지 않습니다. packages.txt에 ffmpeg를 추가해주세요.")
    upload = st.file_uploader("크롭할 영상을 선택하세요" if crop else "여백을 추가할 영상을 선택하세요", type=VIDEO_TYPES, key=f"{prefix}_uploader")
    if not upload:
        return
    w, h, fps, duration = get_video_info(upload)
    if not w or not h:
        st.error("영상 정보를 읽을 수 없습니다.")
        return
    st.caption(f"원본: {w} × {h} / {ratio_label(w,h)} / {duration:.1f}초")
    position = "중앙"
    if crop:
        if w/h > target_ratio(fmt):
            position = st.radio("크롭 기준", ["좌측", "중앙", "우측"], horizontal=True, key=f"{prefix}_horizontal")
        elif w/h < target_ratio(fmt):
            position = st.radio("크롭 기준", ["상단", "중앙", "하단"], horizontal=True, key=f"{prefix}_vertical")
        else:
            st.info(f"업로드한 영상이 이미 {fmt} 비율입니다.")
    else:
        direction = "상하 검은 여백" if w/h > target_ratio(fmt) else "좌우 검은 여백" if w/h < target_ratio(fmt) else "여백 추가 불필요"
        st.info(f"목표 비율: **{fmt}**  \n원본: **{w} × {h}**  \n적용 방식: **{direction}**")
    signature = (file_identity(upload), fmt, position)
    result_key = f"{prefix}_result"
    if st.button(f"🎬 {fmt} 영상 {'크롭' if crop else '여백 추가'} 시작", use_container_width=True, key=f"{prefix}_start"):
        if not shutil.which("ffmpeg"):
            st.error("FFmpeg가 설치되어 있지 않습니다.")
        else:
            try:
                with st.spinner("영상 변환 중..."):
                    data, original, output = transform_video(upload, fmt, mode, position)
                base = os.path.splitext(upload.name)[0]
                ending = "crop" if crop else "black_padding"
                st.session_state[result_key] = (signature, data, f"{base}_{fmt.replace(':','x')}_{ending}.mp4", original, output)
            except Exception as e:
                st.session_state.pop(result_key, None)
                st.error("❌ 영상 변환 실패")
                st.caption(str(e))
    result = st.session_state.get(result_key)
    if result and result[0] == signature:
        st.success("✅ 영상 변환 완료")
        st.caption(f"원본: {result[3][0]} × {result[3][1]} → 결과: {result[4][0]} × {result[4][1]} / {ratio_label(*result[4])}")
        st.download_button("⬇️ 크롭 영상 다운로드" if crop else "⬇️ 여백 영상 다운로드", result[1], file_name=result[2], mime="video/mp4", use_container_width=True, key=f"{prefix}_download")


st.title("📏 광고 소재 사이즈 검수 툴")
st.caption("업로드하신 소재의 비율을 자동으로 체크합니다.")
st.markdown("상세 내용은 [**[ 광고 소재 가이드 ]**](https://fastpaepr.myportfolio.com/1696f1f311accb) 확인 부탁드립니다.")
validation_section()
st.divider()
option = st.session_state.get("check_type", "이미지")
st.info(f"**💡 {option} 안내사항**\n\n- 다른 사이즈로 전달 주신 경우 위아래가 잘릴 수 있습니다.\n- 소재 위아래가 잘려 업로드 되더라도 이상이 없다면 진행하셔도 무관합니다.\n- **캐러셀 내 영상이 가로형(16:9)일 경우**: 위아래 검은색 바를 추가하여 4:5로 업로드 가능합니다.\n- **주의**: 패스트페이퍼에서 별도 영상을 수정할 수 없습니다. 브랜드 측에서 수정하여 전달 필요합니다.")
st.warning("**📢 공통 안내사항**\n\n1. 메타 가이드 상 해시태그는 **'#광고'를 포함한 5개까지** 가능합니다. (추가적인 해시태그는 댓글로 작성이 가능합니다.)\n\n2. 릴스 소재로 여러 미디어에 노출 시, 메타에서 '추천하지 않는 게시글'로 분류할 가능성이 있습니다. 이미지 에셋과 함께 **캐러셀 형태를 권장**드립니다. *이 내용은 매체 가이드가 아닌 메타 가이드인 점 참고 부탁드립니다.*")
st.divider()
image_section("crop")
st.divider()
image_section("padding")
st.divider()
video_section("crop")
st.divider()
video_section("padding")
