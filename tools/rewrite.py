"""文章のリライト・文体変換ツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "rewrite"
ICON = "🔁"
LABEL = "リライト・文体変換"
DESCRIPTION = "意味はそのままに、読み手や場面に合わせて文章を書き換えます。"

SYSTEM = (
    "あなたは日本語のリライトのプロです。"
    "元の文章の意味・事実・ニュアンスを変えず、情報を勝手に足しません。"
    "指示された方向性に沿って語彙・語順・構成を組み替えてください。"
    "書き換えた文章のみを出力し、前置きや解説は書かないでください。"
)

DIRECTIONS = {
    "丁寧・敬語にする": "ビジネスで通用する丁寧語・敬語に整える。二重敬語は避ける。",
    "カジュアルにする": "話し言葉寄りの、肩の力が抜けた親しみやすい文体にする。",
    "簡潔にする（短く）": "意味を保ったまま冗長表現を削り、短く引き締める。",
    "詳しくする（膨らませる）": "具体例や補足説明を足し、読み手が理解しやすい厚みを出す。",
    "PREP法で構成し直す": "結論→理由→具体例→結論 の順に組み替える。",
    "やさしい日本語にする": "専門用語を避け、小学校高学年でも読める言葉づかいにする。",
    "セールスライティングにする": "読み手のベネフィットを前面に出し、行動を促す締めにする。",
    "SEOを意識して整える": "見出しを整理し、指定キーワードを不自然にならない範囲で盛り込む。",
}


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    source = ui.long_text_input(
        "書き換えたい文章 *",
        key="rw_src",
        height=250,
        placeholder="ここに元の文章を貼り付けてください。",
    )

    with st.form("rw_form"):
        col1, col2 = st.columns(2)
        with col1:
            direction = st.selectbox("書き換えの方向性", list(DIRECTIONS))
            ratio = st.select_slider(
                "分量",
                options=["半分くらいに", "そのまま", "1.5倍くらいに", "2倍くらいに"],
                value="そのまま",
            )
        with col2:
            audience = st.text_input(
                "読み手（任意）", placeholder="例: 取引先の役員 / ブログ読者"
            )
            keywords = st.text_input(
                "入れたいキーワード（任意・カンマ区切り）", placeholder="例: 生成AI, 業務効率化"
            )
        show_diff = st.checkbox("どこを変えたか、変更点の一覧も出す", value=False)
        submitted = st.form_submit_button("🔁 書き換える", type="primary")

    if submitted:
        if not source.strip():
            st.warning("書き換えたい文章を入力してください。")
        else:
            blocks = [
                "次の文章を指示に沿って書き換えてください。",
                f"# 元の文章\n```\n{source}\n```",
                f"# 書き換えの方向性\n{DIRECTIONS[direction]}",
                f"# 分量\n{ratio}",
            ]
            if audience.strip():
                blocks.append(f"# 読み手\n{audience}")
            if keywords.strip():
                blocks.append(f"# 自然に含めるキーワード\n{keywords}")
            if show_diff:
                blocks.append(
                    "# 出力形式\n"
                    "## 書き換え後 に本文を書き、そのあと ## 主な変更点 として"
                    "「どこを・なぜ変えたか」を箇条書きで5点以内にまとめる。"
                )
            else:
                blocks.append("# 出力形式\n書き換え後の文章だけを出す。")
            ui.generate(
                TOOL_KEY,
                prompt="\n\n".join(blocks),
                system_instruction=SYSTEM,
                history_title=f"リライト（{direction}）: {source[:40]}",
                history_summary=f"方向性: {direction} / 分量: {ratio} / 読み手: {audience or '指定なし'}",
                temperature=min(ui.current_temperature(), 0.6),
            )

    ui.result_area(TOOL_KEY, filename="rewrite.md")
