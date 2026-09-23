import streamlit as st
from PIL import Image, ImageOps
import cv2
import tempfile
import os
import zipfile
import json
import subprocess
import shutil
from io import BytesIO
import streamlit.components.v1 as components


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="소재 규격 검수기",
    layout="centered"
)


@st.cache_data(ttl=3600)
def clear_cache_periodically():
    return True


clear_cache_periodically()


# =========================================================
# 공통 함수
# =========================================================

def get_ratio_str(w, h):

    if h == 0:
        return "-"

    r = w / h

    if abs(r - 0.75) < 0.03:
        return "3:4"

    if abs(r - 0.8) < 0.03:
        return "4:5"

    if abs(r - 0.5625) < 0.03:
        return "9:16"

    if abs(r - 1.0) < 0.03:
        return "1:1"

    if abs(r - (16 / 9)) < 0.05:
        return "16:9"

    return f"{r:.2f}:1"


def get_target_ratio(target_format):

    if target_format == "4:5":
        return 4 / 5

    elif target_format == "9:16":
        return 9 / 16

    else:
        raise ValueError(
            "지원하지 않는 목표 비율입니다."
        )


def get_video_dimensions(file, file_ext):

    temp_path = None

    try:

        file.seek(0)

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext
        ) as tfile:

            tfile.write(file.read())
            temp_path = tfile.name

        vf = cv2.VideoCapture(temp_path)

        w = int(
            vf.get(cv2.CAP_PROP_FRAME_WIDTH)
        )

        h = int(
            vf.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )

        fps = vf.get(
            cv2.CAP_PROP_FPS
        )

        frame_count = int(
            vf.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        vf.release()

        duration = 0

        if fps and fps > 0:
            duration = frame_count / fps

        return (
            w,
            h,
            fps,
            duration
        )

    except Exception:

        return (
            0,
            0,
            0,
            0
        )

    finally:

        if (
            temp_path
            and os.path.exists(temp_path)
        ):
            os.remove(temp_path)


def save_image_to_buffer(
    img,
    file_ext
):

    buffer = BytesIO()

    if file_ext == ".png":

        img.save(
            buffer,
            format="PNG",
            optimize=False
        )

        download_ext = ".png"
        mime_type = "image/png"

    elif file_ext == ".webp":

        img.save(
            buffer,
            format="WEBP",
            lossless=True,
            quality=100,
            method=6
        )

        download_ext = ".webp"
        mime_type = "image/webp"

    else:

        if img.mode not in (
            "RGB",
            "L"
        ):
            img = img.convert("RGB")

        img.save(
            buffer,
            format="JPEG",
            quality=100,
            subsampling=0,
            optimize=False
        )

        download_ext = ".jpg"
        mime_type = "image/jpeg"

    buffer.seek(0)

    return (
        buffer.getvalue(),
        download_ext,
        mime_type
    )


# =========================================================
# 이미지 4:5 크롭
# =========================================================

def crop_image_to_4_5(
    img,
    crop_position="중앙"
):

    target_ratio = 4 / 5

    w, h = img.size
    current_ratio = w / h

    if abs(
        current_ratio - target_ratio
    ) < 0.001:

        return img.copy()

    # 가로가 넓음 → 좌우 크롭
    if current_ratio > target_ratio:

        new_width = round(
            h * target_ratio
        )

        left = (
            w - new_width
        ) // 2

        crop_box = (
            left,
            0,
            left + new_width,
            h
        )

    # 세로가 김 → 상하 크롭
    else:

        new_height = round(
            w / target_ratio
        )

        if crop_position == "상단":

            top = 0

        elif crop_position == "하단":

            top = h - new_height

        else:

            top = (
                h - new_height
            ) // 2

        crop_box = (
            0,
            top,
            w,
            top + new_height
        )

    return img.crop(
        crop_box
    )


# =========================================================
# 이미지 4:5 검은 여백
# =========================================================

def add_black_padding_to_4_5(
    img,
    padding_direction
):

    target_ratio = 4 / 5

    w, h = img.size
    current_ratio = w / h

    if abs(
        current_ratio - target_ratio
    ) < 0.001:

        return img.copy()

    # 상하 여백
    if padding_direction == "상하 여백":

        if current_ratio < target_ratio:

            raise ValueError(
                "이 이미지는 상하 여백으로 "
                "4:5를 만들 수 없습니다. "
                "좌우 여백을 선택해주세요."
            )

        new_height = round(
            w / target_ratio
        )

        canvas = Image.new(
            "RGB",
            (
                w,
                new_height
            ),
            (
                0,
                0,
                0
            )
        )

        top = (
            new_height - h
        ) // 2

        if img.mode == "RGBA":

            canvas.paste(
                img,
                (
                    0,
                    top
                ),
                img
            )

        else:

            if img.mode != "RGB":
                img = img.convert("RGB")

            canvas.paste(
                img,
                (
                    0,
                    top
                )
            )

        return canvas

    # 좌우 여백
    elif padding_direction == "좌우 여백":

        if current_ratio > target_ratio:

            raise ValueError(
                "이 이미지는 좌우 여백으로 "
                "4:5를 만들 수 없습니다. "
                "상하 여백을 선택해주세요."
            )

        new_width = round(
            h * target_ratio
        )

        canvas = Image.new(
            "RGB",
            (
                new_width,
                h
            ),
            (
                0,
                0,
                0
            )
        )

        left = (
            new_width - w
        ) // 2

        if img.mode == "RGBA":

            canvas.paste(
                img,
                (
                    left,
                    0
                ),
                img
            )

        else:

            if img.mode != "RGB":
                img = img.convert("RGB")

            canvas.paste(
                img,
                (
                    left,
                    0
                )
            )

        return canvas

    raise ValueError(
        "올바른 여백 방향을 선택해주세요."
    )


# =========================================================
# FFmpeg
# =========================================================

def ffmpeg_available():

    return (
        shutil.which("ffmpeg")
        is not None
    )


def run_ffmpeg(
    input_path,
    output_path,
    video_filter
):

    command = [
        "ffmpeg",
        "-y",

        "-i",
        input_path,

        "-vf",
        video_filter,

        "-c:v",
        "libx264",

        "-crf",
        "16",

        "-preset",
        "medium",

        "-pix_fmt",
        "yuv420p",

        # 원본 FPS 유지
        # 별도 -r 옵션을 넣지 않음

        # 오디오 원본 스트림 유지
        "-c:a",
        "copy",

        "-movflags",
        "+faststart",

        output_path
    ]

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if process.returncode != 0:

        raise RuntimeError(
            process.stderr[-3000:]
        )


# =========================================================
# 영상 크롭 필터
# =========================================================

def get_video_crop_filter(
    w,
    h,
    target_format,
    position
):

    target_ratio = get_target_ratio(
        target_format
    )

    current_ratio = w / h

    # 이미 목표 비율
    if abs(
        current_ratio - target_ratio
    ) < 0.001:

        return (
            f"crop={w}:{h}:0:0"
        )

    # =====================================================
    # 원본이 목표보다 가로로 넓음
    # → 좌우를 자름
    # =====================================================

    if current_ratio > target_ratio:

        crop_w = int(
            h * target_ratio
        )

        # H.264 호환성을 위해 짝수
        crop_w -= (
            crop_w % 2
        )

        if position == "좌측":

            x = 0

        elif position == "우측":

            x = w - crop_w

        else:

            x = (
                w - crop_w
            ) // 2

        x -= (
            x % 2
        )

        return (
            f"crop="
            f"{crop_w}:"
            f"{h}:"
            f"{x}:"
            f"0"
        )

    # =====================================================
    # 원본이 목표보다 세로로 김
    # → 상하를 자름
    # =====================================================

    else:

        crop_h = int(
            w / target_ratio
        )

        crop_h -= (
            crop_h % 2
        )

        if position == "상단":

            y = 0

        elif position == "하단":

            y = h - crop_h

        else:

            y = (
                h - crop_h
            ) // 2

        y -= (
            y % 2
        )

        return (
            f"crop="
            f"{w}:"
            f"{crop_h}:"
            f"0:"
            f"{y}"
        )


# =========================================================
# 영상 검은 여백 필터
# =========================================================

def get_video_padding_filter(
    w,
    h,
    target_format
):

    target_ratio = get_target_ratio(
        target_format
    )

    current_ratio = w / h

    # 이미 목표 비율
    if abs(
        current_ratio - target_ratio
    ) < 0.001:

        return (
            f"pad={w}:{h}:0:0:black"
        )

    # =====================================================
    # 원본이 목표보다 가로로 넓음
    # → 상하 검은 여백
    # =====================================================

    if current_ratio > target_ratio:

        new_h = int(
            w / target_ratio
        )

        if new_h % 2 != 0:
            new_h += 1

        y = (
            new_h - h
        ) // 2

        y -= (
            y % 2
        )

        return (
            f"pad="
            f"{w}:"
            f"{new_h}:"
            f"0:"
            f"{y}:"
            f"black"
        )

    # =====================================================
    # 원본이 목표보다 세로로 김
    # → 좌우 검은 여백
    # =====================================================

    else:

        new_w = int(
            h * target_ratio
        )

        if new_w % 2 != 0:
            new_w += 1

        x = (
            new_w - w
        ) // 2

        x -= (
            x % 2
        )

        return (
            f"pad="
            f"{new_w}:"
            f"{h}:"
            f"{x}:"
            f"0:"
            f"black"
        )


# =========================================================
# 영상 처리 공통
# =========================================================

def process_video(
    uploaded_file,
    mode,
    target_format,
    crop_position="중앙"
):

    input_path = None
    output_path = None

    try:

        original_ext = os.path.splitext(
            uploaded_file.name
        )[1].lower()

        uploaded_file.seek(0)

        # 원본 임시파일
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=original_ext
        ) as temp_input:

            temp_input.write(
                uploaded_file.read()
            )

            input_path = (
                temp_input.name
            )

        # 영상 정보
        vf = cv2.VideoCapture(
            input_path
        )

        w = int(
            vf.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        h = int(
            vf.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        fps = vf.get(
            cv2.CAP_PROP_FPS
        )

        vf.release()

        if w == 0 or h == 0:

            raise ValueError(
                "영상 사이즈를 확인할 수 없습니다."
            )

        # 필터 생성
        if mode == "crop":

            video_filter = (
                get_video_crop_filter(
                    w,
                    h,
                    target_format,
                    crop_position
                )
            )

        elif mode == "padding":

            video_filter = (
                get_video_padding_filter(
                    w,
                    h,
                    target_format
                )
            )

        else:

            raise ValueError(
                "잘못된 영상 처리 방식입니다."
            )

        # 출력 임시파일
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp4"
        ) as temp_output:

            output_path = (
                temp_output.name
            )

        if os.path.exists(
            output_path
        ):
            os.remove(
                output_path
            )

        # FFmpeg 실행
        run_ffmpeg(
            input_path,
            output_path,
            video_filter
        )

        # 결과 읽기
        with open(
            output_path,
            "rb"
        ) as result_file:

            result_data = (
                result_file.read()
            )

        # 결과 사이즈 확인
        result_vf = cv2.VideoCapture(
            output_path
        )

        result_w = int(
            result_vf.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        result_h = int(
            result_vf.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        result_vf.release()

        return (
            result_data,
            w,
            h,
            result_w,
            result_h,
            fps
        )

    finally:

        if (
            input_path
            and os.path.exists(
                input_path
            )
        ):
            os.remove(
                input_path
            )

        if (
            output_path
            and os.path.exists(
                output_path
            )
        ):
            os.remove(
                output_path
            )


# =========================================================
# 메인
# =========================================================

st.title(
    "📏 광고 소재 사이즈 검수 툴"
)

st.caption(
    "업로드하신 소재의 비율을 자동으로 체크합니다."
)

st.markdown(
    "상세 내용은 "
    "[**[ 광고 소재 가이드 ]**]"
    "(https://fastpaepr.myportfolio.com/1696f1f311accb) "
    "확인 부탁드립니다."
)

st.write("")


# =========================================================
# 1. 소재 검수
# =========================================================

option = st.radio(
    "검수할 유형을 선택하세요",
    [
        "이미지",
        "영상",
        "캐러셀"
    ],
    horizontal=True
)


uploaded_files = st.file_uploader(
    f"{option} 파일을 선택하세요",
    accept_multiple_files=True,
    key="check_uploader"
)


results = []


if uploaded_files:

    st.subheader(
        "🔍 검수 결과"
    )

    for uploaded_file in uploaded_files:

        file_ext = os.path.splitext(
            uploaded_file.name
        )[1].lower()

        # 이미지 / 캐러셀 이미지
        if (
            option == "이미지"
            or (
                option == "캐러셀"
                and file_ext in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                ]
            )
        ):

            try:

                uploaded_file.seek(0)

                with Image.open(
                    uploaded_file
                ) as img:

                    img = (
                        ImageOps.exif_transpose(
                            img
                        )
                    )

                    w, h = img.size

                r_str = get_ratio_str(
                    w,
                    h
                )

                if abs(
                    (w / h) - 0.8
                ) < 0.05:

                    results.append(
                        f"✅ {uploaded_file.name}: "
                        f"이상없음 "
                        f"({w}x{h}, {r_str})"
                    )

                else:

                    results.append(
                        f"❌ {uploaded_file.name}: "
                        f"이미지 사이즈가 틀립니다. "
                        f"4:5 사이즈로 수정이 필요합니다. "
                        f"(현재 {w}x{h}, {r_str})"
                    )

            except Exception:

                results.append(
                    f"❌ {uploaded_file.name}: "
                    f"파일을 읽는 중 오류가 발생했습니다."
                )

        # 영상 / 캐러셀 영상
        elif (
            option == "영상"
            or (
                option == "캐러셀"
                and file_ext in [
                    ".mp4",
                    ".mov",
                    ".avi"
                ]
            )
        ):

            (
                w,
                h,
                fps,
                duration
            ) = get_video_dimensions(
                uploaded_file,
                file_ext
            )

            if w == 0 or h == 0:

                results.append(
                    f"❌ {uploaded_file.name}: "
                    f"영상 데이터를 읽을 수 없습니다."
                )

                continue

            r_str = get_ratio_str(
                w,
                h
            )

            ratio = w / h

            # 일반 영상 = 9:16
            if option == "영상":

                if abs(
                    ratio - (9 / 16)
                ) < 0.05:

                    results.append(
                        f"✅ {uploaded_file.name}: "
                        f"이상없음 "
                        f"({w}x{h}, {r_str})"
                    )

                else:

                    results.append(
                        f"⚠️ {uploaded_file.name}: "
                        f"현재 사이즈가 "
                        f"{w}x{h} ({r_str})입니다. "
                        f"9:16 사이즈가 아니므로, "
                        f"그대로 진행 시 위아래가 "
                        f"잘려 업로드됩니다."
                    )

            # 캐러셀 영상 = 4:5
            elif option == "캐러셀":

                if abs(
                    ratio - 0.8
                ) < 0.05:

                    results.append(
                        f"✅ {uploaded_file.name}: "
                        f"이상없음 "
                        f"({w}x{h}, {r_str})"
                    )

                elif abs(
                    ratio - (16 / 9)
                ) < 0.1:

                    results.append(
                        f"❌ {uploaded_file.name}: "
                        f"가로형(16:9) 영상입니다. "
                        f"위아래 검은색 바를 추가하여 "
                        f"4:5 비율로 수정 후 전달 부탁드립니다. "
                        f"(패스트페이퍼 수정 불가, "
                        f"현재 {w}x{h})"
                    )

                else:

                    results.append(
                        f"⚠️ {uploaded_file.name}: "
                        f"4:5 비율이 아닙니다. "
                        f"그대로 진행 시 위아래가 "
                        f"잘릴 수 있습니다. "
                        f"(현재 {w}x{h}, {r_str})"
                    )

        else:

            results.append(
                f"❌ {uploaded_file.name}: "
                f"지원하지 않는 파일 형식입니다."
            )


# =========================================================
# 검수 결과 출력
# =========================================================

if results:

    result_text = "\n".join(
        results
    )

    st.code(
        result_text,
        language=None,
        wrap_lines=True
    )

    result_text_json = json.dumps(
        result_text,
        ensure_ascii=False
    )

    components.html(
        f"""
        <button
            id="copyButton"
            onclick="copyResults()"
            style="
                width:100%;
                padding:11px 15px;
                background:white;
                color:#262730;
                border:1px solid #d6d6d6;
                border-radius:8px;
                font-size:14px;
                font-weight:600;
                cursor:pointer;
            "
        >
            📋 검수 결과 복사
        </button>

        <script>

        const resultText =
            {result_text_json};

        async function copyResults() {{

            const button =
                document.getElementById(
                    "copyButton"
                );

            try {{

                await navigator.clipboard
                    .writeText(
                        resultText
                    );

            }} catch (err) {{

                const textarea =
                    document.createElement(
                        "textarea"
                    );

                textarea.value =
                    resultText;

                document.body.appendChild(
                    textarea
                );

                textarea.select();

                document.execCommand(
                    "copy"
                );

                document.body.removeChild(
                    textarea
                );
            }}

            button.innerText =
                "✅ 복사 완료";

            setTimeout(
                function() {{

                    button.innerText =
                        "📋 검수 결과 복사";

                }},
                1500
            );
        }}

        </script>
        """,
        height=55
    )


# =========================================================
# 안내사항
# =========================================================

st.divider()


st.info(
    f"""
**💡 {option} 안내사항**

- 다른 사이즈로 전달 주신 경우 위아래가 잘릴 수 있습니다.
- 소재 위아래가 잘려 업로드 되더라도 이상이 없다면 진행하셔도 무관합니다.
- **캐러셀 내 영상이 가로형(16:9)일 경우**: 위아래 검은색 바를 추가하여 4:5로 업로드 가능합니다.
- **주의**: 패스트페이퍼에서 별도 영상을 수정할 수 없습니다. 브랜드 측에서 수정하여 전달 필요합니다.
"""
)


st.warning(
    """
**📢 공통 안내사항**

1. 메타 가이드 상 해시태그는 **'#광고'를 포함한 5개까지** 가능합니다.  
   (추가적인 해시태그는 댓글로 작성이 가능합니다.)

2. 릴스 소재로 여러 미디어에 노출 시, 메타에서 "추천하지 않는 게시글"로 분류할 가능성이 있습니다.  
   이미지 에셋과 함께 **캐러셀 형태를 권장**드립니다.  
   * 이 내용은 매체 가이드가 아닌 메타 가이드인 점 참고 부탁드립니다.
"""
)


# =========================================================
# 2. 4:5 이미지 크롭
# =========================================================

st.divider()

st.header(
    "✂️ 4:5 이미지 크롭"
)

st.caption(
    "원본 이미지를 확대하지 않고 "
    "4:5 비율로 크롭합니다."
)


crop_files = st.file_uploader(
    "크롭할 이미지를 선택하세요",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ],
    accept_multiple_files=True,
    key="crop_uploader"
)


crop_position = st.radio(
    "크롭 기준",
    [
        "중앙",
        "상단",
        "하단"
    ],
    horizontal=True,
    key="crop_position"
)


if crop_files:

    st.subheader(
        "🖼️ 크롭 결과"
    )

    zip_buffer = BytesIO()

    success_count = 0

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for index, crop_file in enumerate(
            crop_files
        ):

            try:

                file_ext = os.path.splitext(
                    crop_file.name
                )[1].lower()

                crop_file.seek(0)

                img = Image.open(
                    crop_file
                )

                img = (
                    ImageOps.exif_transpose(
                        img
                    )
                )

                original_w, original_h = (
                    img.size
                )

                cropped_img = (
                    crop_image_to_4_5(
                        img,
                        crop_position
                    )
                )

                new_w, new_h = (
                    cropped_img.size
                )

                st.write(
                    f"**{crop_file.name}**"
                )

                st.caption(
                    f"원본: "
                    f"{original_w} × {original_h}"
                    f" → "
                    f"크롭: "
                    f"{new_w} × {new_h}"
                )

                st.image(
                    cropped_img,
                    caption=(
                        f"{crop_position} 기준 "
                        f"4:5 크롭"
                    ),
                    use_container_width=True
                )

                (
                    file_data,
                    download_ext,
                    mime_type
                ) = save_image_to_buffer(
                    cropped_img,
                    file_ext
                )

                original_name = (
                    os.path.splitext(
                        crop_file.name
                    )[0]
                )

                download_filename = (
                    f"{original_name}"
                    f"_4x5"
                    f"{download_ext}"
                )

                st.download_button(
                    label=(
                        f"⬇️ "
                        f"{crop_file.name} "
                        f"다운로드"
                    ),
                    data=file_data,
                    file_name=download_filename,
                    mime=mime_type,
                    key=(
                        f"crop_download_"
                        f"{index}"
                    )
                )

                zip_file.writestr(
                    download_filename,
                    file_data
                )

                success_count += 1

                st.divider()

            except Exception as e:

                st.error(
                    f"❌ {crop_file.name}: "
                    f"이미지 처리 중 오류가 발생했습니다."
                )

                st.caption(
                    str(e)
                )

    if success_count > 0:

        zip_buffer.seek(0)

        st.subheader(
            "📦 전체 다운로드"
        )

        st.download_button(
            label=(
                f"⬇️ 전체 크롭 이미지 다운로드 "
                f"({success_count}개)"
            ),
            data=zip_buffer.getvalue(),
            file_name="4x5_cropped_images.zip",
            mime="application/zip",
            use_container_width=True,
            key="download_all_crop"
        )


# =========================================================
# 3. 4:5 이미지 검은 여백
# =========================================================

st.divider()

st.header(
    "⬛ 4:5 이미지 여백 추가"
)

st.caption(
    "원본 이미지를 확대/축소하지 않고 "
    "검은색 RGB(0,0,0) 여백을 추가합니다."
)


padding_files = st.file_uploader(
    "여백을 추가할 이미지를 선택하세요",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ],
    accept_multiple_files=True,
    key="padding_uploader"
)


