"""自由に相談できるチャット。書きかけの文章の壁打ちに使う。"""

from __future__ import annotations

import streamlit as st

from core.config import get_api_key
from core.gemini import stream_chat
from core.history import add_history
from core import ui

TOOL_KEY = "chat"
ICON = "💬"
LABEL = "相談チャット"
DESCRIPTION = "決まったフォームに収まらない相談を、会話しながら詰めていきます。"

PERSONAS = {
    "編集者（書き手の壁打ち相手）": (
        "あなたはベテランの編集者です。書き手の意図を引き出し、"
        "構成の甘さや読者視点の抜けを具体的に指摘します。"
        "曖昧な相談には、まず短い質問を1〜2個返して方向を定めてください。"
    ),
    "コピーライター": (
        "あなたは反応率にこだわるコピーライターです。"
        "案を出すときは必ず複数パターンを示し、それぞれの狙いを一言添えます。"
    ),
    "ビジネス文書の相談相手": (
        "あなたはビジネス文書に詳しいコンサルタントです。"
        "敬語・言い回し・伝える順番について、根拠を添えて具体的に助言します。"
    ),
    "何でも相談（万能アシスタント）": (
        "あなたは有能な日本語アシスタントです。"
        "結論から述べ、必要に応じて箇条書きで簡潔に答えます。"
    ),
}


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    col1, col2 = st.columns([3, 1])
    with col1:
        persona = st.selectbox("話し相手", list(PERSONAS), key="chat_persona")
    with col2:
        st.write("")
        if st.button("🧹 会話をリセット", use_container_width=True):
            st.session_state["chat_messages"] = []
            st.rerun()

    messages: list[dict[str, str]] = st.session_state.setdefault("chat_messages", [])

    for msg in messages:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])

    prompt = st.chat_input("相談したいことを入力…")
    if not prompt:
        if not messages:
            st.info("例:「この記事の構成、読者が途中で離脱しそうな箇所はどこ？」")
        return

    api_key = get_api_key()
    if not api_key:
        st.error("APIキーが設定されていません。サイドバーから設定してください。")
        return

    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        errors: list[Exception] = []
        stream = stream_chat(
            api_key=api_key,
            model=ui.current_model(),
            messages=messages,
            system_instruction=PERSONAS[persona],
            temperature=ui.current_temperature(),
        )
        reply = st.write_stream(ui.safe_stream(stream, errors))

    if errors:
        st.error(f"生成に失敗しました: {errors[0]}")
        messages.pop()
        return

    reply = reply if isinstance(reply, str) else "".join(reply)
    messages.append({"role": "model", "content": reply})
    add_history(
        tool=TOOL_KEY,
        title=prompt[:60],
        prompt_summary=f"[{persona}] {prompt}",
        output=reply,
    )
