"""AI ライティングツール — Streamlit アプリのエントリーポイント。

起動方法:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from core.config import (
    APP_ICON,
    APP_TITLE,
    available_models,
    get_api_key,
    pick_default,
)
from tools import (
    blog,
    chat,
    history_view,
    ideas,
    mail,
    proofread,
    rewrite,
    sns,
    summarize,
    translate,
)

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

# 画面に並べるツール（サイドバーの並び順もこの順番）
TOOLS = [blog, mail, summarize, rewrite, proofread, sns, ideas, translate, chat]
TOOL_LABELS = {t.TOOL_KEY: f"{t.ICON} {t.LABEL}" for t in TOOLS}
PAGES = {f"{t.ICON} {t.LABEL}": t for t in TOOLS}
HISTORY_PAGE = f"{history_view.ICON} {history_view.LABEL}"


def sidebar() -> str:
    with st.sidebar:
        st.title(f"{APP_ICON} {APP_TITLE}")
        page = st.radio("ツールを選ぶ", list(PAGES) + [HISTORY_PAGE], label_visibility="collapsed")

        st.divider()
        st.subheader("⚙️ 生成の設定")
        _model_selector()
        st.session_state["temperature"] = st.slider(
            "創造性（temperature）",
            0.0,
            1.5,
            0.7,
            0.1,
            help="低いほど堅実で安定、高いほど自由な発想になります。",
        )

        st.divider()
        _api_key_section()
    return page


def _model_selector() -> None:
    """使えるモデルをAPIから引いて選ばせる。提供終了したモデルは自動的に消える。"""
    models = available_models(get_api_key())
    ids = list(models.values())

    # 前回選んだモデルが使えなくなっていたら、既定に戻す
    current = st.session_state.get("model")
    selected_id = current if current in ids else pick_default(ids)

    label = st.selectbox(
        "モデル",
        list(models),
        index=ids.index(selected_id),
        help="速さ重視なら Flash、じっくり書かせたいなら Pro。",
    )
    st.session_state["model"] = models[label]
    st.caption(f"`{models[label]}`")


def _api_key_section() -> None:
    st.subheader("🔑 APIキー")
    if get_api_key():
        st.success("設定済み", icon="✅")
        if st.session_state.get("manual_api_key"):
            if st.button("キーを消す", use_container_width=True):
                st.session_state.pop("manual_api_key", None)
                st.rerun()
        return

    st.warning("未設定です", icon="⚠️")
    key = st.text_input(
        "APIキーを入力",
        type="password",
        placeholder="AIza...",
        help="この入力はブラウザのセッション内だけに保持され、ファイルには保存されません。",
    )
    if key:
        st.session_state["manual_api_key"] = key.strip()
        st.rerun()
    st.caption(
        "[Google AI Studio](https://aistudio.google.com/apikey) で無料のキーを取得できます。"
    )


def welcome() -> None:
    """APIキーが無いときに出す、最初の案内。"""
    st.info("まずは APIキーを設定してください。", icon="🔑")
    st.markdown(
        """
### セットアップ（1分）

1. [Google AI Studio](https://aistudio.google.com/apikey) でAPIキーを作成する
2. このフォルダの `.env.example` を `.env` にリネームする
3. `GEMINI_API_KEY=取得したキー` を書いて保存する
4. アプリを再起動する（サイドバーに直接貼り付けてもOK）
        """
    )


def main() -> None:
    page = sidebar()

    if not get_api_key():
        st.title(f"{APP_ICON} {APP_TITLE}")
        welcome()
        st.divider()

    if page == HISTORY_PAGE:
        history_view.render(TOOL_LABELS)
    else:
        PAGES[page].render()


if __name__ == "__main__":
    main()
