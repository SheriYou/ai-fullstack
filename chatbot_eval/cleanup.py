"""Clean eval-only chatbot rows. The guard refuses non-eval prefixes."""

from __future__ import annotations

import argparse

from . import harness

TABLES = [
    "wa_chat_message",
    "wa_message_trace_log",
    "wa_agent_step",
    "wa_agent_session",
    "wa_tool_call_log",
    "wa_conversation",
]
SAFE_PREFIX = "eval"


def _guard(prefix: str) -> None:
    if not prefix.startswith(SAFE_PREFIX):
        raise SystemExit(f"refuse cleanup: prefix must start with {SAFE_PREFIX!r}, got {prefix!r}")


def count(prefix: str) -> dict[str, int]:
    _guard(prefix)
    like = harness.sql_escape(prefix)
    out = {}
    for table in TABLES:
        rows = harness.mysql_rows("SELECT COUNT(*) FROM %s WHERE whatsapp_id LIKE '%s%%'" % (table, like))
        out[table] = int(rows[0][0]) if rows else 0
    return out


def purge(prefix: str, quiet: bool = False) -> dict[str, int]:
    _guard(prefix)
    like = harness.sql_escape(prefix)
    deleted = {}
    for table in TABLES:
        rows = harness.mysql_rows("SELECT COUNT(*) FROM %s WHERE whatsapp_id LIKE '%s%%'" % (table, like))
        n_rows = int(rows[0][0]) if rows else 0
        if n_rows:
            harness.mysql("DELETE FROM %s WHERE whatsapp_id LIKE '%s%%'" % (table, like))
        deleted[table] = n_rows
    if not quiet:
        total = sum(deleted.values())
        print(f"已清理 {prefix!r}* 测试数据：{total} 行")
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean eval* chatbot test data.")
    parser.add_argument("--prefix", default=SAFE_PREFIX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        current = count(args.prefix)
        print(f"[dry-run] {args.prefix!r}* 现有测试行：")
        for table, n_rows in current.items():
            print(f"  {table}: {n_rows}")
        print(f"  合计: {sum(current.values())}")
    else:
        purge(args.prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

