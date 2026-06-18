"""Project 15: 乌托邦计划 — Local chat database extraction.

Supported platforms (Phase 1: file-based, Phase 2: direct DB):

  WeChat (Windows):
    Path: %USERPROFILE%/Documents/WeChat Files/<wxid>/Msg/
    DB:   MSG*.db (SQLite + custom XOR/RC4 encryption)
    Media: FileStorage/  (images, voice, video)
    Decrypt: via known key derivation from wxid + phone IMEI hash

  QQ (Windows):
    Path: %USERPROFILE%/Documents/Tencent Files/<qq>/Msg3.0/
    DB:   msg3.0.db (SQLite + AES encryption)
    Decrypt: 16-byte key from QQ key derivation

  Feishu / Lark (Windows/Mac):
    Path: %LOCALAPPDATA%/Lark/packages/<appid>/data/
    Export: Built-in export to .csv / .json  (no decryption needed)
    API:    OAuth via app.feishu.cn

  WeCom / 企业微信 (Windows):
    Path: %USERPROFILE%/Documents/WXWork/<corpid>/Data/
    DB:   similar to WeChat
    Export: admin can export via management console

Strategy:
  1. Try reading from known local paths if available
  2. Fall back to user-provided export files
  3. Decrypt with platform-specific algorithms
  4. Normalize to [timestamp, sender, content, chat_type] format
"""

import json
import os
import platform
import sqlite3
import struct
from datetime import datetime
from typing import Any


# ═══════════════════════════════════════════════════════════
# Platform detection and known paths
# ═══════════════════════════════════════════════════════════

def _system() -> str:
    return platform.system()  # "Windows" / "Darwin" / "Linux"


def _find_wechat_paths() -> list[str]:
    """Find WeChat Msg directories on local machine."""
    system = _system()
    candidates = []

    if system == "Windows":
        home = os.environ.get("USERPROFILE", "C:/Users/Default")
        wechat_root = os.path.join(home, "Documents", "WeChat Files")
        if os.path.isdir(wechat_root):
            for d in os.listdir(wechat_root):
                msg_dir = os.path.join(wechat_root, d, "Msg")
                if os.path.isdir(msg_dir):
                    candidates.append(msg_dir)
    elif system == "Darwin":
        home = os.environ.get("HOME", "/tmp")
        wechat_root = os.path.join(home, "Library", "Containers",
                                   "com.tencent.xinWeChat", "Data", "Library",
                                   "Application Support",
                                   "com.tencent.xinWeChat", "2.0b4.0.9")
        for version_dir in os.listdir(wechat_root) if os.path.isdir(wechat_root) else []:
            msg_dir = os.path.join(wechat_root, version_dir, "Message")
            if os.path.isdir(msg_dir):
                candidates.append(msg_dir)

    return candidates


def _find_qq_paths() -> list[str]:
    """Find QQ Msg3.0 directories."""
    system = _system()
    candidates = []

    if system == "Windows":
        home = os.environ.get("USERPROFILE", "C:/Users/Default")
        qq_root = os.path.join(home, "Documents", "Tencent Files")
        if os.path.isdir(qq_root):
            for d in os.listdir(qq_root):
                db_path = os.path.join(qq_root, d, "Msg3.0", "msg3.0.db")
                if os.path.isfile(db_path):
                    candidates.append(db_path)

    return candidates


def _find_feishu_paths() -> list[str]:
    """Find Feishu/Lark data directories."""
    candidates = []
    system = _system()

    if system == "Windows":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        lark_root = os.path.join(localappdata, "Lark", "packages")
    elif system == "Darwin":
        home = os.environ.get("HOME", "/tmp")
        lark_root = os.path.join(home, "Library", "Application Support", "Lark")
    else:
        return candidates

    if os.path.isdir(lark_root):
        for d in os.listdir(lark_root):
            data_dir = os.path.join(lark_root, d, "data")
            if os.path.isdir(data_dir):
                candidates.append(data_dir)

    return candidates


def _find_wecom_paths() -> list[str]:
    """Find WeCom/WXWork data directories."""
    candidates = []
    system = _system()

    if system == "Windows":
        home = os.environ.get("USERPROFILE", "C:/Users/Default")
        wxwork_root = os.path.join(home, "Documents", "WXWork")
        if os.path.isdir(wxwork_root):
            for d in os.listdir(wxwork_root):
                data_dir = os.path.join(wxwork_root, d, "Data")
                if os.path.isdir(data_dir):
                    candidates.append(data_dir)

    return candidates


# ═══════════════════════════════════════════════════════════
# WeChat Database Decryption
# ═══════════════════════════════════════════════════════════

# WeChat uses a custom XOR-based encryption on SQLite databases.
# The key is derived from: MD5(wxid + 0x0000 + IMEI_hash)[:7]
# This is a simplified mode — real decryption may need pysqlcipher or
# the WeChatMsg project's approach.

# For now we implement a "try known techniques" approach:
# 1. If DB is unencrypted SQLite → read directly
# 2. If DB is encrypted → require user to provide key or pre-decrypted file
# 3. Accept exported .txt files from third-party tools like WeChatMsg


