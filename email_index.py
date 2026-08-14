import argparse
import sqlite3
import sys
import time as time_module
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path

from actions import determine_email_classification


DEFAULT_DB_PATH = Path(__file__).with_name("email_index.db")
BUSY_TIMEOUT_MS = 5000
PROGRESS_BAR_WIDTH = 40
EMAIL_COLUMNS = [
    "message_id",
    "thread_id",
    "internal_date",
    "date_text",
    "sender",
    "sender_email",
    "subject",
    "snippet",
    "importance_score",
    "importance_level",
    "can_archive",
    "category_label",
    "bank_name",
    "finance_type",
    "security_type",
    "is_unread",
    "in_inbox",
    "indexed_at",
]


def _db_path(db_path=None):
    return Path(db_path) if db_path else DEFAULT_DB_PATH


@contextmanager
def connect_db(db_path=None):
    conn = sqlite3.connect(_db_path(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None):
    with connect_db(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                thread_id TEXT,
                internal_date INTEGER NOT NULL,
                date_text TEXT,
                sender TEXT,
                sender_email TEXT,
                subject TEXT,
                snippet TEXT,
                importance_score INTEGER,
                importance_level TEXT,
                can_archive INTEGER NOT NULL DEFAULT 0,
                category_label TEXT,
                bank_name TEXT,
                finance_type TEXT,
                security_type TEXT,
                is_unread INTEGER NOT NULL DEFAULT 0,
                in_inbox INTEGER NOT NULL DEFAULT 0,
                indexed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_emails_internal_date "
            "ON emails(internal_date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_emails_bank_name "
            "ON emails(bank_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_emails_finance_type "
            "ON emails(finance_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_emails_security_type "
            "ON emails(security_type)"
        )


def _utc_now_text():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_internal_date_ms(value):
    if value is None or value == "":
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)
    if isinstance(value, date):
        dt = datetime.combine(value, time.min, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        if value.isdigit():
            return int(value)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    raise TypeError(f"Unsupported internal_date value: {value!r}")


def _date_start_ms(value):
    if isinstance(value, str):
        value = date.fromisoformat(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)
    dt = datetime.combine(value, time.min, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _date_end_exclusive_ms(value):
    if isinstance(value, str):
        value = date.fromisoformat(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)
    return _date_start_ms(value + timedelta(days=1))


def _recent_start_ms(days):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return int(start.timestamp() * 1000)


def _message_id(mail):
    return mail.get("message_id") or mail.get("id")


def _label_ids(mail):
    return mail.get("label_ids") or mail.get("labelIds") or mail.get("labels") or []


def _bool_from_mail(mail, key, label):
    if key in mail:
        return 1 if mail.get(key) else 0
    return 1 if label in _label_ids(mail) else 0


def _build_row(mail):
    message_id = _message_id(mail)
    if not message_id:
        raise ValueError("mail is missing message_id/id")

    classification = determine_email_classification(mail)
    importance = classification.get("importance") or mail.get("importance") or {}
    sender = mail.get("from", mail.get("sender", ""))
    sender_name, sender_email = parseaddr(sender)

    return {
        "message_id": message_id,
        "thread_id": mail.get("thread_id", mail.get("threadId", "")),
        "internal_date": _to_internal_date_ms(
            mail.get("internal_date", mail.get("internalDate"))
        ),
        "date_text": mail.get("date", mail.get("date_text", "")),
        "sender": sender,
        "sender_email": sender_email or sender_name,
        "subject": mail.get("subject", ""),
        "snippet": mail.get("snippet", ""),
        "importance_score": int(importance.get("score", 50)),
        "importance_level": importance.get("level", ""),
        "can_archive": 1 if importance.get("can_archive") else 0,
        "category_label": classification.get("label"),
        "bank_name": classification.get("bank"),
        "finance_type": classification.get("finance_type"),
        "security_type": classification.get("security_type"),
        "is_unread": _bool_from_mail(mail, "is_unread", "UNREAD"),
        "in_inbox": _bool_from_mail(mail, "in_inbox", "INBOX"),
        "indexed_at": _utc_now_text(),
    }


def upsert_email(mail, db_path=None):
    init_db(db_path)
    row = _build_row(mail)
    with connect_db(db_path) as conn:
        existed = conn.execute(
            "SELECT 1 FROM emails WHERE message_id = ?",
            (row["message_id"],),
        ).fetchone()
        _upsert_row(conn, row)
    return "updated" if existed else "inserted"


def _upsert_row(conn, row):
    columns = EMAIL_COLUMNS
    placeholders = ", ".join("?" for _ in columns)
    update_columns = [col for col in columns if col != "message_id"]
    update_clause = ", ".join(
        f"{col}=excluded.{col}" for col in update_columns
    )
    conn.execute(
        f"""
        INSERT INTO emails ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(message_id) DO UPDATE SET {update_clause}
        """,
        [row[col] for col in columns],
    )


def _format_duration(seconds):
    seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes}分{remaining_seconds}秒"
    return f"{remaining_seconds}秒"


def _progress_line(processed, total, errors=0, width=PROGRESS_BAR_WIDTH):
    if total <= 0:
        percent = 0
        filled = 0
    else:
        percent = int(processed * 100 / total)
        filled = int(width * processed / total)

    bar = "█" * filled + "-" * (width - filled)
    line = f"[{bar}] {percent}% {processed}/{total}"
    if errors:
        line += f" | errors: {errors}"
    return line


def _write_progress(stream, processed, total, errors=0):
    stream.write("\r" + _progress_line(processed, total, errors))
    stream.flush()


def _write_progress_done(stream):
    stream.write("\n")
    stream.flush()


def _print_sync_error(stream, message_id, error):
    stream.write(
        f"\n單封同步失敗：message_id={message_id or '-'} "
        f"error={type(error).__name__}\n"
    )
    stream.flush()


def _fetch_gmail_message_refs(days=90, date_from=None, date_to=None, limit=None):
    if limit == 0:
        from gmail_service import get_gmail_service

        return get_gmail_service(), []

    from gmail_service import _build_index_query, get_gmail_service

    service = get_gmail_service()
    gmail_query = _build_index_query(
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    refs = []
    page_token = None

    while True:
        if limit is not None and len(refs) >= limit:
            break

        request = {
            "userId": "me",
            "q": gmail_query,
            "maxResults": min(500, limit - len(refs)) if limit else 500,
        }
        if page_token:
            request["pageToken"] = page_token

        results = service.users().messages().list(**request).execute()
        refs.extend(results.get("messages", []))

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return service, refs


def _fetch_gmail_message_for_index(service, message_id):
    msg_data = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    ).execute()

    headers = msg_data.get("payload", {}).get("headers", [])
    email_info = {
        "id": message_id,
        "thread_id": msg_data.get("threadId", ""),
        "internal_date": msg_data.get("internalDate"),
        "from": "",
        "subject": "",
        "date": "",
        "snippet": msg_data.get("snippet", ""),
        "label_ids": msg_data.get("labelIds", []),
    }

    for header in headers:
        name = header.get("name")
        if name == "From":
            email_info["from"] = header.get("value", "")
        elif name == "Subject":
            email_info["subject"] = header.get("value", "")
        elif name == "Date":
            email_info["date"] = header.get("value", "")

    return email_info


def _select_email_classification(message_id, db_path=None):
    init_db(db_path)
    with connect_db(db_path) as conn:
        return conn.execute(
            """
            SELECT
                message_id,
                subject,
                category_label,
                bank_name,
                finance_type,
                security_type
            FROM emails
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()


def debug_message(message_id, db_path=None, service=None, stream=None):
    stream = stream or sys.stdout
    if service is None:
        from gmail_service import get_gmail_service

        service = get_gmail_service()

    mail = _fetch_gmail_message_for_index(service, message_id)
    classification = determine_email_classification(mail)
    expected_label = classification.get("label")
    expected_finance_type = classification.get("finance_type")

    stream.write("Before UPSERT:\n")
    stream.write(f"message_id = {message_id}\n")
    stream.write(f"subject = {mail.get('subject', '')}\n")
    stream.write(f"label = {expected_label}\n")
    stream.write(f"bank = {classification.get('bank')}\n")
    stream.write(f"finance_type = {expected_finance_type}\n")
    stream.write(f"security_type = {classification.get('security_type')}\n")

    result = upsert_email(mail, db_path=db_path)
    stored = _select_email_classification(message_id, db_path=db_path)

    stream.write("\nAfter UPSERT:\n")
    if stored:
        stream.write(f"label = {stored['category_label']}\n")
        stream.write(f"bank = {stored['bank_name']}\n")
        stream.write(f"finance_type = {stored['finance_type']}\n")
        stream.write(f"security_type = {stored['security_type']}\n")
    else:
        raise RuntimeError("Message was not found after UPSERT")

    if stored["category_label"] != expected_label:
        raise RuntimeError("Classification persistence mismatch: label")
    if stored["finance_type"] != expected_finance_type:
        raise RuntimeError("Classification persistence mismatch: finance_type")

    return {
        "message_id": message_id,
        "mail": mail,
        "classification": classification,
        "db": dict(stored),
        "upsert_result": result,
    }


def _ref_message_id(ref):
    if isinstance(ref, dict):
        return ref.get("id") or ref.get("message_id")
    return str(ref)


def sync_email_index(
    days=90,
    date_from=None,
    date_to=None,
    limit=None,
    db_path=None,
    fetcher=None,
    progress=False,
    stream=None,
):
    started_at = time_module.monotonic()
    stream = stream or sys.stdout
    init_db(db_path)
    stats = {
        "fetched": 0,
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
        "interrupted": False,
        "elapsed_seconds": 0,
    }

    if progress:
        stream.write("📬 正在建立 Gmail 郵件索引\n")
        if date_from or date_to:
            stream.write(f"期間：{date_from or '-'} 到 {date_to or '-'}\n\n")
        else:
            stream.write(f"期間：最近 {days} 天\n\n")
        stream.write(f"📬 正在查詢最近 {days} 天 Gmail 郵件...\n")
        stream.flush()

    use_gmail_refs = fetcher is None
    service = None
    emails = []

    try:
        if use_gmail_refs:
            service, emails = _fetch_gmail_message_refs(
                days=days,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
        else:
            emails = fetcher(
                days=days,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
    except KeyboardInterrupt:
        stats["interrupted"] = True
        stats["elapsed_seconds"] = time_module.monotonic() - started_at
        return stats

    stats["fetched"] = len(emails)

    if progress:
        stream.write(f"找到 {stats['fetched']} 封\n")
        if stats["fetched"] == 0:
            stream.write("沒有需要同步的郵件。\n")
        else:
            stream.write("開始建立索引...\n\n")
            _write_progress(stream, 0, stats["fetched"], 0)

    with connect_db(db_path) as conn:
        for item in emails:
            message_id = _ref_message_id(item)
            try:
                if use_gmail_refs:
                    mail = _fetch_gmail_message_for_index(service, message_id)
                else:
                    mail = item
                    message_id = _message_id(mail)

                row = _build_row(mail)
                existed = conn.execute(
                    "SELECT 1 FROM emails WHERE message_id = ?",
                    (row["message_id"],),
                ).fetchone()
                _upsert_row(conn, row)
                if existed:
                    stats["updated"] += 1
                else:
                    stats["inserted"] += 1
            except KeyboardInterrupt:
                stats["interrupted"] = True
                break
            except Exception as error:
                stats["errors"] += 1
                if progress:
                    _print_sync_error(stream, message_id, error)
            finally:
                if not stats["interrupted"]:
                    stats["processed"] += 1
                    if progress and stats["fetched"] > 0:
                        _write_progress(
                            stream,
                            stats["processed"],
                            stats["fetched"],
                            stats["errors"],
                        )

    if progress and stats["fetched"] > 0:
        _write_progress_done(stream)

    stats["elapsed_seconds"] = time_module.monotonic() - started_at
    return stats


def _query_emails(where_parts=None, params=None, limit=20, db_path=None):
    init_db(db_path)
    where_parts = where_parts or []
    params = params or []
    sql = "SELECT * FROM emails"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY internal_date DESC"
    if limit:
        sql += " LIMIT ?"
        params = [*params, limit]

    with connect_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row):
    internal_date = row["internal_date"]
    dt = datetime.fromtimestamp(internal_date / 1000, timezone.utc)
    return {
        "message_id": row["message_id"],
        "thread_id": row["thread_id"],
        "date": dt.isoformat(timespec="seconds"),
        "date_text": row["date_text"],
        "sender": row["sender"],
        "sender_email": row["sender_email"],
        "subject": row["subject"],
        "snippet": row["snippet"],
        "importance_score": row["importance_score"],
        "importance_level": row["importance_level"],
        "can_archive": bool(row["can_archive"]),
        "category_label": row["category_label"],
        "bank_name": row["bank_name"],
        "finance_type": row["finance_type"],
        "security_type": row["security_type"],
        "is_unread": bool(row["is_unread"]),
        "in_inbox": bool(row["in_inbox"]),
        "indexed_at": row["indexed_at"],
    }


def _date_filters(date_from=None, date_to=None):
    where = []
    params = []
    if date_from:
        where.append("internal_date >= ?")
        params.append(_date_start_ms(date_from))
    if date_to:
        where.append("internal_date < ?")
        params.append(_date_end_exclusive_ms(date_to))
    return where, params


def get_recent_emails(limit=20, days=7, db_path=None):
    return _query_emails(
        ["internal_date >= ?"],
        [_recent_start_ms(days)],
        limit=limit,
        db_path=db_path,
    )


def get_emails(date_from=None, date_to=None, limit=20, db_path=None):
    where, params = _date_filters(date_from, date_to)
    return _query_emails(where, params, limit=limit, db_path=db_path)


def get_important_emails(min_score=80, limit=20, days=None, db_path=None):
    where = ["importance_score >= ?"]
    params = [min_score]
    if days:
        where.append("internal_date >= ?")
        params.append(_recent_start_ms(days))
    return _query_emails(where, params, limit=limit, db_path=db_path)


def get_bank_emails(bank_name, limit=20, days=None, db_path=None):
    where = ["bank_name = ?"]
    params = [bank_name]
    if days:
        where.append("internal_date >= ?")
        params.append(_recent_start_ms(days))
    return _query_emails(where, params, limit=limit, db_path=db_path)


def get_bank_statements(
    bank_name=None,
    date_from=None,
    date_to=None,
    limit=20,
    db_path=None,
):
    where, params = _date_filters(date_from, date_to)
    where.append("finance_type = ?")
    params.append("帳單")
    if bank_name:
        where.append("bank_name = ?")
        params.append(bank_name)
    return _query_emails(where, params, limit=limit, db_path=db_path)


def get_login_records(
    bank_name=None,
    date_from=None,
    date_to=None,
    bank_only=False,
    limit=20,
    db_path=None,
):
    where, params = _date_filters(date_from, date_to)
    where.append(
        "(finance_type = ? OR security_type = ? OR category_label = ?)"
    )
    params.extend(["登入紀錄", "登入紀錄", "AI/安全/登入紀錄"])
    if bank_name:
        where.append("bank_name = ?")
        params.append(bank_name)
    if bank_only:
        where.append("bank_name IS NOT NULL")
    return _query_emails(where, params, limit=limit, db_path=db_path)


def get_security_emails(
    date_from=None,
    date_to=None,
    limit=20,
    db_path=None,
):
    where, params = _date_filters(date_from, date_to)
    where.append("(security_type IS NOT NULL OR category_label LIKE ?)")
    params.append("AI/安全/%")
    return _query_emails(where, params, limit=limit, db_path=db_path)


def get_stats(db_path=None):
    init_db(db_path)
    with connect_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN bank_name IS NOT NULL THEN 1 ELSE 0 END) AS finance,
                SUM(CASE WHEN finance_type = '帳單' THEN 1 ELSE 0 END) AS bills,
                SUM(CASE
                    WHEN finance_type = '登入紀錄'
                        OR security_type = '登入紀錄'
                        OR category_label = 'AI/安全/登入紀錄'
                    THEN 1 ELSE 0 END
                ) AS login_records,
                SUM(CASE
                    WHEN security_type IS NOT NULL
                        OR category_label LIKE 'AI/安全/%'
                    THEN 1 ELSE 0 END
                ) AS security,
                SUM(CASE WHEN importance_score >= 80 THEN 1 ELSE 0 END)
                    AS important,
                MIN(internal_date) AS oldest,
                MAX(internal_date) AS newest
            FROM emails
            """
        ).fetchone()

    stats = dict(row)
    for key in ["finance", "bills", "login_records", "security", "important"]:
        stats[key] = stats[key] or 0
    stats["oldest_date"] = _ms_to_text(stats.pop("oldest"))
    stats["newest_date"] = _ms_to_text(stats.pop("newest"))
    return stats


def _ms_to_text(value):
    if value is None:
        return "-"
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(
        timespec="seconds"
    )


def _print_sync_stats(stats):
    print("同步完成")
    print(f"讀取：{stats['fetched']}")
    print(f"新增：{stats['inserted']}")
    print(f"更新：{stats['updated']}")
    print(f"錯誤：{stats['errors']}")


def _print_db_stats(stats):
    print("Email Index")
    print()
    print(f"郵件總數：{stats['total']}")
    print(f"金融：{stats['finance']}")
    print(f"帳單：{stats['bills']}")
    print(f"登入紀錄：{stats['login_records']}")
    print(f"安全通知：{stats['security']}")
    print(f"高重要：{stats['important']}")
    print()
    print(f"最早索引日期：{stats['oldest_date']}")
    print(f"最新索引日期：{stats['newest_date']}")


def _print_sync_summary(stats):
    if stats.get("interrupted"):
        print("⚠️ 使用者中止同步")
        print()
        print(f"目前進度：{stats.get('processed', 0)}/{stats.get('fetched', 0)}")
        print(f"已新增：{stats['inserted']}")
        print(f"已更新：{stats['updated']}")
        print(f"錯誤：{stats['errors']}")
    else:
        print("✅ 同步完成")
        print(f"讀取：{stats['fetched']}")
        print(f"新增：{stats['inserted']}")
        print(f"更新：{stats['updated']}")
        print(f"錯誤：{stats['errors']}")

    print(f"耗時：{_format_duration(stats.get('elapsed_seconds', 0))}")


def main():
    parser = argparse.ArgumentParser(description="Local Gmail metadata index")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--debug-message")
    args = parser.parse_args()

    if args.debug_message:
        debug_message(args.debug_message, db_path=args.db)
        return

    if args.sync:
        stats = sync_email_index(
            days=args.days,
            limit=args.limit,
            db_path=args.db,
            progress=True,
        )
        _print_sync_summary(stats)

    if args.stats or not args.sync:
        _print_db_stats(get_stats(args.db))


if __name__ == "__main__":
    main()
