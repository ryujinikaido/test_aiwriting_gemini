# ✍️ AI ライティングツール

Python + Streamlit + Gemini API で作った、個人用のライティング支援ツールです。
ブログ執筆・メール返信・要約など、よく使う文章まわりの作業を1つの画面にまとめています。
ログインもデータベースも不要。ローカルで起動して、自分だけで使う想定です。

## できること

| ツール | 用途 |
|---|---|
| ✍️ ブログ記事 | テーマと読者を指定して、見出し構成つきの記事本文を生成（構成案のみも可） |
| 📧 メール返信 | 受信メールを貼り付け、返信のスタンスと敬語レベルを選ぶだけで返信文を作成 |
| 📝 要約 | 議事録・記事を3行／箇条書き／議事録形式などにまとめ直す |
| 🔁 リライト・文体変換 | 敬語化・カジュアル化・簡潔化・PREP法など8方向に書き換え |
| 🔍 校正・推敲 | 誤字脱字や係り受けを指摘一覧＋修正版で返す |
| 📣 SNS投稿文 | X / Instagram / LinkedIn など、媒体の作法に合わせた投稿文を複数案 |
| 💡 タイトル・コピー案 | 記事タイトル・メール件名・キャッチコピーを切り口別に量産 |
| 🌐 翻訳 | 11言語・4つの文体。逆翻訳で意味のズレも確認できる |
| 💬 相談チャット | フォームに収まらない相談を、会話しながら詰める |
| 📚 履歴 | 生成結果をローカルに保存。検索・ダウンロード・削除ができる |

## セットアップ

```bash
pip install -r requirements.txt
```

APIキーは [Google AI Studio](https://aistudio.google.com/apikey) で無料で取得できます。

```bash
# .env.example をコピーして .env を作る
cp .env.example .env
# .env を開いて、取得したキーを書く
# GEMINI_API_KEY=AIza...
```

`.env` を作らずに、アプリのサイドバーへ直接キーを貼り付けてもかまいません
（その場合はブラウザを閉じるまでの一時的な保持で、ファイルには残りません）。

## 起動

```bash
streamlit run app.py
```

Windows なら `run.bat` をダブルクリックでも起動できます。
ブラウザで http://localhost:8501 が開きます。

## サイドバーの設定

- **モデル** — 速さ重視なら Flash、じっくり長文を書かせたいなら Pro
- **創造性（temperature）** — 低いほど堅実、高いほど自由な発想
  （校正や翻訳など、正確さが要るツールでは内部で上限をかけています）

## ファイル構成

```
app.py                  画面の入口。サイドバーとページ切り替え
core/
  config.py             APIキーの取得、モデル一覧などの設定
  gemini.py             Gemini API の薄いラッパー（ストリーミング生成／チャット）
  ui.py                 各ツール共通のUI部品（生成・結果表示・履歴保存）
  history.py            履歴の保存・読み込み（history/history.json）
tools/
  blog.py mail.py summarize.py rewrite.py proofread.py
  sns.py ideas.py translate.py chat.py history_view.py
history/                生成履歴の保存先（gitignore 済み）
```

## ツールを追加したくなったら

`tools/` に新しいファイルを1つ作り、`TOOL_KEY` / `ICON` / `LABEL` と `render()` を用意して、
`app.py` の `TOOLS` リストに追加するだけです。生成・結果表示・履歴保存は
`core/ui.py` の `ui.generate()` と `ui.result_area()` が引き受けます。

```python
from core import ui

TOOL_KEY, ICON, LABEL = "myapp", "🧪", "新しいツール"

def render():
    ui.tool_header(ICON, LABEL, "説明文")
    # …入力ウィジェット…
    ui.generate(TOOL_KEY, prompt="…", system_instruction="…")
    ui.result_area(TOOL_KEY, filename="output.md")
```

## 注意

- APIキーは `.env` に置き、GitHub などに公開しないでください（`.gitignore` 済み）。
- 生成結果は必ず自分の目で確認してから使ってください。事実関係の誤りが混ざることがあります。
