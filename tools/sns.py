"""SNS 投稿文を作るツール。"""

from __future__ import annotations

import streamlit as st

from core import ui

TOOL_KEY = "sns"
ICON = "📣"
LABEL = "SNS投稿文"
DESCRIPTION = "伝えたいことを、各SNSの作法に合わせた投稿文に整えます。"

SYSTEM = (
    "あなたはSNS運用のプロです。各プラットフォームの文化と文字数制限を理解しています。"
    "最初の1〜2行で読み手の手を止めさせ、そのあとに中身を置く構成にします。"
    "誇張や煽りすぎ、絵文字の使いすぎは避け、投稿文そのものだけを出力してください。"
)

PLATFORMS = {
    "X（旧Twitter）": "140字以内に収める。1投稿で完結させ、改行を使って読みやすく。ハッシュタグは多くても2つ。",
    "X（連続ポスト・スレッド）": "1本目でフックを作り、2〜5本の連続ポストに分ける。各ポストは140字以内。番号を振る。",
    "Instagram": "冒頭2行で引き込み、改行を多めに。最後に関連ハッシュタグを10〜15個まとめて置く。",
    "Facebook": "やや長め（300〜500字）で、体験や背景を語る文体。ハッシュタグは少なめ。",
    "LinkedIn": "ビジネス文脈。学びや示唆を中心に、300〜600字。最後に問いかけで締める。",
    "note / ブログ告知": "記事に誘導する告知文。何が読めるのかを具体的に示す。200〜300字。",
    "YouTube 概要欄": "動画の内容・見どころ・タイムスタンプ例・関連リンクの枠を含む構成にする。",
}


def render() -> None:
    ui.tool_header(ICON, LABEL, DESCRIPTION)

    with st.form("sns_form"):
        content = st.text_area(
            "投稿したい内容・伝えたいこと *",
            height=140,
            placeholder="例: 個人開発したAIライティングツールを公開した。Streamlit+Gemini製で、ブログ・メール・要約が1つにまとまっている。",
        )
        col1, col2 = st.columns(2)
        with col1:
            platform = st.selectbox("投稿先", list(PLATFORMS))
            tone = st.selectbox("トーン", ui.TONES, index=1)
        with col2:
            n = st.slider("案の数", 1, 5, 3)
            hashtags = st.checkbox("ハッシュタグを付ける", value=True)
        cta = st.text_input(
            "最後に促したい行動（任意）", placeholder="例: プロフィールのリンクから試してほしい"
        )
        submitted = st.form_submit_button("📣 投稿文をつくる", type="primary")

    if submitted:
        if not content.strip():
            st.warning("投稿したい内容を入力してください。")
        else:
            blocks = [
                f"次の内容を「{platform}」向けの投稿文にしてください。",
                f"# 伝えたいこと\n{content}",
                f"# プラットフォームの作法\n{PLATFORMS[platform]}",
                f"# トーン\n{tone}",
                f"# ハッシュタグ\n{'内容に合ったものを付ける' if hashtags else '付けない'}",
            ]
            if cta.strip():
                blocks.append(f"# 促したい行動\n{cta}")
            blocks.append(
                f"# 出力形式\n案を{n}つ出す。それぞれ「## 案1」のような見出しを付け、"
                "見出しの下に投稿文をそのままコピーできる形で書く。案ごとに切り口を変える。"
                "各案の最後に「→ 狙い: 〜」と1行で意図を添える。"
            )
            ui.generate(
                TOOL_KEY,
                prompt="\n\n".join(blocks),
                system_instruction=SYSTEM,
                history_title=f"{platform}: {content[:40]}",
                history_summary=f"投稿先: {platform} / トーン: {tone} / {n}案",
                temperature=max(ui.current_temperature(), 0.9),
            )

    ui.result_area(TOOL_KEY, filename="sns.md")