padding_direction = st.radio(
    "여백 방향",
    [
        "상하 여백",
        "좌우 여백"
    ],
    horizontal=True,
    key="padding_direction"
)


if padding_files:

    st.subheader(
        "🖼️ 여백 추가 결과"
    )

    padding_zip_buffer = (
        BytesIO()
    )

    padding_success_count = 0

    with zipfile.ZipFile(
        padding_zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as padding_zip_file:

        for index, padding_file in enumerate(
            padding_files
        ):

            try:

                file_ext = os.path.splitext(
                    padding_file.name
                )[1].lower()

                padding_file.seek(0)

                img = Image.open(
                    padding_file
                )

                img = (
                    ImageOps.exif_transpose(
                        img
                    )
                )

                original_w, original_h = (
                    img.size
                )

                padded_img = (
                    add_black_padding_to_4_5(
                        img,
                        padding_direction
                    )
                )

                new_w, new_h = (
                    padded_img.size
                )

                st.write(
                    f"**{padding_file.name}**"
                )

                st.caption(
                    f"원본: "
                    f"{original_w} × {original_h}"
                    f" → "
                    f"여백 추가: "
                    f"{new_w} × {new_h}"
                )

                st.image(
                    padded_img,
                    caption=(
                        f"{padding_direction} / "
                        f"4:5"
                    ),
                    use_container_width=True
                )

                (
                    file_data,
                    download_ext,
                    mime_type
                ) = save_image_to_buffer(
                    padded_img,
                    file_ext
                )

                original_name = (
                    os.path.splitext(
                        padding_file.name
                    )[0]
                )

                download_filename = (
                    f"{original_name}"
                    f"_4x5_black_padding"
                    f"{download_ext}"
                )

                st.download_button(
                    label=(
                        f"⬇️ "
                        f"{padding_file.name} "
                        f"다운로드"
                    ),
                    data=file_data,
                    file_name=download_filename,
                    mime=mime_type,
                    key=(
                        f"padding_download_"
                        f"{index}"
                    )
                )

                padding_zip_file.writestr(
                    download_filename,
                    file_data
                )

                padding_success_count += 1

                st.divider()

            except Exception as e:

                st.error(
                    f"❌ {padding_file.name}: "
                    f"여백 추가 중 오류가 발생했습니다."
                )

                st.caption(
                    str(e)
                )

    if padding_success_count > 0:

        padding_zip_buffer.seek(0)

        st.subheader(
            "📦 전체 다운로드"
        )

        st.download_button(
            label=(
                f"⬇️ 전체 여백 이미지 다운로드 "
                f"({padding_success_count}개)"
            ),
            data=padding_zip_buffer.getvalue(),
            file_name=(
                "4x5_black_padding_images.zip"
            ),
            mime="application/zip",
            use_container_width=True,
            key="download_all_padding"
        )


# =========================================================
# 4. 영상 크롭
# =========================================================

st.divider()

st.header(
    "🎬 영상 크롭"
)

st.caption(
    "원본 영상을 확대/축소하지 않고 "
    "선택한 비율의 영역만 크롭합니다."
)


video_crop_target = st.radio(
    "변환할 영상 비율",
    [
        "4:5",
        "9:16"
    ],
    horizontal=True,
    key="video_crop_target"
)


if not ffmpeg_available():

    st.error(
        "FFmpeg가 설치되어 있지 않습니다. "
        "packages.txt에 ffmpeg를 추가해주세요."
    )


video_crop_files = st.file_uploader(
    "크롭할 영상을 선택하세요",
    type=[
        "mp4",
        "mov",
        "avi"
    ],
    accept_multiple_files=True,
    key="video_crop_uploader"
)


video_crop_position = "중앙"


if video_crop_files:

    # 첫 번째 영상 기준으로
    # 필요한 크롭 방향 UI 표시
    first_file = (
        video_crop_files[0]
    )

    first_ext = os.path.splitext(
        first_file.name
    )[1].lower()

    (
        first_w,
        first_h,
        first_fps,
        first_duration
    ) = get_video_dimensions(
        first_file,
        first_ext
    )

    if (
        first_w > 0
        and first_h > 0
    ):

        first_ratio = (
            first_w / first_h
        )

        target_ratio = (
            get_target_ratio(
                video_crop_target
            )
        )

        # 원본이 목표보다 가로로 넓음
        # → 좌우 크롭
        if first_ratio > target_ratio:

            video_crop_position = (
                st.radio(
                    "크롭 기준",
                    [
                        "좌측",
                        "중앙",
                        "우측"
                    ],
                    horizontal=True,
                    key="video_crop_horizontal"
                )
            )

        # 원본이 목표보다 세로로 김
        # → 상하 크롭
        elif first_ratio < target_ratio:

            video_crop_position = (
                st.radio(
                    "크롭 기준",
                    [
                        "상단",
                        "중앙",
                        "하단"
                    ],
                    horizontal=True,
                    key="video_crop_vertical"
                )
            )

        else:

            st.info(
                f"업로드한 영상이 이미 "
                f"{video_crop_target} 비율입니다."
            )


    if st.button(
        f"🎬 {video_crop_target} 영상 크롭 시작",
        use_container_width=True,
        key="start_video_crop"
    ):

        if not ffmpeg_available():

            st.error(
                "FFmpeg가 설치되어 있지 않습니다."
            )

        else:

            video_crop_zip = (
                BytesIO()
            )

            video_crop_success = 0

            with zipfile.ZipFile(
                video_crop_zip,
                "w",
                zipfile.ZIP_DEFLATED
            ) as video_zip:

                for index, video_file in enumerate(
                    video_crop_files
                ):

                    try:

                        with st.spinner(
                            f"{video_file.name} "
                            f"{video_crop_target} 크롭 중..."
                        ):

                            (
                                result_data,
                                original_w,
                                original_h,
                                result_w,
                                result_h,
                                fps
                            ) = process_video(
                                video_file,
                                "crop",
                                video_crop_target,
                                video_crop_position
                            )

                        st.success(
                            f"✅ {video_file.name}"
                        )

                        st.caption(
                            f"원본: "
                            f"{original_w} × {original_h}"
                            f" → "
                            f"결과: "
                            f"{result_w} × {result_h}"
                            f" / "
                            f"{get_ratio_str(result_w, result_h)}"
                        )

                        original_name = (
                            os.path.splitext(
                                video_file.name
                            )[0]
                        )

                        ratio_filename = (
                            video_crop_target
                            .replace(
                                ":",
                                "x"
                            )
                        )

                        download_name = (
                            f"{original_name}"
                            f"_{ratio_filename}_crop.mp4"
                        )

                        st.download_button(
                            label=(
                                f"⬇️ "
                                f"{video_file.name} "
                                f"다운로드"
                            ),
                            data=result_data,
                            file_name=download_name,
                            mime="video/mp4",
                            key=(
                                f"video_crop_download_"
                                f"{index}"
                            )
                        )

                        video_zip.writestr(
                            download_name,
                            result_data
                        )

                        video_crop_success += 1

                        st.divider()

                    except Exception as e:

                        st.error(
                            f"❌ "
                            f"{video_file.name}: "
                            f"영상 크롭 실패"
                        )

                        st.caption(
                            str(e)
                        )

            if video_crop_success > 0:

                video_crop_zip.seek(0)

                ratio_filename = (
                    video_crop_target
                    .replace(
                        ":",
                        "x"
                    )
                )

                st.download_button(
                    label=(
                        f"⬇️ 전체 "
                        f"{video_crop_target} "
                        f"크롭 영상 다운로드 "
                        f"({video_crop_success}개)"
                    ),
                    data=video_crop_zip.getvalue(),
                    file_name=(
                        f"{ratio_filename}"
                        f"_cropped_videos.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True,
                    key="download_all_video_crop"
                )


# =========================================================
# 5. 영상 검은 여백
# =========================================================

st.divider()

st.header(
    "🎬 영상 여백 추가"
)

st.caption(
    "원본 영상을 확대/축소하지 않고 "
    "검은색 여백을 추가하여 "
    "선택한 비율로 만듭니다."
)


video_padding_target = st.radio(
    "변환할 영상 비율",
    [
        "4:5",
        "9:16"
    ],
    horizontal=True,
    key="video_padding_target"
)


video_padding_files = (
    st.file_uploader(
        "여백을 추가할 영상을 선택하세요",
        type=[
            "mp4",
            "mov",
            "avi"
        ],
        accept_multiple_files=True,
        key="video_padding_uploader"
    )
)


if video_padding_files:

    st.info(
        f"선택한 목표 비율은 "
        f"**{video_padding_target}**입니다.\n\n"
        "영상 비율을 자동으로 계산하여 "
        "필요한 방향에 검은색 여백을 추가합니다.\n\n"
        "• 원본이 목표보다 가로로 넓음 → 상하 여백\n\n"
        "• 원본이 목표보다 세로로 김 → 좌우 여백"
    )

    if st.button(
        f"🎬 {video_padding_target} 영상 여백 추가 시작",
        use_container_width=True,
        key="start_video_padding"
    ):

        if not ffmpeg_available():

            st.error(
                "FFmpeg가 설치되어 있지 않습니다."
            )

        else:

            video_padding_zip = (
                BytesIO()
            )

            video_padding_success = 0

            with zipfile.ZipFile(
                video_padding_zip,
                "w",
                zipfile.ZIP_DEFLATED
            ) as padding_video_zip:

                for index, video_file in enumerate(
                    video_padding_files
                ):

                    try:

                        with st.spinner(
                            f"{video_file.name} "
                            f"{video_padding_target} "
                            f"여백 추가 중..."
                        ):

                            (
                                result_data,
                                original_w,
                                original_h,
                                result_w,
                                result_h,
                                fps
                            ) = process_video(
                                video_file,
                                "padding",
                                video_padding_target
                            )

                        st.success(
                            f"✅ {video_file.name}"
                        )

                        st.caption(
                            f"원본: "
                            f"{original_w} × {original_h}"
                            f" → "
                            f"결과: "
                            f"{result_w} × {result_h}"
                            f" / "
                            f"{get_ratio_str(result_w, result_h)}"
                        )

                        original_name = (
                            os.path.splitext(
                                video_file.name
                            )[0]
                        )

                        ratio_filename = (
                            video_padding_target
                            .replace(
                                ":",
                                "x"
                            )
                        )

                        download_name = (
                            f"{original_name}"
                            f"_{ratio_filename}"
                            f"_black_padding.mp4"
                        )

                        st.download_button(
                            label=(
                                f"⬇️ "
                                f"{video_file.name} "
                                f"다운로드"
                            ),
                            data=result_data,
                            file_name=download_name,
                            mime="video/mp4",
                            key=(
                                f"video_padding_download_"
                                f"{index}"
                            )
                        )

                        padding_video_zip.writestr(
                            download_name,
                            result_data
                        )

                        video_padding_success += 1

                        st.divider()

                    except Exception as e:

                        st.error(
                            f"❌ "
                            f"{video_file.name}: "
                            f"영상 여백 추가 실패"
                        )

                        st.caption(
                            str(e)
                        )

            if video_padding_success > 0:

                video_padding_zip.seek(0)

                ratio_filename = (
                    video_padding_target
                    .replace(
                        ":",
                        "x"
                    )
                )

                st.download_button(
                    label=(
                        f"⬇️ 전체 "
                        f"{video_padding_target} "
                        f"여백 영상 다운로드 "
                        f"({video_padding_success}개)"
                    ),
                    data=(
                        video_padding_zip.getvalue()
                    ),
                    file_name=(
                        f"{ratio_filename}"
                        f"_black_padding_videos.zip"
                    ),
                    mime="application/zip",
                    use_container_width=True,
                    key="download_all_video_padding"
                )
