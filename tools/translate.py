"""翻訳ツール。トーンを保ったまま訳す。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "translate"
ICON = "🌐"
LABEL = "翻訳"
DESCRIPTION = "直訳ではなく、場面と相手に合った自然な訳文にします。"

SYSTEM = (
    "あなたはプロの翻訳者です。逐語訳ではなく、目的の言語の読み手にとって自然な表現に置き換えます。"
    "原文の意味・トーン・敬意のレベルを保ち、情報を足したり省いたりしません。"
    "訳文のみを出力し、前置きは書かないでください。"
)

LANGUAGES = [
    "日本語",
    "英語",
    "中国語（簡体字）",
    "中国語（繁体字）",
    "韓国語",
    "フランス語",
    "ドイツ語",
    "スペイン語",
    "ポルトガル語",
    "タイ語",
    "ベトナム語",
]

REGISTERS = {
    "ビジネス（フォーマル）": "取引先に出せるフォーマルな文体。",
    "日常会話（カジュアル）": "友人に話すような自然な口語。",
    "技術文書": "技術用語は正確に。曖昧さを避けた説明的な文体。",
    "マーケティング": "買いたくなるトーン。多少の意訳は可。",
}


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    source = ui.long_text_input(
        "翻訳したい文章 *",
        key="tr_src",
        height=220,
        placeholder="ここに原文を貼り付けてください。",
    )

    with st.form("tr_form"):
        col1, col2 = st.columns(2)
        with col1:
            src_lang = st.selectbox("原文の言語", ["自動判定"] + LANGUAGES)
            register = st.selectbox("文体", list(REGISTERS))
        with col2:
            dst_lang = st.selectbox("訳したい言語", LANGUAGES, index=1)
            back = st.checkbox("逆翻訳して意味のズレを確認する", value=False)
        glossary = st.text_area(
            "用語の指定（任意・1行1組）",
            height=80,
            placeholder="生成AI = generative AI\n弊社 = our company",
        )
        submitted = st.form_submit_button("🌐 翻訳する", type="primary")

    if submitted:
        if not source.strip():
            st.warning("翻訳したい文章を入力してください。")
        else:
            src = "原文の言語を自動判定する" if src_lang == "自動判定" else src_lang
            blocks = [
                f"次の文章を{dst_lang}に翻訳してください。",
                f"# 原文（{src}）\n```\n{source}\n```",
                f"# 訳文の文体\n{REGISTERS[register]}",
            ]
            if glossary.strip():
                blocks.append(f"# 訳語の指定（必ず従う）\n{glossary}")
            if back:
                blocks.append(
                    "# 出力形式\n"
                    "## 訳文 に翻訳結果、## 逆翻訳 に訳文を元の言語へ戻した文、"
                    "## 補足 に意味がズレやすい箇所や訳し分けの理由を3点以内で書く。"
                )
            else:
                blocks.append("# 出力形式\n訳文だけを出す。")
            ui.generate(
                TOOL_KEY,
                prompt="\n\n".join(blocks),
                system_instruction=SYSTEM,
                history_title=f"{src_lang}→{dst_lang}: {source[:40]}",
                history_summary=f"{src_lang} → {dst_lang} / 文体: {register}",
                temperature=min(ui.current_temperature(), 0.4),
            )

    ui.result_area(TOOL_KEY, filename="translation.md")
