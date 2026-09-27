"""ブログ記事の構成案・本文をまとめて書いてもらうツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "blog"
ICON = "✍️"
LABEL = "ブログ記事"
DESCRIPTION = "テーマとターゲットを入れるだけで、見出し構成つきの記事本文を書き上げます。"

SYSTEM = (
    "あなたは日本語のプロのWebライター兼編集者です。"
    "読者が最後まで読み進められる、具体的で読みやすい記事を書きます。"
    "抽象的な一般論や水増し表現は避け、具体例・数字・手順を入れてください。"
    "出力は Markdown 形式（見出しは ## / ###）で、記事本文だけを返します。"
    "「承知しました」などの前置きやメタ発言は書かないでください。"
)

PURPOSES = [
    "読者の悩みを解決する（お役立ち記事）",
    "商品・サービスを紹介する（レビュー）",
    "自分の体験を共有する（体験談）",
    "ニュース・トレンドを解説する",
    "手順をわかりやすく説明する（HowTo）",
]


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    with st.form("blog_form"):
        topic = st.text_input(
            "記事のテーマ・タイトル案 *",
            placeholder="例: 初心者がPythonを3ヶ月で習得する勉強法",
        )
        col1, col2 = st.columns(2)
        with col1:
            target = st.text_input(
                "想定読者", placeholder="例: 未経験からエンジニア転職を目指す20代"
            )
            tone = st.selectbox("文体・トーン", ui.TONES, index=0)
            length = st.select_slider(
                "記事のボリューム", options=list(ui.LENGTH_HINTS), value="普通"
            )
        with col2:
            keywords = st.text_input(
                "入れたいキーワード（カンマ区切り）",
                placeholder="例: Python, 独学, ロードマップ",
            )
            purpose = st.selectbox("記事の目的", PURPOSES)
            outline_only = st.checkbox("まず構成案（見出しだけ）が欲しい", value=False)

        outline = st.text_area(
            "使いたい見出し構成があれば貼り付け（任意）",
            height=100,
            placeholder="## はじめに\n## 勉強法3ステップ\n## まとめ",
        )
        notes = st.text_area(
            "そのほかの指示（任意）",
            height=80,
            placeholder="例: 自分の失敗談を交えて。最後にメルマガ登録を促して。",
        )
        submitted = st.form_submit_button("🚀 記事を書いてもらう", type="primary")

    if submitted:
        if not topic.strip():
            st.warning("記事のテーマを入力してください。")
        else:
            prompt = _build_prompt(
                topic, target, tone, length, keywords, purpose, outline, notes, outline_only
            )
            label = "[構成案] " if outline_only else ""
            ui.generate(
                TOOL_KEY,
                prompt=prompt,
                system_instruction=SYSTEM,
                history_title=f"{label}{topic}",
                history_summary=f"読者: {target} / トーン: {tone} / 目的: {purpose}",
            )

    ui.result_area(TOOL_KEY, filename="blog.md")


def _build_prompt(
    topic: str,
    target: str,
    tone: str,
    length: str,
    keywords: str,
    purpose: str,
    outline: str,
    notes: str,
    outline_only: bool,
) -> str:
    blocks = [
        "次の条件でブログ記事を書いてください。",
        f"# テーマ\n{topic}",
        f"# 想定読者\n{target or '特に指定なし（一般的なWeb読者）'}",
        f"# 記事の目的\n{purpose}",
        f"# 文体・トーン\n{tone}",
        f"# 分量の目安\n{ui.LENGTH_HINTS[length]}",
    ]
    if keywords.strip():
        blocks.append(f"# 自然に含めるキーワード\n{keywords}")
    if outline.strip():
        blocks.append(f"# 指定の見出し構成（これに沿って書く）\n{outline}")
    if notes.strip():
        blocks.append(f"# 追加の指示\n{notes}")

    if outline_only:
        blocks.append(
            "# 出力形式\n"
            "本文は書かず、記事の構成案だけを出してください。\n"
            "1. タイトル案を3つ\n"
            "2. リード文の要旨（2〜3行）\n"
            "3. 見出し構成（## と ### の階層。各見出しに何を書くかを1行メモ付き）\n"
            "4. まとめで伝えること"
        )
    else:
        blocks.append(
            "# 出力形式\n"
            "1. 記事タイトル（# 見出し）\n"
            "2. リード文（読者の悩みに共感し、読むメリットを示す。2〜4行）\n"
            "3. 本文（## の見出しで区切る。必要に応じて ### や箇条書き・表を使う）\n"
            "4. まとめ（要点の振り返りと、読者への次の一歩の提案）"
        )
    return "\n\n".join(blocks)
