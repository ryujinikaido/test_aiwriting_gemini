"""セキュリティチェック用に、プロジェクトの事実を集める。

読み取り専用・外部通信なし。見つけた秘密情報は伏せ字で表示する。
ここでの検出は「読みに行くべき手がかり」であって、指摘そのものではない。

使い方（プロジェクト直下で）:
    python .claude/skills/app-security-audit/scripts/collect_facts.py
    python .claude/skills/app-security-audit/scripts/collect_facts.py --write-pinned <出力パス>
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from importlib import metadata, util
from pathlib import Path
from typing import Iterator

# Windows の cp932 コンソールでも日本語を出せるようにする
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 秘密情報の検出で見ないディレクトリ
SKIP_SECRET = {".git", ".venv", "venv", "env", "__pycache__", "node_modules"}
# コードの検出で見ないディレクトリ（.claude はこのスキル自身の説明文を拾うので除く）
SKIP_CODE = SKIP_SECRET | {".claude"}

TEXT_SUFFIXES = {
    ".py", ".toml", ".txt", ".md", ".json", ".bat", ".cmd", ".ps1", ".sh",
    ".cfg", ".ini", ".yaml", ".yml", ".example", ".html", ".js",
}
MAX_BYTES = 5 * 1024 * 1024

# 実物の `streamlit config show` で確認した既定値
STREAMLIT_KEYS = {
    "server.address": "（未設定）= 全ネットワークインターフェースで待ち受け",
    "server.port": "8501",
    "server.enableCORS": "true",
    "server.enableXsrfProtection": "true",
    "server.maxUploadSize": "200 (MB)",
    "server.headless": "false",
    "client.showErrorDetails": '"full"（例外の詳細をブラウザに表示）',
    "client.toolbarMode": '"auto"',
}

SENSITIVE_FILES = [".env", ".streamlit/secrets.toml", "history/history.json"]

# Windows ファイアウォール・接続中ネットワーク・待ち受け状況を読み取る（変更はしない）
PS_NETWORK = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$rules = Get-NetFirewallApplicationFilter |
  Where-Object { $_.Program -match 'python|streamlit' } |
  ForEach-Object {
    $prog = $_.Program
    foreach ($r in @($_ | Get-NetFirewallRule)) {
      [pscustomobject]@{
        name = $r.DisplayName; enabled = "$($r.Enabled)"; direction = "$($r.Direction)"
        action = "$($r.Action)"; profile = "$($r.Profile)"; program = $prog
      }
    }
  }
$listen = Get-NetTCPConnection -State Listen -LocalPort __PORT__ -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{ address = $_.LocalAddress } }
$profiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{ name = $_.Name; category = "$($_.NetworkCategory)" } }
@{ rules = @($rules); listen = @($listen); profiles = @($profiles) } | ConvertTo-Json -Depth 4
"""

SECRET_PATTERNS = [
    ("Google APIキー", r"AIza[0-9A-Za-z_\-]{35}"),
    ("秘密情報らしき代入", r"(?i)(api[_-]?key|secret|token|password|passwd)\w*\s*[:=]\s*[\"']?([A-Za-z0-9_\-.]{20,})"),
]

CODE_PATTERNS = [
    ("HTML をそのまま描画", r"unsafe_allow_html\s*=\s*True|\bst\.html\("),
    ("任意の HTML/JS を埋め込み", r"components(\.v1)?\.(html|iframe)\("),
    ("文字列をコードとして実行", r"(?<![\w.])(eval|exec)\("),
    ("外部コマンド実行", r"\bsubprocess\b|\bos\.(system|popen)\(|shell\s*=\s*True"),
    ("危険なデシリアライズ", r"\bpickle\.loads?\(|\bmarshal\.loads?\(|\byaml\.load\((?![^)]*SafeLoader)"),
    ("外部への HTTP 通信", r"\b(requests|httpx|aiohttp)\b|urllib\.request"),
    ("ファイル書き込み", r"\.write_(text|bytes)\(|\bopen\([^)]*[\"'][wax]b?\+?[\"']"),
    ("APIキーを表示・出力している可能性", r"(print|logging\.\w+|logger\.\w+|st\.(write|text|code|json|markdown|caption|error|info|warning))\([^)]*api_?key"),
    ("例外内容を画面に表示", r"st\.exception\(|st\.(error|warning)\(f[\"'].*\{[^}]*(exc|err)"),
    ("Markdown として描画（外部由来の内容が流れるか確認）", r"\bst\.(markdown|write_stream)\(|\bst\.write\((?![\"']{2}\))"),
    ("ファイルアップロード", r"\bst\.file_uploader\("),
    ("全セッション共有のキャッシュ", r"@st\.cache_(resource|data)"),
]


