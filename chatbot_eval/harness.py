"""Webhook injection and MySQL polling primitives for deterministic eval."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "profiles" / "hot70"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_dotenv() -> None:
    project = Path(os.environ.get("AHT_PROJECT_ROOT", DEFAULT_PROJECT))
    environment = os.environ.get("TEST_ENV", "").strip().lower()
    candidates = [
        REPO_ROOT / (f".env.{environment}" if environment else ".env"),
        project / (f"config.{environment}.env" if environment else "config.env"),
        project / (f".env.{environment}" if environment else ".env"),
    ]
    for path in candidates:
        _load_env_file(path)


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def _normalize_bot_url(raw_url: str) -> str:
    url = (raw_url or "").strip().rstrip("/")
    if not url:
        return "http://127.0.0.1:8081"
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4] or ""
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


BOT_URL = _normalize_bot_url(_env("BOT_URL") or _env("BOT_TEST_API_URL", "http://127.0.0.1:8081"))
CHANNEL = _env("BOT_CHANNEL_KEY", "ch_wa_01")
MYSQL_C = _env("MYSQL_CONTAINER", "cpm-bot-mysql")
MYSQL_U = _env("MYSQL_USER", "whatsapp")
MYSQL_P = _env("MYSQL_PASSWORD", "whatsapp123")
MYSQL_DB = _env("MYSQL_DB", "whatsapp_bot")
MYSQL_MODE = _env("MYSQL_MODE", "docker").lower()
MYSQL_HOST = _env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(_env("MYSQL_PORT", "3306"))


def now_ms() -> int:
    return int(time.time() * 1000)


def post_json(url: str, body: dict, headers: dict | None = None, timeout: int = 30) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def bot_message_url() -> str:
    if not CHANNEL:
        raise RuntimeError("BOT_CHANNEL_KEY is empty")
    return f"{BOT_URL}/api/webhook/channels/{CHANNEL}/messages"


def send(wa_id: str, text: str, msg_id: str, sender_name: str = "Eval") -> dict:
    body = {
        "message_id": msg_id,
        "whatsapp_id": wa_id,
        "direction": "inbound",
        "message_type": "text",
        "content": text,
        "sender_name": sender_name,
        "timestamp": now_ms(),
    }
    return post_json(bot_message_url(), body)


def mysql(sql: str) -> str:
    if MYSQL_MODE == "direct":
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("MYSQL_MODE=direct requires pymysql; install project dependencies first") from exc
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_U,
            password=MYSQL_P,
            database=MYSQL_DB,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=10,
            read_timeout=25,
            write_timeout=25,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
            return "\n".join(
                "\t".join("" if value is None else str(value) for value in row)
                for row in rows
            ).strip()
        finally:
            connection.close()

    if MYSQL_MODE != "docker":
        raise RuntimeError("MYSQL_MODE only supports docker or direct")
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                MYSQL_C,
                "mysql",
                "--default-character-set=utf8mb4",
                f"-u{MYSQL_U}",
                f"-p{MYSQL_P}",
                "-D",
                MYSQL_DB,
                "-N",
                "-e",
                sql,
            ],
            capture_output=True,
            timeout=25,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("MYSQL_MODE=docker requires Docker CLI; set MYSQL_MODE=direct for UAT DB access") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"docker mysql failed: {detail}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def mysql_rows(sql: str) -> list[list[str]]:
    raw = mysql(sql)
    if not raw:
        return []
    return [line.split("\t") for line in raw.split("\n")]


def sql_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def wait_reply(wa_id: str, after_ms: int, timeout_s: int = 120, poll_s: int = 3, msg_id: str | None = None) -> str | None:
    wa = sql_escape(wa_id)
    cutoff_ms = after_ms
    if msg_id:
        inbound = mysql_rows(
            "SELECT `timestamp` FROM wa_chat_message "
            "WHERE whatsapp_id='%s' AND direction='inbound' "
            "AND message_id LIKE '%%%s%%' ORDER BY id DESC LIMIT 1"
            % (wa, sql_escape(msg_id))
        )
        if inbound and inbound[0] and inbound[0][0]:
            try:
                cutoff_ms = int(inbound[0][0])
            except (TypeError, ValueError):
                pass

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = mysql(
            "SELECT content FROM wa_chat_message WHERE whatsapp_id='%s' "
            "AND direction='outbound' AND `timestamp` > %d "
            "ORDER BY `timestamp` ASC LIMIT 1" % (wa, cutoff_ms)
        )
        if row:
            return row
        time.sleep(poll_s)
    return None


def backend_healthy() -> bool:
    try:
        request = urllib.request.Request(f"{BOT_URL}/actuator/health")
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False
