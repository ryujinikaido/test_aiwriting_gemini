"""校正・推敲ツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "proofread"
ICON = "🔍"
LABEL = "校正・推敲"
DESCRIPTION = "誤字脱字や読みにくい箇所を指摘し、修正版まで出します。"

SYSTEM = (
    "あなたは日本語の校正者です。"
    "誤字脱字・変換ミス・助詞の誤り・係り受けの乱れ・表記ゆれ・二重敬語・冗長表現を見つけます。"
    "書き手の意図や文体は尊重し、好みの問題だけで書き換えないでください。"
    "指摘には「なぜ直すのか」が伝わる短い理由を添えます。"
    "問題がない場合は無理に指摘を作らず、その旨を述べてください。"
)

CHECKS = {
    "誤字脱字・変換ミス": "誤字、脱字、同音異義語の変換ミス",
    "文法・係り受け": "助詞の誤用、主述のねじれ、係り受けの曖昧さ",
    "表記ゆれ": "送り仮名・カタカナ語・数字表記などの不統一",
    "敬語の使い方": "二重敬語、尊敬語と謙譲語の取り違え",
    "冗長表現": "同じ意味の重複、まわりくどい言い回し",
    "読みやすさ": "一文が長すぎる箇所、改行や段落の切り方",
    "事実の矛盾": "文章内で数字や主張が食い違っている箇所",
}

STRICTNESS = {
    "軽め（明らかなミスだけ）": "明らかな誤りだけを指摘し、細かい好みには踏み込まない。",
    "標準": "誤りに加え、読みにくさの改善提案も適度に行う。",
    "厳しめ（表現まで踏み込む）": "細かな表現・リズム・語彙選択まで踏み込んで指摘する。",
}


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    source = ui.long_text_input(
        "校正したい文章 *",
        key="pr_src",
        height=250,
        placeholder="ここに文章を貼り付けてください。",
    )

    with st.form("pr_form"):
        checks = st.multiselect(
            "チェックする観点", list(CHECKS), default=list(CHECKS)[:5]
        )
        col1, col2 = st.columns(2)
        with col1:
            strictness = st.selectbox("指摘の厳しさ", list(STRICTNESS), index=1)
        with col2:
            with_fixed = st.checkbox("修正版の全文も出す", value=True)
        submitted = st.form_submit_button("🔍 校正する", type="primary")

    if submitted:
        if not source.strip():
            st.warning("校正したい文章を入力してください。")
        elif not checks:
            st.warning("チェックする観点を1つ以上選んでください。")
        else:
            check_lines = "\n".join(f"- {c}: {CHECKS[c]}" for c in checks)
            fmt = [
                "## 指摘一覧",
                "| # | 該当箇所 | 指摘内容 | 修正案 |",
                "|---|---|---|---|",
                "の形式の表で、重要な順に並べる。該当箇所は原文から短く引用する。",
            ]
            if with_fixed:
                fmt.append("そのあと ## 修正版 として、指摘を反映した全文を出す。")
            fmt.append("最後に ## 総評 として、良い点と全体の改善方針を3行以内で述べる。")

            blocks = [
                "次の文章を校正してください。",
                f"# 対象の文章\n```\n{source}\n```",
                f"# チェック観点\n{check_lines}",
                f"# 指摘の厳しさ\n{STRICTNESS[strictness]}",
                "# 出力形式\n" + "\n".join(fmt),
            ]
            ui.generate(
                TOOL_KEY,
                prompt="\n\n".join(blocks),
                system_instruction=SYSTEM,
                history_title=f"校正: {source[:40]}",
                history_summary=f"観点: {', '.join(checks)} / {strictness}",
                temperature=min(ui.current_temperature(), 0.3),
            )

    ui.result_area(TOOL_KEY, filename="proofread.md")
