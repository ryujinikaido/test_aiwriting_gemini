# AIライティングツールの設計図

> ブログ記事、メール返信、校正、翻訳——9つの文章ツールを1つのアプリに詰め込んだ Streamlit アプリ。
> 総量は数百行しかないのに、ツールを1つ足すのに必要な作業は「ファイルを1つ作って、リストに1行足す」だけ。
> その仕掛けを、実際のコードを追いながら解剖します。

対象: `app.py` / `core/` 4ファイル / `tools/` 10ファイル — Streamlit × Gemini API、認証・DB なし

---

## 1. このアプリが何をするものか

ローカルで `streamlit run app.py` と叩くと、サイドバーにツールの一覧が並んだ画面が立ち上がります。
左でツールを選び、フォームを埋めてボタンを押すと、Gemini が文章を書きながら画面に流し込んでくる——それだけのアプリです。ログインもデータベースもありません。

| ツール | モジュール | ツール | モジュール |
|---|---|---|---|
| ✍️ ブログ記事 | `blog` | 📣 SNS投稿文 | `sns` |
| 📧 メール返信 | `mail` | 💡 タイトル・コピー案 | `ideas` |
| 📝 要約 | `summarize` | 🌐 翻訳 | `translate` |
| 🔁 リライト・文体変換 | `rewrite` | 💬 相談チャット | `chat` |
| 🔍 校正・推敲 | `proofread` | 📚 履歴 | `history_view` |

面白いのは中身の分け方です。9つのツールは、やっていることが「フォームを出して、その内容からプロンプトを組み立てる」という一点に切り詰められています。
**生成も、表示も、保存も、ツール側には書かれていません。**

---

## 2. 4つの層を、一方向に流れる

このアプリの背骨は、依存が一方通行だということです。上流は下流を知っていますが、下流は上流を知りません。
そして **`tools/` のモジュール同士は、互いを import しません**。

```
層1  app.py          ツール一覧とサイドバー。どの画面を描くかを決めるだけ
  ↓
層2  tools/*.py      画面ごとのフォームと、入力からのプロンプト組み立て
  ↓
層3  core/ui.py      生成の実行、結果の表示、ダウンロード、履歴保存
  ↓
層4  core/gemini.py  Gemini API の薄いラッパー。ストリーミングはここだけ
```

＋ `core/config.py`（APIキーとモデル解決）と `core/history.py`（JSON 履歴）が横から支えます。

この形のおかげで、たとえば「API の呼び方を変えたい」ときに触るのは層4だけ、「生成結果の見せ方を変えたい」なら層3だけで済みます。9つのツールを1つずつ直して回る必要がありません。

---

## 3. `app.py` は「目次」しか持っていない

エントリーポイントである `app.py` には、各ツールの中身が一切書かれていません。
モジュールをリストに並べ、そのモジュールが公開している属性を読んで画面を組み立てます。

```python
# app.py — 画面に並べるツール（サイドバーの並び順もこの順番）
TOOLS = [blog, mail, summarize, rewrite, proofread, sns, ideas, translate, chat]
TOOL_LABELS = {t.TOOL_KEY: f"{t.ICON} {t.LABEL}" for t in TOOLS}
PAGES = {f"{t.ICON} {t.LABEL}": t for t in TOOLS}
```

そして描画は、選ばれたラベルからモジュールを引いて `render()` を呼ぶだけ。
`if page == "ブログ記事": ...` のような分岐は1つもありません。

```python
# app.py — main()
if page == HISTORY_PAGE:
    history_view.render(TOOL_LABELS)
else:
    PAGES[page].render()
```

これが成り立つのは、`tools/` の各モジュールが同じ「顔」を持つと決めてあるからです。
Python にインターフェース宣言は要らず、同じ名前の属性さえあれば同じように扱えます（ダックタイピング）。
ツールモジュールの約束は4つの定数と1つの関数だけ。

```python
# tools/proofread.py — 冒頭
TOOL_KEY = "proofread"      # 履歴とセッション状態のキー
ICON     = "🔍"             # サイドバーの絵文字
LABEL    = "校正・推敲"       # サイドバーの表示名
DESCRIPTION = "誤字脱字や読みにくい箇所を指摘し、修正版まで出します。"

def render() -> None: ...   # 画面ぜんぶ
```

