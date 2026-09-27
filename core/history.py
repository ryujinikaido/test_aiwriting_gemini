"""生成結果をローカルの JSON ファイルに保存する簡易履歴。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from core.config import HISTORY_DIR

HISTORY_FILE = HISTORY_DIR / "history.json"
MAX_ITEMS = 300


def _load_raw() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def load_history(tool: str | None = None) -> list[dict[str, Any]]:
    """新しい順に履歴を返す。tool を指定するとそのツールだけ。"""
    items = _load_raw()
    if tool:
        items = [i for i in items if i.get("tool") == tool]
    return items


def add_history(tool: str, title: str, prompt_summary: str, output: str) -> None:
    """1件追加する。古いものは MAX_ITEMS を超えたら捨てる。"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    items = _load_raw()
    items.insert(
        0,
        {
            "id": uuid.uuid4().hex[:8],
            "tool": tool,
            "title": title[:80] or "(無題)",
            "prompt_summary": prompt_summary[:400],
            "output": output,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    )
    _save(items[:MAX_ITEMS])


def delete_history(item_id: str) -> None:
    _save([i for i in _load_raw() if i.get("id") != item_id])


def clear_history() -> None:
    _save([])


def _save(items: list[dict[str, Any]]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