def try_read_sqlite(db_path: str, key: str | None = None) -> list[dict]:
    """Attempt to read a SQLite database (WeChat/QQ format).

    If key is provided, attempt decryption.
    Returns normalized messages or empty list on failure.
    """
    messages = []

    # Try direct SQLite first
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()

        # WeChat MSG format (simplified schema)
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        if "MSG" in tables:
            rows = cur.execute(
                "SELECT CreateTime, StrTalker, StrContent, Type, IsSender "
                "FROM MSG ORDER BY CreateTime LIMIT 100000"
            ).fetchall()
            for row in rows:
                ts, talker, content, msg_type, is_sender = row
                messages.append({
                    "timestamp": _wechat_ts(ts),
                    "sender": "self" if is_sender else talker,
                    "content": content or "",
                    "msg_type": msg_type,
                    "platform": "wechat",
                })

        conn.close()
        return messages
    except Exception:
        pass

    # Try with key (for encrypted QQ/WeChat DBs)
    if key:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            # PRAGMA key is used by SQLCipher
            conn.execute(f"PRAGMA key='{key}'")
            conn.execute("SELECT count(*) FROM sqlite_master")
            # ... same reading logic as above
            conn.close()
        except Exception:
            pass

    return messages


def _wechat_ts(ts_val) -> str:
    """Convert WeChat CreateTime to ISO string."""
    try:
        ts = int(ts_val)
        if ts > 1e12:  # milliseconds
            ts = ts // 1000
        return datetime.fromtimestamp(ts).isoformat()
    except (ValueError, OSError):
        return datetime.now().isoformat()[:19]


# ═══════════════════════════════════════════════════════════
# Universal chat export format parser
# ═══════════════════════════════════════════════════════════

def parse_wechat_txt(filepath: str) -> list[dict]:
    """Parse WeChat PC exported .txt chat log.

    Format (Chinese WeChat):
        2024-01-15 14:32:01 张三
        这条消息内容
        2024-01-15 14:32:05 李四
        回复内容
    """
    messages = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return messages

    import re
    header_pat = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}) (.+)$')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = header_pat.match(line)
        if match:
            ts, sender = match.groups()
            # Next line(s) are content
            content_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if header_pat.match(next_line):
                    break
                if next_line:
                    content_lines.append(next_line)
                i += 1
            messages.append({
                "timestamp": ts.replace(" ", "T"),
                "sender": sender,
                "content": "\n".join(content_lines),
                "platform": "wechat",
            })
        else:
            i += 1

    return messages


def parse_feishu_json(filepath: str) -> list[dict]:
    """Parse Feishu exported .json chat file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    messages = []
    items = data if isinstance(data, list) else data.get("messages", [])

    for item in items:
        body = item.get("body", {})
        content = body.get("content", {})
        text = content.get("text", "") if isinstance(content, dict) else str(content)

        messages.append({
            "timestamp": item.get("create_time", ""),
            "sender": item.get("sender", {}).get("name", "") if isinstance(item.get("sender"), dict) else "",
            "content": text,
            "platform": "feishu",
        })

    return messages


def parse_feishu_csv(filepath: str) -> list[dict]:
    """Parse Feishu exported .csv chat file."""
    import csv
    messages = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                messages.append({
                    "timestamp": row.get("timestamp", row.get("时间", "")),
                    "sender": row.get("sender_name", row.get("发送者", "")),
                    "content": row.get("content", row.get("内容", "")),
                    "platform": "feishu",
                })
    except (FileNotFoundError, UnicodeDecodeError):
        pass
    return messages


# ═══════════════════════════════════════════════════════════
# Auto-discovery + extraction
# ═══════════════════════════════════════════════════════════

def discover_chat_sources() -> list[dict]:
    """Auto-discover local chat databases and export files.

    Returns list of {platform, type, path, message_count}
    """
    sources = []

    # WeChat DBs
    for path in _find_wechat_paths():
        for f in os.listdir(path):
            if f.startswith("MSG") and f.endswith(".db"):
                full = os.path.join(path, f)
                sources.append({"platform": "wechat", "type": "db", "path": full})

    # QQ DBs
    for path in _find_qq_paths():
        sources.append({"platform": "qq", "type": "db", "path": path})

    # Feishu/Lark
    for path in _find_feishu_paths():
        sources.append({"platform": "feishu", "type": "directory", "path": path})

    # WeCom
    for path in _find_wecom_paths():
        for f in os.listdir(path):
            if f.endswith(".db"):
                full = os.path.join(path, f)
                sources.append({"platform": "wecom", "type": "db", "path": full})

    return sources


def extract_messages(sources: list[dict], db_key: str | None = None) -> dict:
    """Extract all messages from discovered or user-provided sources.

    Returns {platform: [messages], total_count: N}
    """
    all_messages: dict[str, list[dict]] = {
        "wechat": [], "qq": [], "feishu": [], "wecom": [], "other": [],
    }

    for src in sources:
        platform = src["platform"]
        path = src["path"]
        src_type = src.get("type", "file")

        msgs = []

        if src_type == "db" and path.endswith(".db"):
            msgs = try_read_sqlite(path, db_key)
        elif src_type == "db":
            msgs = try_read_sqlite(path, db_key)
        elif path.endswith(".txt"):
            msgs = parse_wechat_txt(path)
        elif path.endswith(".json"):
            msgs = parse_feishu_json(path)
        elif path.endswith(".csv"):
            msgs = parse_feishu_csv(path)

        if msgs:
            all_messages[platform].extend(msgs)
        elif src_type == "directory":
            # Scan directory for export files
            for f in os.listdir(path):
                fp = os.path.join(path, f)
                if f.endswith(".txt"):
                    all_messages[platform].extend(parse_wechat_txt(fp))
                elif f.endswith(".json"):
                    all_messages[platform].extend(parse_feishu_json(fp))
                elif f.endswith(".csv"):
                    all_messages[platform].extend(parse_feishu_csv(fp))

    total = sum(len(v) for v in all_messages.values())
    return {"by_platform": all_messages, "total_count": total}