def walk(root: Path, skip: set[str]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            yield Path(dirpath) / name


def is_text(path: Path) -> bool:
    name = path.name
    looks_text = (
        path.suffix.lower() in TEXT_SUFFIXES
        or name.startswith(".env")
        or name in {".gitignore", "Dockerfile", "Procfile"}
    )
    try:
        return looks_text and path.stat().st_size <= MAX_BYTES
    except OSError:
        return False


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp932", errors="ignore")


def mask(value: str) -> str:
    return f"{value[:4]}…（{len(value)}文字）"


def naive_ignored(relpath: str, patterns: list[str]) -> str | None:
    """git が使えないとき用の、.gitignore の簡易照合。否定パターンは考慮しない。"""
    parts = relpath.split("/")
    prefixes = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    for raw in patterns:
        pat = raw.rstrip("/")
        anchored = pat.startswith("/")
        pat = pat.lstrip("/")
        candidates = list(prefixes)
        if "/" not in pat and not anchored:
            candidates += parts  # 名前だけのパターンはどの階層にもマッチする
        if any(fnmatch.fnmatch(c, pat) for c in candidates):
            return raw
    return None


def run_git(root: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return res.stdout.strip()


# ---------------------------------------------------------------- 各セクション


def section_streamlit(root: Path) -> int:
    """設定を表示し、実効のポート番号を返す。"""
    print("\n## 1. Streamlit の実効設定")
    sources = [
        ("プロジェクト", root / ".streamlit" / "config.toml"),
        ("グローバル", Path.home() / ".streamlit" / "config.toml"),
    ]
    loaded: list[tuple[str, dict]] = []
    for label, path in sources:
        if not path.exists():
            print(f"- {label}設定: なし（{path}）")
            continue
        try:
            loaded.append((label, tomllib.loads(read_text(path))))
            print(f"- {label}設定: {path}")
        except tomllib.TOMLDecodeError as exc:
            print(f"- {label}設定: {path} は TOML として読めない（{exc}）")

    print("\n| キー | 値 | 設定元 |")
    print("|---|---|---|")
    for key, default in STREAMLIT_KEYS.items():
        section, name = key.split(".")
        found = None
        for label, data in loaded:  # プロジェクト設定がグローバル設定より優先
            if name in data.get(section, {}):
                found = (data[section][name], label)
                break
        if found is None:
            print(f"| {key} | 既定値: {default} | 未設定 |")
        else:
            print(f"| {key} | {found[0]!r} | {found[1]} |")

    env = sorted(k for k in os.environ if k.startswith("STREAMLIT_"))
    if env:
        print("\n- STREAMLIT_* 環境変数（設定より優先される）:")
        for k in env:
            shown = os.environ[k] if re.search(r"ADDRESS|PORT|HEADLESS|CORS|XSRF", k) else "（値は伏せる）"
            print(f"  - {k} = {shown}")
    else:
        print("\n- STREAMLIT_* 環境変数: なし")

    launches = []
    for path in walk(root, SKIP_CODE):
        if path.suffix.lower() in {".bat", ".cmd", ".ps1", ".sh"} or path.name in {"Procfile", "Dockerfile"}:
            for i, line in enumerate(read_text(path).splitlines(), 1):
                if "streamlit" in line and "run" in line:
                    launches.append(f"{path.relative_to(root).as_posix()}:{i}: {line.strip()}")
    print("- 起動コマンド（--server.* 指定は設定ファイルより優先される）:")
    for item in launches or ["なし"]:
        print(f"  - {item}")

    port = next((d["server"]["port"] for _, d in loaded if "port" in d.get("server", {})), 8501)
    return int(os.environ.get("STREAMLIT_SERVER_PORT") or port)


def section_network(port: int) -> None:
    print("\n## 1b. ネットワークから届くか（Windows ファイアウォール・接続中のネットワーク・待ち受け）")
    if os.name != "nt" or shutil.which("powershell") is None:
        print("- Windows 以外、または PowerShell が無いため未確認")
        return
    print(f"- このスクリプトを動かした Python: {sys.executable}")
    print(f"- streamlit コマンド: {shutil.which('streamlit') or '見つからない'}")
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_NETWORK.replace("__PORT__", str(port))],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        data = json.loads(res.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"- 取得できなかった（{type(exc).__name__}）。PowerShell の Get-NetFirewallRule で手動確認すること")
        return

    def as_list(value: object) -> list[dict]:
        items = value if isinstance(value, list) else [value]
        return [x for x in items if isinstance(x, dict)]

    profiles = as_list(data.get("profiles"))
    shown = ", ".join(f"{p.get('name')}（{p.get('category')}）" for p in profiles)
    print(f"- いま接続中のネットワーク: {shown or '取得できず'}（Public＝パブリック。公共 Wi-Fi は通常こちら）")

    listen = as_list(data.get("listen"))
    if listen:
        for item in listen:
            print(f"- ポート {port} で待ち受け中: {item.get('address')}（0.0.0.0 や :: は全インターフェース）")
    else:
        print(f"- ポート {port}: いまは待ち受けていない（アプリ未起動）")

    rules = as_list(data.get("rules"))
    if not rules:
        print("- python / streamlit 向けのファイアウォールルール: なし（ポート指定のルールは対象外）")
        return
    print("\n| ルール名 | 有効 | 方向 | 動作 | プロファイル | プログラム |")
    print("|---|---|---|---|---|---|")
    for r in rules:
        print(
            f"| {r.get('name')} | {r.get('enabled')} | {r.get('direction')} | {r.get('action')} "
            f"| {r.get('profile')} | {r.get('program')} |"
        )


def section_sensitive_files(root: Path) -> None:
    print("\n## 2. 秘密情報・個人データを含むファイルと ignore 状況")
    patterns: list[str] = []
    gitignore = root / ".gitignore"
    if gitignore.exists():
        lines = [l.strip() for l in read_text(gitignore).splitlines()]
        patterns = [l for l in lines if l and not l.startswith("#")]
        if any(p.startswith("!") for p in patterns):
            print("- 注意: .gitignore に否定パターン（!）がある。簡易判定では考慮しない")
    else:
        print("- .gitignore: なし")

    use_git = (root / ".git").exists() and shutil.which("git") is not None
    print(f"- 判定方法: {'git check-ignore' if use_git else '.gitignore の簡易照合（git リポジトリではない）'}")

    for relpath in SENSITIVE_FILES:
        path = root / relpath
        if path.exists():
            info = f"あり（{path.stat().st_size} バイト"
            if relpath.endswith(".json"):
                try:
                    info += f"、{len(json.loads(read_text(path)))} 件"
                except (json.JSONDecodeError, TypeError):
                    info += "、JSON として読めない"
            info += "）"
        else:
            info = "なし"

        if use_git:
            ignored = subprocess.run(["git", "check-ignore", "-q", relpath], cwd=root).returncode == 0
            status = "ignore される" if ignored else "**ignore されない**"
        else:
            hit = naive_ignored(relpath, [p for p in patterns if not p.startswith("!")])
            status = f"ignore される（{hit}）" if hit else "**ignore されない**"
        print(f"- {relpath}: {info} / {status}")

    if use_git:
        tracked = run_git(root, "ls-files", "--", *SENSITIVE_FILES)
        print(f"- git で追跡中: {tracked.replace(chr(10), ', ') if tracked else 'なし'}")
        added = run_git(root, "log", "--all", "--diff-filter=A", "--format=%h %ad", "--date=short", "--", *SENSITIVE_FILES)
        print(f"- 過去にコミットされた記録: {added.replace(chr(10), ', ') if added else 'なし'}")


def section_secrets(root: Path) -> None:
    print("\n## 3. 秘密情報らしき文字列（値は伏せ字）")
    seen: set[tuple[str, int, str]] = set()
    for path in walk(root, SKIP_SECRET):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".claude/skills/") or not is_text(path):
            continue
        for i, line in enumerate(read_text(path).splitlines(), 1):
            for label, rx in SECRET_PATTERNS:
                for m in re.finditer(rx, line):
                    value = m.group(m.lastindex) if m.lastindex else m.group(0)
                    if (rel, i, value) in seen:
                        continue
                    seen.add((rel, i, value))
                    print(f"- {rel}:{i}: {label} {mask(value)}")
    if not seen:
        print("- 検出なし")


