                "상하 검은 여백"
            )

        elif (
            padding_current_ratio
            < padding_target_ratio
        ):
            padding_direction_text = (
                "좌우 검은 여백"
            )

        else:
            padding_direction_text = (
                "여백 추가 불필요"
            )

        st.info(
            f"목표 비율: **{video_padding_target}**  \n"
            f"원본: **{padding_w} × {padding_h}**  \n"
            f"적용 방식: **{padding_direction_text}**"
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

        elif padding_w <= 0 or padding_h <= 0:
            st.error(
                "영상 정보를 읽을 수 없습니다."
            )

        else:
            try:
                with st.spinner(
                    f"{video_padding_file.name} "
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
                        video_padding_file,
                        "padding",
                        video_padding_target
                    )

                ratio_filename = (
                    video_padding_target.replace(":", "x")
                )

                original_name = os.path.splitext(
                    video_padding_file.name
                )[0]

                st.session_state[
                    "video_padding_result"
                ] = {
                    "data": result_data,
                    "file_name": (
                        f"{original_name}_"
                        f"{ratio_filename}_"
                        f"black_padding.mp4"
                    ),
                    "source_name": video_padding_file.name,
                    "original_w": original_w,
                    "original_h": original_h,
                    "result_w": result_w,
                    "result_h": result_h,
                    "target": video_padding_target
                }

            except Exception as e:
                st.session_state.pop(
                    "video_padding_result",
                    None
                )
                st.error(
                    f"❌ {video_padding_file.name}: "
                    f"영상 여백 추가 실패"
                )
                st.caption(str(e))

    padding_result = st.session_state.get(
        "video_padding_result"
    )

    if (
        padding_result
        and padding_result["source_name"]
        == video_padding_file.name
        and padding_result["target"]
        == video_padding_target
    ):
        st.success("✅ 영상 여백 추가 완료")

        st.caption(
            f"원본: "
            f"{padding_result['original_w']} × "
            f"{padding_result['original_h']}"
            f" → 결과: "
            f"{padding_result['result_w']} × "
            f"{padding_result['result_h']}"
            f" / "
            f"{get_ratio_str(padding_result['result_w'], padding_result['result_h'])}"
        )

        st.download_button(
            label="⬇️ 여백 영상 다운로드",
            data=padding_result["data"],
            file_name=padding_result["file_name"],
            mime="video/mp4",
            use_container_width=True,
            key="video_padding_download"
        )

