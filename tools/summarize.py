"""長文を目的に合わせて要約するツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "summarize"
ICON = "📝"
LABEL = "要約"
DESCRIPTION = "議事録・記事・レポートを、目的に合わせた形にまとめ直します。"

SYSTEM = (
    "あなたは要約の専門家です。原文にない情報を足さず、重要度の高い順に整理します。"
    "固有名詞・数字・日付は原文どおり正確に残してください。"
    "原文から読み取れない内容を補う場合は、必ず「（推測）」と明示します。"
)

FORMATS = {
    "3行まとめ": "3行（各行40〜60文字）で要点だけを述べる。",
    "箇条書き（5〜7点）": "箇条書きで5〜7点。各項目は1行で完結させる。",
    "見出し付きサマリー": "## 見出しで話題ごとに区切り、各節を2〜4行でまとめる。",
    "議事録スタイル": "## 決定事項 / ## 議論の要点 / ## ToDo（担当者と期限つき） の3節に整理する。",
    "要点＋次のアクション": "## 要点 を箇条書きにしたあと、## 次にすべきこと を具体的な行動で挙げる。",
    "やさしい日本語で説明": "専門用語を噛み砕き、比喩を使って中学生でも理解できる説明にする。",
}

RATIOS = ["ぎゅっと（1割程度）", "標準（2〜3割）", "ゆるめ（半分程度）"]


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    source = ui.long_text_input(
        "要約したい文章 *",
        key="sum_src",
        height=300,
        placeholder="ここに記事・議事録・メールなどを貼り付けてください。",
    )
    if source.strip():
        st.caption(f"入力: {len(source)} 文字")

    with st.form("sum_form"):
        col1, col2 = st.columns(2)
        with col1:
            fmt = st.selectbox("まとめ方", list(FORMATS))
            ratio = st.select_slider("圧縮の強さ", options=RATIOS, value=RATIOS[1])
        with col2:
            focus = st.text_input(
                "特に知りたい観点（任意）", placeholder="例: 費用と納期に関する部分だけ"
            )
            keywords = st.checkbox("キーワードを5つ抽出する", value=True)
        submitted = st.form_submit_button("📝 要約する", type="primary")

    if submitted:
        if not source.strip():
            st.warning("要約したい文章を入力してください。")
        else:
            blocks = [
                "次の文章を要約してください。",
                f"# 原文\n```\n{source}\n```",
                f"# まとめ方\n{FORMATS[fmt]}",
                f"# 分量\n原文の{ratio}",
            ]
            if focus.strip():
                blocks.append(f"# 特に重視する観点\n{focus}")
            if keywords:
                blocks.append(
                    "# 追加\n最後に「## キーワード」として重要語を5つ、カンマ区切りで挙げる。"
                )
            ui.generate(
                TOOL_KEY,
                prompt="\n\n".join(blocks),
                system_instruction=SYSTEM,
                history_title=f"要約（{fmt}）: {source[:40]}",
                history_summary=f"形式: {fmt} / 圧縮: {ratio} / 観点: {focus or 'なし'}",
                temperature=min(ui.current_temperature(), 0.4),
            )

    ui.result_area(TOOL_KEY, filename="summary.md")