> **この設計の効き目**
> 10個目のツールを足す作業は、**① `tools/` にファイルを1つ作る ② `TOOLS` に名前を1つ足す**——これだけです。
> サイドバー、ページ切り替え、履歴のラベル表示は、すべて自動でついてきます。

例外は履歴画面 `tools/history_view.py` です。ここだけ `render(tool_labels)` と引数を取るため `TOOLS` には入れず、`app.py` 側で特別扱いしています。
「例外は1つだけ、しかもコードを読めばすぐ分かる場所にある」——ルールを崩すときの、素直な崩し方です。

---

## 4. サイドバーが持つ3つのつまみ

### 4-1. モデル選択 — 一覧をハードコードしない

ここは地味ですが、いちばん寿命が延びる工夫です。選べるモデルの一覧を定数で持たず、**APIキーを使って実際に使えるモデルを毎回問い合わせています**（1時間キャッシュ）。
提供終了したモデルは選択肢から勝手に消え、新モデルは勝手に増えます。

```python
# core/config.py — available_models()
names = list_text_models(api_key) if api_key else []
if not names:
    names = list(FALLBACK_MODELS)      # 取得に失敗したときだけ暫定リスト
return {model_label(n): n for n in sorted(names, key=_sort_key)}
```

`core/gemini.py` の `list_text_models()` が、名前に `embedding` / `imagen` / `veo` / `tts` などを含むモデル（文章生成に使えないもの）を弾き、`_sort_key()` が「新しい世代 → 上位ティア → 安定版」の順に並べ替えます。
表示名は `Gemini 2.5 Flash（速い・普段使い）` のように日本語のヒント付きに整形されます。

さらに、セッションに保存されていたモデルが一覧から消えていた場合の面倒も見ています。

```python
# app.py — _model_selector()
# 前回選んだモデルが使えなくなっていたら、既定に戻す
current = st.session_state.get("model")
selected_id = current if current in ids else pick_default(ids)
```

### 4-2. 創造性（temperature）

0.0〜1.5、既定 0.7 のスライダー。値は `st.session_state["temperature"]` に入り、全ツールから参照されます。
ただし、そのまま使われるわけではありません（→ 第6章）。

### 4-3. APIキー — 3段階で探す

```python
# core/config.py — get_api_key()
key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")   # ① .env
if not key:
    key = st.secrets.get("GEMINI_API_KEY")                         # ② secrets
if not key:
    key = st.session_state.get("manual_api_key")                   # ③ 画面入力
return key or None
```

③のサイドバー直接入力は、ブラウザのセッションにしか残りません（ファイルに書き出さない）。ちょっと試したいときの逃げ道として用意されています。

> **⚠ ハマりどころ**
> `load_dotenv()` は `core.config` が import される瞬間に一度だけ走ります。
> つまり **`.env` を書き換えたら、アプリを再起動しないと反映されません**。
> 「キーを直したのに未設定のまま」のときは、まずここを疑ってください。

なお、キーが無くてもツール画面そのものは描画されます。エラーになるのは生成ボタンを押した瞬間。
「動かしてみないと何のアプリか分からない」状態を避ける作りです。

---

## 5. ツールの仕事は、プロンプトを組み立てるまで

各ツールは、**役割を固定する system 指示**と、**入力から組み立てる prompt** の2つを作って `ui.generate()` に渡します。
system 側はモジュール定数で、ツールの人格そのものです。

```python
# tools/blog.py
SYSTEM = (
    "あなたは日本語のプロのWebライター兼編集者です。"
    "抽象的な一般論や水増し表現は避け、具体例・数字・手順を入れてください。"
    "出力は Markdown 形式（見出しは ## / ###）で、記事本文だけを返します。"
    "「承知しました」などの前置きやメタ発言は書かないでください。"
)
```

prompt 側は、見出し付きのブロックをリストに積んで最後に連結する、という素直な作りです。
任意項目は、入力があったときだけ `append` されます。

