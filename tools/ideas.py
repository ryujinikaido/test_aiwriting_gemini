"""タイトル・キャッチコピーなどのアイデア出しツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "ideas"
ICON = "💡"
LABEL = "タイトル・コピー案"
DESCRIPTION = "ブログタイトル、メール件名、キャッチコピーを、切り口を変えて量産します。"

SYSTEM = (
    "あなたは反応率にこだわるコピーライターです。"
    "ありきたりな言い回しを避け、具体的な数字・対象・ベネフィットを入れて差別化します。"
    "誇大表現や事実に反する断定はしません。案だけを出し、言い訳や前置きは書きません。"
)

KINDS = {
    "ブログ記事のタイトル": "検索されやすく、クリックしたくなる記事タイトル。32文字前後。",
    "メールの件名": "開封率を意識した件名。20文字前後で、内容が一目でわかること。",
    "商品・サービスのキャッチコピー": "短く記憶に残るコピー。20文字以内を中心に。",
    "SNS投稿の書き出し（フック）": "スクロールを止める1行目。長くても40文字。",
    "YouTube動画のタイトル": "クリック率を意識しつつ内容と齟齬のないタイトル。40文字前後。",
    "サービス名・ネーミング案": "読みやすく覚えやすい名前。由来を一言添える。",
}

ANGLES = [
    "ベネフィット訴求（得られる結果）",
    "数字・具体性",
    "問いかけ・疑問形",
    "常識への逆張り",
    "失敗回避・不安の解消",
    "初心者向けのやさしさ",
    "権威・実績",
    "ストーリー・体験談",
]


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    with st.form("ideas_form"):
        subject = st.text_area(
            "テーマ・題材 *",
            height=100,
            placeholder="例: 個人開発のAIライティングツール。Python初心者でも3時間で作れる。",
        )
        col1, col2 = st.columns(2)
        with col1:
            kind = st.selectbox("何の案が欲しい？", list(KINDS))
            n = st.slider("案の数", 5, 30, 15, step=5)
        with col2:
            target = st.text_input("ターゲット", placeholder="例: 副業でAIを使いたい会社員")
            keywords = st.text_input(
                "必ず入れたい語（任意）", placeholder="例: Streamlit, 生成AI"
            )
        angles = st.multiselect("使ってほしい切り口", ANGLES, default=ANGLES[:4])
        submitted = st.form_submit_button("💡 案を出してもらう", type="primary")

    if submitted:
        if not subject.strip():
            st.warning("テーマ・題材を入力してください。")
        else:
            blocks = [
                f"「{kind}」の案を{n}個出してください。",
                f"# テーマ・題材\n{subject}",
                f"# 案の性質\n{KINDS[kind]}",
                f"# ターゲット\n{target or '特に指定なし'}",
            ]
            if keywords.strip():
                blocks.append(f"# 必ず入れたい語\n{keywords}")
            if angles:
                blocks.append("# 使う切り口\n" + "\n".join(f"- {a}" for a in angles))
            blocks.append(
                "# 出力形式\n"
                "| # | 案 | 切り口 | ひとこと狙い |\n|---|---|---|---|\n"
                "の表で全案を並べる。そのあと ## おすすめ3案 として、"
                "特に反応が良さそうな3つを理由つきで挙げる。"
            )
            ui.generate(
                TOOL_KEY,
                prompt="\n\n".join(blocks),
                system_instruction=SYSTEM,
                history_title=f"{kind}: {subject[:40]}",
                history_summary=f"種類: {kind} / {n}案 / ターゲット: {target or '指定なし'}",
                temperature=max(ui.current_temperature(), 1.0),
            )

    ui.result_area(TOOL_KEY, filename="ideas.md")
