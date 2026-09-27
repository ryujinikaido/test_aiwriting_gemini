"""各ツール画面で共通して使う UI 部品をまとめたモジュール。"""

from __future__ import annotations

from typing import Iterator

import streamlit as st

from core.config import DEFAULT_MODEL, get_api_key
from core.gemini import stream_text
from core.history import add_history

# ---------------------------------------------------------------- 共通の選択肢

TONES = [
    "丁寧・ですます調",
    "カジュアル・親しみやすい",
    "ビジネス・かっちり",
    "専門的・解説寄り",
    "熱量高め・セールス寄り",
    "淡々と事実ベース",
]

LENGTH_HINTS = {
    "短め": "全体で 300〜500 文字程度",
    "普通": "全体で 800〜1200 文字程度",
    "長め": "全体で 2000〜3000 文字程度",
    "かなり長め": "全体で 4000 文字以上",
}


def tool_header(icon: str, title: str, description: str) -> None:
    st.header(f"{icon} {title}")
    st.caption(description)


def current_model() -> str:
    return st.session_state.get("model", DEFAULT_MODEL)


def current_temperature() -> float:
    return float(st.session_state.get("temperature", 0.7))


# ---------------------------------------------------------------- 入力部品


def long_text_input(
    label: str,
    key: str,
    height: int = 260,
    placeholder: str = "",
) -> str:
    """長文入力欄。テキストファイル（.txt / .md）の読み込みにも対応する。"""
    uploaded = st.file_uploader(
        "テキストファイルから読み込む（任意・.txt / .md）",
        type=["txt", "md"],
        key=f"up_{key}",
    )
    default = ""
    if uploaded is not None:
        raw = uploaded.getvalue()
        try:
            default = raw.decode("utf-8")
        except UnicodeDecodeError:
            default = raw.decode("cp932", errors="ignore")
        st.caption(f"📄 {uploaded.name} を読み込みました（{len(default)} 文字）")

    # ファイルを読み込んだときは、その内容を初期値にした別ウィジェットに差し替える
    widget_key = f"ta_{key}_{uploaded.name}" if uploaded is not None else f"ta_{key}"
    return st.text_area(
        label,
        value=default,
        height=height,
        key=widget_key,
        placeholder=placeholder,
    )


# ---------------------------------------------------------------- 生成まわり


def _safe_stream(gen: Iterator[str], errors: list[Exception]) -> Iterator[str]:
    """ストリーム中の例外を拾って、後でまとめて表示できるようにする。"""
    try:
        for chunk in gen:
            yield chunk
    except Exception as exc:  # noqa: BLE001 - 画面に文言で見せるため
        errors.append(exc)


def safe_stream(gen: Iterator[str], errors: list[Exception]) -> Iterator[str]:
    """_safe_stream の公開版。チャット画面など、外から使いたいとき用。"""
    return _safe_stream(gen, errors)


def generate(
    tool_key: str,
    *,
    prompt: str,
    system_instruction: str = "",
    history_title: str = "",
    history_summary: str = "",
    temperature: float | None = None,
    model: str | None = None,
    save_history: bool = True,
) -> str | None:
    """プロンプトを Gemini に投げ、結果をストリーミング表示して返す。"""
    api_key = get_api_key()
    if not api_key:
        st.error(
            "APIキーが設定されていません。サイドバーの「APIキーを入力」に貼り付けるか、"
            "`.env` に `GEMINI_API_KEY=...` を書いてください。"
        )
        return None

    errors: list[Exception] = []
    st.subheader("生成結果")
    with st.spinner("生成中…"):
        stream = stream_text(
            api_key=api_key,
            model=model or current_model(),
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=current_temperature() if temperature is None else temperature,
        )
        text = st.write_stream(_safe_stream(stream, errors))

    if errors:
        st.error(f"生成に失敗しました: {errors[0]}")
        st.caption("APIキー・モデル名・ネットワークを確認してもう一度お試しください。")
        return None

    text = text if isinstance(text, str) else "".join(text)
    if not text.strip():
        st.warning("空の応答が返ってきました。入力を変えてもう一度お試しください。")
        return None

    st.session_state[f"result_{tool_key}"] = text
    st.session_state["_just_generated"] = tool_key

    if save_history:
        add_history(
            tool=tool_key,
            title=history_title or prompt[:80],
            prompt_summary=history_summary or prompt,
            output=text,
        )
    return text


def result_area(tool_key: str, filename: str = "output.md") -> None:
    """保存済みの生成結果と、コピー／ダウンロードのボタンを表示する。"""
    text = st.session_state.get(f"result_{tool_key}")
    if not text:
        return

    just_generated = st.session_state.pop("_just_generated", None) == tool_key
    if not just_generated:
        st.subheader("前回の生成結果")
        st.markdown(text)

    st.caption(f"文字数: {len(text)} 文字")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ ダウンロード",
            data=text,
            file_name=filename,
            mime="text/markdown",
            key=f"dl_{tool_key}",
            use_container_width=True,
        )
    with col2:
        if st.button("🗑️ 結果をクリア", key=f"clr_{tool_key}", use_container_width=True):
            st.session_state.pop(f"result_{tool_key}", None)
            st.rerun()

    with st.expander("📋 コピー用（右上のアイコンでコピーできます）"):
        st.code(text, language="markdown")