```python
# tools/blog.py — _build_prompt()
blocks = [
    "次の条件でブログ記事を書いてください。",
    f"# テーマ\n{topic}",
    f"# 想定読者\n{target or '特に指定なし（一般的なWeb読者）'}",
    f"# 文体・トーン\n{tone}",
    f"# 分量の目安\n{ui.LENGTH_HINTS[length]}",
]
if keywords.strip():
    blocks.append(f"# 自然に含めるキーワード\n{keywords}")
...
return "\n\n".join(blocks)
```

注目したいのは、最後に必ず **「# 出力形式」ブロックを足している**ことです。
「タイトル → リード文 → 本文 → まとめ」と構造まで指定してあるので、返ってくる Markdown の形が毎回安定します。
校正ツールに至っては、指摘一覧を Markdown の表で出せと、列まで指定しています。

```python
# tools/proofread.py — 出力形式の指定
fmt = [
    "## 指摘一覧",
    "| # | 該当箇所 | 指摘内容 | 修正案 |",
    "|---|---|---|---|",
    "の形式の表で、重要な順に並べる。該当箇所は原文から短く引用する。",
]
```

「選択肢は辞書で持ち、キーを画面に出し、値をプロンプトに入れる」という書き方も一貫しています。
たとえば校正の厳しさは `{"軽め（明らかなミスだけ）": "明らかな誤りだけを指摘し…"}` という辞書で、UI のラベルと AI への指示文が一箇所に並んでいます。増やすのも直すのも、辞書に1行です。

---

## 6. いちばんの勘所 — 二重表示を防ぐ受け渡し

ここだけは、コードを読んだだけでは意図が分かりにくい部分です。
`ui.generate()` と `ui.result_area()` は、`st.session_state` を挟んで暗黙に連携しています。

1. `generate()` が `st.write_stream` で **画面に描きながら** 生成し、結果を `session_state["result_<TOOL_KEY>"]` に保存する
2. 同時に `session_state["_just_generated"]` に自分の `TOOL_KEY` を立てる
3. `result_area()` がそのフラグを `pop` する。自分のキーなら **本文を再描画しない**（すでに write_stream が描いているので、描くと二重になる）
4. 自分のキーでなければ「前回の生成結果」として `st.markdown` で描く

```python
# core/ui.py — result_area()
just_generated = st.session_state.pop("_just_generated", None) == tool_key
if not just_generated:
    st.subheader("前回の生成結果")
    st.markdown(text)
```

> **⚠ 守るべきルール**
> `ui.result_area()` は、**submit の分岐の外で、`render()` の末尾に無条件で呼ぶ**こと。
> submit されたときだけ呼ぶ書き方にすると、Streamlit が再実行されるたび（スライダーを触っただけでも）過去の結果が画面から消えてしまいます。

Streamlit は「入力のたびにスクリプトを頭から実行し直す」フレームワークなので、*前回描いたもの* は自分で覚えておかないと消えます。
この2関数の取り決めは、その性質に対する答えです。結果が残っていれば、文字数・ダウンロードボタン・コピー用のコードブロック・クリアボタンもまとめて付いてきます。

---

## 7. temperature は、ツール側で握り潰す

サイドバーのスライダーはあくまで**グローバルな気分**です。
各ツールは、その値を用途に合わせて `min()` / `max()` で制限してから API に渡します。
正確さが要る仕事には上限を、発想が要る仕事には下限をかける——という方針です。

```python
temperature=min(ui.current_temperature(), 0.3)   # 校正：暴れさせない
temperature=max(ui.current_temperature(), 1.0)   # 案出し：固くさせない
```

| ツール | クランプ | 値 | 意図 |
|---|---|---|---|
| 校正・推敲 | 上限 | 0.3 | 原文を勝手に書き換えさせない |
| 要約 | 上限 | 0.4 | 事実を足させない |
| 翻訳 | 上限 | 0.4 | 訳文をブレさせない |
| メール返信 | 上限 | 0.6 | 礼を失しない範囲で自然に |
| リライト | 上限 | 0.6 | 意味を保ったまま書き換える |
| SNS投稿文 | 下限 | 0.9 | 面白みを殺さない |
| タイトル・コピー案 | 下限 | 1.0 | 切り口を散らす |
| ブログ記事／相談チャット | — | そのまま | ユーザーの指定を尊重 |