def section_code_patterns(root: Path) -> None:
    print("\n## 4. コード上の手がかり（.py のみ。指摘ではなく、読みに行く場所の一覧）")
    hits: dict[str, list[str]] = {label: [] for label, _ in CODE_PATTERNS}
    for path in walk(root, SKIP_CODE):
        if path.suffix != ".py":
            continue
        rel = path.relative_to(root).as_posix()
        for i, line in enumerate(read_text(path).splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for label, rx in CODE_PATTERNS:
                if re.search(rx, line):
                    hits[label].append(f"{rel}:{i}: {stripped[:140]}")
    for label, items in hits.items():
        print(f"\n### {label}（{len(items)} 件）")
        for item in items or ["なし"]:
            print(f"- {item}")


def section_dependencies(root: Path, write_pinned: str | None) -> None:
    print("\n## 5. 依存パッケージ（requirements.txt と実際にインストールされている版）")
    req = root / "requirements.txt"
    if not req.exists():
        print("- requirements.txt なし")
        return
    try:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
    except ImportError:
        SpecifierSet = None  # type: ignore[assignment]

    print("\n| パッケージ | 指定 | インストール済み | 指定を満たすか |")
    print("|---|---|---|---|")
    pinned: list[str] = []
    for raw in read_text(req).splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._\-]*)(\[[^\]]*\])?\s*(.*)$", line)
        if not m:
            continue
        name, spec = m.group(1), m.group(3).split(";")[0].strip()
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            version = None

        if version is None:
            verdict = "未インストール"
        elif not spec:
            verdict = "指定なし"
        elif SpecifierSet is None:
            verdict = "判定不可（packaging なし）"
        else:
            try:
                ok = SpecifierSet(spec).contains(version, prereleases=True)
                verdict = "満たす" if ok else "**満たさない**"
            except InvalidSpecifier:
                verdict = "指定の書式が不正"
        print(f"| {name} | {spec or '-'} | {version or '-'} | {verdict} |")
        if version:
            pinned.append(f"{name}=={version}")

    has_audit = shutil.which("pip-audit") is not None or util.find_spec("pip_audit") is not None
    print(f"\n- pip-audit: {'利用可能' if has_audit else '未インストール'}")

    if write_pinned:
        out = Path(write_pinned)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(pinned) + "\n", encoding="utf-8")
        print(f"- 版を固定した requirements を書き出した: {out}（{', '.join(pinned)}）")


def main() -> int:
    parser = argparse.ArgumentParser(description="セキュリティチェック用の事実収集（読み取り専用）")
    parser.add_argument("--root", default=".", help="プロジェクトのルート（既定: カレントディレクトリ）")
    parser.add_argument(
        "--write-pinned",
        metavar="PATH",
        help="インストール済みの版で固定した requirements を書き出す（pip-audit 用）",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()

    print(f"# セキュリティ事実収集: {root}")
    if not (root / "app.py").exists():
        print("警告: app.py が見つからない。プロジェクト直下で実行しているか確認すること。")

    port = section_streamlit(root)
    section_network(port)
    section_sensitive_files(root)
    section_secrets(root)
    section_code_patterns(root)
    section_dependencies(root, args.write_pinned)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
