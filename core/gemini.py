"""Gemini API の薄いラッパー。ストリーミング生成をここに集約する。"""

from __future__ import annotations

from typing import Iterator

import streamlit as st
from google import genai
from google.genai import types


@st.cache_resource(show_spinner=False)
def get_client(api_key: str) -> genai.Client:
    """APIキーごとにクライアントを使い回す。"""
    return genai.Client(api_key=api_key)


def stream_text(
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.7,
    max_output_tokens: int | None = None,
) -> Iterator[str]:
    """プロンプトを投げて、生成されたテキストを少しずつ返す。"""
    client = get_client(api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction or None,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    stream = client.models.generate_content_stream(
        model=model, contents=prompt, config=config
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def generate_text(
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.7,
) -> str:
    """ストリーミングせず、まとめて生成する（短い用途向け）。"""
    client = get_client(api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction or None,
        temperature=temperature,
    )
    res = client.models.generate_content(model=model, contents=prompt, config=config)
    return res.text or ""


def count_tokens(api_key: str, model: str, text: str) -> int | None:
    """入力テキストのトークン数を数える。失敗したら None。"""
    try:
        client = get_client(api_key)
        res = client.models.count_tokens(model=model, contents=text)
        return res.total_tokens
    except Exception:
        return None


def stream_chat(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    system_instruction: str = "",
    temperature: float = 0.7,
) -> Iterator[str]:
    """会話履歴つきで生成する。messages は {"role": "user"|"model", "content": str}。"""
    client = get_client(api_key)
    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]
    config = types.GenerateContentConfig(
        system_instruction=system_instruction or None,
        temperature=temperature,
    )
    stream = client.models.generate_content_stream(
        model=model, contents=contents, config=config
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


# 生成に使えないモデル（埋め込み・画像・音声・動画など）を名前で弾く
_NON_TEXT_HINTS = (
    "embedding", "imagen", "veo", "tts", "audio", "image",
    "live", "computer-use", "robotics", "aqa",
)


@st.cache_data(ttl=3600, show_spinner=False)
def list_text_models(api_key: str) -> list[str]:
    """APIキーで実際に使えるテキスト生成モデルのIDを返す。失敗したら空リスト。

    モデルの提供終了・新モデル追加に追従するため、一覧はハードコードせず
    毎回APIに問い合わせる（1時間キャッシュ）。
    """
    try:
        client = get_client(api_key)
        found: list[str] = []
        for m in client.models.list():
            name = (m.name or "").removeprefix("models/")
            actions = getattr(m, "supported_actions", None) or []
            if not name.startswith("gemini-"):
                continue
            if actions and "generateContent" not in actions:
                continue
            if any(h in name for h in _NON_TEXT_HINTS):
                continue
            found.append(name)
        return found
    except Exception:
        return []