新しいツールを足すときも、この方針を踏襲するのが吉です。

---

## 8. ストリーム中の例外は、投げずにリストへ入れる

生成はストリーミング（少しずつ届いたテキストを即座に画面へ流す）で行われます。
ここで厄介なのが、途中で通信エラーが起きたときです。ジェネレータの中で例外を raise すると、`st.write_stream` が描きかけの状態で止まり、画面が壊れます。

そこで、例外を**投げずにリストへ詰めて、ジェネレータ自体は正常終了させる**という手を使っています。

```python
# core/ui.py
def _safe_stream(gen, errors: list[Exception]):
    try:
        for chunk in gen:
            yield chunk
    except Exception as exc:
        errors.append(exc)          # 投げずに溜める

# 呼び出し側は、ストリームが終わってから errors を見る
errors: list[Exception] = []
text = st.write_stream(_safe_stream(stream, errors))
if errors:
    st.error(f"生成に失敗しました: {errors[0]}")
```

チャット画面では、これに後始末が1行足されます。失敗したときに `messages.pop()` で**直前のユーザー発言を巻き戻す**のです。

```python
# tools/chat.py
if errors:
    st.error(f"生成に失敗しました: {errors[0]}")
    messages.pop()      # 返事が無いユーザー発言を履歴に残さない
    return
```

巻き戻さないと、「ユーザー発言だけがあって返事が無い」という歪んだ履歴を次の送信で API に渡すことになります。
会話履歴を自前で持つときの、定番の落とし穴です。

---

## 9. 履歴は、JSON ファイル1枚

データベースは使いません。`history/history.json` に配列で丸ごと書き出すだけです。
新しいものが先頭、上限300件。`insert(0, ...)` で先頭に足し、保存時に `[:MAX_ITEMS]` で尻を切る——たった2行で「新しい順・件数制限」が成立します。

```python
# core/history.py — add_history()
items.insert(0, {
    "id": uuid.uuid4().hex[:8],
    "tool": tool,
    "title": title[:80] or "(無題)",
    "prompt_summary": prompt_summary[:400],
    "output": output,
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
})
_save(items[:MAX_ITEMS])
```

読み込み側は、ファイルが無くても JSON が壊れていても**空リストを返して黙って続行**します。
履歴は本質的な機能ではないので、壊れてもアプリ全体は止めない、という判断です。

保存は `ui.generate()` が自動で行うため、ツール側は `history_title` と `history_summary` を渡すだけ。
履歴画面ではツールでの絞り込みとキーワード検索ができ、`app.py` が作った `TOOL_LABELS`（キー → 「🔍 校正・推敲」）を受け取って絵文字付きの名前で表示します。ここでも、ツール名の定義元は1箇所きりです。

---

## 10. 持ち帰れる4つの型

1. **「同じ顔」を決めて、リストに並べる。**
   `TOOL_KEY` / `ICON` / `LABEL` / `DESCRIPTION` / `render()` の5つを約束にしたから、分岐を1つも書かずに画面が増やせる。Python なら継承も基底クラスも要らない。

2. **変わるものを、外から取る。**
   モデル名は定数ではなく API から。失敗したときだけ暫定リストに落ちる。提供終了に人間が追従しなくていい構造になる。

3. **再実行前提のフレームワークでは、状態の受け渡しを明文化する。**
   `_just_generated` フラグと「`result_area()` は末尾で無条件に呼ぶ」という規約。暗黙の約束は、コードの近くに書き残す。

4. **エラーは、壊れない形に変換してから扱う。**
   ストリーム中の例外はリストに詰めて後で見る。会話履歴は失敗したら巻き戻す。

次にこのアプリを触るなら、10個目のツールを足してみるのが近道です。
`tools/` の既存ファイルを1つコピーして、定数5つと `_build_prompt()` を書き換え、`app.py` の `TOOLS` に足す。
それだけで、サイドバーにも履歴にも、勝手に馴染みます。

---

対象コード: `app.py` / `core/config.py` / `core/gemini.py` / `core/ui.py` / `core/history.py` / `tools/*.py`
— Streamlit + google-genai + python-dotenv
