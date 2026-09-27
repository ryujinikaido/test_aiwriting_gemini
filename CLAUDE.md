# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Streamlit + Gemini API による個人用ライティング支援ツール。認証・DB なし、ローカル起動のみ。
コード・コメント・UI 文言はすべて日本語で統一されている。

## コマンド

```bash
pip install -r requirements.txt
streamlit run app.py          # Windows は run.bat でも可
```

テストスイートは無い。変更後の動作確認は `streamlit.testing.v1.AppTest` で全ページを回す:

```bash
PYTHONIOENCODING=utf-8 GEMINI_API_KEY=DUMMY python -c "
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('app.py', default_timeout=60).run()
for opt in at.sidebar.radio[0].options:
    t = AppTest.from_file('app.py', default_timeout=60).run()
    t.sidebar.radio[0].set_value(opt).run()
    print(opt, list(t.exception))
"
```

ダミーキーでも UI 描画パスは全て通る（実際の API 呼び出しはボタン押下時のみ）。
`ScriptRunContext` の警告は bare mode の正常な出力なので無視してよい。

**Windows 固有**: このマシンの Python は cp932 のため、日本語を stdout に出す
スクリプトは `PYTHONIOENCODING=utf-8` を付けないと `UnicodeEncodeError` で落ちる。

## アーキテクチャ

`app.py`（ナビゲーション）→ `tools/*.py`（画面ごとのフォームとプロンプト組み立て）
→ `core/ui.py`（生成の実行と結果表示）→ `core/gemini.py`（API 呼び出し）の一方向。
`tools/` 同士は互いを import しない。

### ツールモジュールの規約

`tools/` の各モジュールは `TOOL_KEY` / `ICON` / `LABEL` / `DESCRIPTION` と `render()` を公開する。
`app.py` は `TOOLS` リストに並べたモジュールの属性を読んでサイドバーを組み立てるので、
ツール追加は「ファイルを1つ作り、`TOOLS` に足す」だけで済む。

`tools/history_view.py` だけは例外で、`TOOLS` に入れず `render(tool_labels)` と引数を取る。

### 生成〜結果表示の session_state プロトコル（要注意）

`ui.generate()` と `ui.result_area()` は暗黙の状態で連携している:

1. `ui.generate()` が `st.write_stream` で画面に描きながら、結果を
   `st.session_state["result_<TOOL_KEY>"]` に保存し、`_just_generated` に TOOL_KEY を立てる
2. `ui.result_area()` が `_just_generated` を pop する。自分の TOOL_KEY だったら
   **本文を再描画しない**（write_stream が既に描いているため二重表示になる）。
   そうでなければ「前回の生成結果」として markdown を描く

このため `ui.result_area()` は **submit 分岐の外で、`render()` の末尾に無条件で呼ぶ**こと。
submit 時だけ呼ぶと、再実行時に過去の結果が消える。

### temperature はツール側でクランプする

サイドバーのスライダー（0.0〜1.5）はグローバル設定で、各ツールが用途に合わせて
`min()` / `max()` で握り潰す。正確さが要るものは上限、発想が要るものは下限をかける:

| 上限をかける | 下限をかける |
|---|---|
| proofread 0.3 / summarize 0.4 / translate 0.4 / mail 0.6 / rewrite 0.6 | sns 0.9 / ideas 1.0 |

`blog` と `chat` はスライダーの値をそのまま使う。新しいツールでもこの方針を踏襲する。

### ストリーム中の例外は戻り値ではなくリストで受ける

ジェネレータ内で raise すると `st.write_stream` の途中で画面が壊れるため、
`ui.safe_stream(gen, errors)` が例外を `errors` リストに詰めて正常終了させ、
呼び出し側がストリーム終了後に `errors` を見てエラー表示する。
`tools/chat.py` はこの検知時に `messages.pop()` で失敗したユーザー発言を巻き戻している
（巻き戻さないと、次の送信で不整合な履歴を API に渡すことになる）。

### APIキーの解決

`core.config.get_api_key()` が `.env` → `st.secrets` → `st.session_state["manual_api_key"]`
の順に探す。`load_dotenv()` は `core.config` の import 時に一度だけ走るので、
**`.env` を書き換えたらアプリの再起動が必要**。
キーが無くてもツール画面自体は描画され、生成を実行した時点で `ui.generate()` がエラーを出す。

### long_text_input のウィジェットキー差し替え

`ui.long_text_input()` はファイルアップロード時、`ta_<key>_<filename>` へ
ウィジェットキーを切り替えて text_area を作り直す。Streamlit は既存キーの
ウィジェットに `value` を後から反映しないため、読み込んだ内容を初期値に入れるにはこの差し替えが必要。

### 履歴

`history/history.json` の単一ファイル。新しい順、上限 300 件（`core/history.py` の `MAX_ITEMS`）。
gitignore 済みで、リポジトリには残らない。
