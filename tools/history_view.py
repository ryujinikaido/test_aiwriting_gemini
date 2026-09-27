"""生成履歴の一覧画面。"""

from __future__ import annotations

import json

import streamlit as st

from core.history import clear_history, delete_history, load_history

TOOL_KEY = "history"
ICON = "📚"
LABEL = "履歴"
DESCRIPTION = "これまでの生成結果を見返して、コピー・削除ができます。"


def render(tool_labels: dict[str, str]) -> None:
    st.header(f"{ICON} {LABEL}")
    st.caption(DESCRIPTION)

    items = load_history()
    if not items:
        st.info("まだ履歴がありません。どれかのツールで文章を作ると、ここに残ります。")
        return

    col1, col2 = st.columns([2, 3])
    with col1:
        used = sorted({i.get("tool", "") for i in items})
        choices = ["すべて"] + [tool_labels.get(t, t) for t in used]
        picked = st.selectbox("ツールで絞り込む", choices)
    with col2:
        query = st.text_input("キーワード検索", placeholder="タイトル・本文から探す")

    label_to_key = {tool_labels.get(t, t): t for t in used}
    if picked != "すべて":
        key = label_to_key[picked]
        items = [i for i in items if i.get("tool") == key]
    if query.strip():
        q = query.strip().lower()
        items = [
            i
            for i in items
            if q in i.get("title", "").lower()
            or q in i.get("output", "").lower()
            or q in i.get("prompt_summary", "").lower()
        ]

    st.caption(f"{len(items)} 件")
    for item in items[:100]:
        tool_label = tool_labels.get(item.get("tool", ""), item.get("tool", "?"))
        with st.expander(f"{item['created_at']}　[{tool_label}]　{item['title']}"):
            st.markdown(item["output"])
            st.caption("▼ このときの指示")
            st.code(item.get("prompt_summary", ""), language="text")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ ダウンロード",
                    data=item["output"],
                    file_name=f"{item.get('tool', 'output')}_{item['id']}.md",
                    mime="text/markdown",
                    key=f"hdl_{item['id']}",
                    use_container_width=True,
                )
            with c2:
                if st.button("🗑️ この履歴を削除", key=f"hdel_{item['id']}", use_container_width=True):
                    delete_history(item["id"])
                    st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ 全履歴をJSONで書き出す",
            data=json.dumps(load_history(), ensure_ascii=False, indent=2),
            file_name="history.json",
            mime="application/json",
            use_container_width=True,
        )
    with c2:
        if st.session_state.get("confirm_clear"):
            if st.button("⚠️ 本当に全部消す（取り消せません）", type="primary", use_container_width=True):
                clear_history()
                st.session_state["confirm_clear"] = False
                st.rerun()
        elif st.button("🗑️ 履歴を全消去", use_container_width=True):
            st.session_state["confirm_clear"] = True
            st.rerun()
