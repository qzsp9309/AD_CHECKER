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
