"""アプリ全体の設定値、APIキーの取得、利用可能モデルの解決。"""

from __future__ import annotations

import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core.gemini import list_text_models

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_DIR = BASE_DIR / "history"

load_dotenv(BASE_DIR / ".env")

APP_TITLE = "AI ライティングツール"
APP_ICON = "✍️"

# APIキーが無くて一覧を引けないときだけ使う暫定リスト。
# 実際に選べるモデルは available_models() が API から取得する。
FALLBACK_MODELS = ["gemini-3.8-flash"]
DEFAULT_MODEL = "gemini-3.8-flash"

# 用途のヒント。長い名前から順に判定する（flash-lite を flash より先に見る）
_TIER_HINTS = (
    ("flash-lite", "最速・軽い用途"),
    ("pro", "賢い・長文向き"),
    ("flash", "速い・普段使い"),
)
_TIER_RANK = {"flash-lite": 2, "pro": 0, "flash": 1}


def get_api_key() -> str | None:
    """APIキーを .env → st.secrets → サイドバー入力 の順で探す。"""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY")  # type: ignore[assignment]
        except Exception:
            key = None
    if not key:
        key = st.session_state.get("manual_api_key")
    return key or None


def _tier(name: str) -> str:
    for tier, _ in _TIER_HINTS:
        if tier in name:
            return tier
    return ""


def _sort_key(name: str) -> tuple:
    """新しい世代・上位ティア・安定版 を先頭に持ってくる並び順。"""
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    version = float(m.group(1)) if m else 0.0
    unstable = 1 if ("preview" in name or "exp" in name) else 0
    return (-version, _TIER_RANK.get(_tier(name), 3), unstable, name)


def model_label(name: str) -> str:
    """モデルIDを、選びやすい日本語ラベルにする。"""
    pretty = name.removeprefix("gemini-").replace("-", " ").title()
    hint = next((h for tier, h in _TIER_HINTS if tier in name), "")
    label = f"Gemini {pretty}"
    return f"{label}（{hint}）" if hint else label


def available_models(api_key: str | None) -> dict[str, str]:
    """選択肢に出すモデルを {表示名: モデルID} で返す。

    APIキーがあれば実際に使える一覧を取得するので、提供終了したモデルは
    自動的に選択肢から消える。取得に失敗したときだけ FALLBACK_MODELS を使う。
    """
    names = list_text_models(api_key) if api_key else []
    if not names:
        names = list(FALLBACK_MODELS)
    return {model_label(n): n for n in sorted(names, key=_sort_key)}


def pick_default(model_ids: list[str]) -> str:
    """既定で選んでおくモデル。普段使いの flash を優先する。

    一覧に残っていても新規ユーザーには提供終了している旧モデルがあるため、
    model_ids（_sort_key で新しい順）のうち最新の安定版 flash を選ぶ。
    """
    stable_flash = [
        m for m in model_ids
        if _tier(m) == "flash" and "preview" not in m and "exp" not in m
    ]
    if stable_flash:
        return stable_flash[0]
    if DEFAULT_MODEL in model_ids:
        return DEFAULT_MODEL
    return (model_ids or [DEFAULT_MODEL])[0]
