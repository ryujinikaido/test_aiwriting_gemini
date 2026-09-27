"""受け取ったメールへの返信文を組み立てるツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "mail"
ICON = "📧"
LABEL = "メール返信"
DESCRIPTION = "受信メールを貼り付けて方針を選ぶだけで、失礼のない返信文を作ります。"

SYSTEM = (
    "あなたは日本のビジネスメールに精通した秘書です。"
    "相手との関係性と敬語レベルに合わせ、簡潔で失礼のない返信文を作成します。"
    "事実として確認できない情報を勝手に断定せず、必要なら [日付] のようなプレースホルダを置いてください。"
    "出力はメール本文のみ。解説やメタ発言は書かないでください。"
)

POLITENESS = {
    "社外・初めての相手（最も丁寧）": "初めて連絡する社外の相手。二重敬語を避けつつ最も丁寧な表現にする。",
    "社外・取引のある相手（丁寧）": "やり取りのある取引先。丁寧だが冗長になりすぎない。",
    "社内・上司（敬語）": "社内の上司。敬語だが簡潔に。",
    "社内・同僚（ややカジュアル）": "社内の同僚。ですます調のまま前置きは最小限に。",
    "友人・知人（カジュアル）": "親しい相手。堅い定型句は使わず自然な口語で。",
}

STANCES = [
    "承諾する / 前向きに進める",
    "丁重にお断りする",
    "条件を交渉・調整したい",
    "質問・確認をする",
    "お礼を伝える",
    "お詫び・謝罪をする",
    "催促する",
]


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    received = ui.long_text_input(
        "返信したいメール本文 *",
        key="mail_src",
        height=220,
        placeholder="お世話になっております。株式会社◯◯の△△です。\n先日ご相談した件ですが……",
    )

    with st.form("mail_form"):
        intent = st.text_area(
            "返信で伝えたいこと *",
            height=100,
            placeholder="例: 日程は来週火曜15時なら可能。資料は明日中に送る。見積もりは予算オーバーなので調整をお願いしたい。",
        )
        col1, col2 = st.columns(2)
        with col1:
            politeness = st.selectbox("相手との関係・敬語レベル", list(POLITENESS))
            length = st.radio(
                "長さ",
                ["簡潔（5〜8行）", "標準（10行前後）", "しっかり（15行以上）"],
                index=1,
            )
        with col2:
            stance = st.selectbox("返信のスタンス", STANCES)
            sender = st.text_input(
                "差出人（自分）の署名", placeholder="例: 株式会社□□ 山田太郎"
            )
        variants = st.checkbox("2案つくる（丁寧版 / 簡潔版）", value=False)
        submitted = st.form_submit_button("✉️ 返信文をつくる", type="primary")

    if submitted:
        if not received.strip() or not intent.strip():
            st.warning("メール本文と「伝えたいこと」の両方を入力してください。")
        else:
            prompt = _build_prompt(
                received, intent, politeness, length, sender, stance, variants
            )
            ui.generate(
                TOOL_KEY,
                prompt=prompt,
                system_instruction=SYSTEM,
                history_title=f"メール返信（{stance}）",
                history_summary=f"スタンス: {stance} / {politeness}\n伝えたいこと: {intent}",
                temperature=min(ui.current_temperature(), 0.6),
            )

    ui.result_area(TOOL_KEY, filename="mail_reply.txt")


def _build_prompt(
    received: str,
    intent: str,
    politeness: str,
    length: str,
    sender: str,
    stance: str,
    variants: bool,
) -> str:
    blocks = [
        "以下のメールへの返信文を作成してください。",
        f"# 受信したメール\n```\n{received}\n```",
        f"# この返信で伝えたいこと\n{intent}",
        f"# スタンス\n{stance}",
        f"# 敬語レベル\n{POLITENESS[politeness]}",
        f"# 長さ\n{length}",
    ]
    if sender.strip():
        blocks.append(f"# 署名\n本文の最後に次の署名を入れる:\n{sender}")
    blocks.append(
        "# 守ること\n"
        "- 1行目に「件名: 」として件名（Re: 付き）を書く\n"
        "- 冒頭で相手の用件に触れ、結論を先に述べる\n"
        "- 不明な固有名詞・日付は作り話にせず [日付] のように空欄で示す\n"
        "- 定型句を並べすぎず、要件が一読でわかる構成にする"
    )
    if variants:
        blocks.append("# 出力形式\n「## 案1: 丁寧版」と「## 案2: 簡潔版」の2パターンを出す。")
    return "\n\n".join(blocks)
