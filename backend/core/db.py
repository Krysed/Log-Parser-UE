from .logger import logger
from .parser import get_log_hash
import psycopg2
import psycopg2.extras
import os


def get_db_connection():
    connection = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "logs_db"),
        user=os.getenv("POSTGRES_USER", "user"),
        password=os.getenv("POSTGRES_PASSWORD", "pass"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return connection

# db operations
def insert_issue(issue_hash, message, timestamp, category, status="open"):
    cursor.execute("SELECT id FROM issues WHERE hash = %s", (issue_hash,))
    existing = cursor.fetchone()
    if existing:
        return existing["id"]

    cursor.execute("""
        INSERT INTO issues (hash, message, timestamp, category, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (issue_hash, message, timestamp, category, status))
    new_id = cursor.fetchone()["id"]
    return new_id

def insert_event(event_hash, message, timestamp, category, type_, issue_id=None):
    cursor.execute("SELECT id FROM events WHERE hash = %s", (event_hash,))
    existing = cursor.fetchone()
    if existing:
        return existing["id"], False

    cursor.execute("""
        INSERT INTO events (hash, message, timestamp, category, type, issue_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (event_hash, message, timestamp, category, type_, issue_id))

    cursor.execute("SELECT id FROM events WHERE hash = %s", (event_hash,))
    row = cursor.fetchone()
    return row["id"], True if row else (None, False)


def insert_traceback(event_id, message, line_number, hash):
    cursor.execute("SELECT id FROM events WHERE hash = %s", (hash,))
    existing = cursor.fetchone()
    if existing:
        return 
    cursor.execute("""
        INSERT INTO error_traceback (error_id, message, line_number, hash)
        VALUES (%s, %s, %s, %s)
    """, (event_id, message, line_number, hash))

def insert_parsed_logs_to_db(log_entries):
    for entry in log_entries:
        try:
            traceback_exists = entry.get("traceback") and len(entry["traceback"]) > 0
            is_error_type = entry.get("type") == "error"

            if is_error_type or traceback_exists:
                insert_issue(
                    issue_hash=entry["issue_hash"],
                    message=entry["message"],
                    timestamp=entry["timestamp"],
                    category=entry["category"],
                    status="open"
                )

                cursor.execute("SELECT id FROM issues WHERE hash = %s", (entry["issue_hash"],))
                issue_row = cursor.fetchone()
                issue_id = issue_row["id"] if issue_row else None

                event_id, is_new_event = insert_event(
                    event_hash=entry["event_hash"],
                    message=entry["message"],
                    timestamp=entry["timestamp"],
                    category=entry["category"],
                    type_="error",
                    issue_id=issue_id
                )

                if is_new_event and event_id:
                    for i, tb_message in enumerate(entry.get("traceback", [])):
                        insert_traceback(
                            event_id=event_id,
                            message=tb_message["message"] if isinstance(tb_message, dict) else str(tb_message),
                            line_number=entry.get("line_number", None) + i if entry.get("line_number") is not None else None,
                            hash=get_log_hash(tb_message["message"])
                        )
                        logger.debug(f"Inserted traceback line for error_id={event_id}")

            elif entry["type"] == "warning":
                insert_event(
                    event_hash=entry["hash"],
                    message=entry["message"],
                    timestamp=entry["timestamp"],
                    category=entry["category"],
                    type_="warning",
                    issue_id=None
                )

        except Exception as e:
            logger.error(f"Caught exception: {e}\nDB insert failed at line {entry.get('line_number')}")
            db.rollback()
            continue

    db.commit()

def delete_specified_issue(issue_id):
    try:
        cursor.execute("DELETE FROM events WHERE issue_id = %s;", (issue_id,))
        
        cursor.execute("DELETE FROM issues WHERE id = %s RETURNING id;", (issue_id,))
        deleted = cursor.fetchone()
        db.commit()

        return deleted is not None
    except Exception as e:
        db.rollback()
        logger.error(f"DB error deleting issue {issue_id}: {e}")
        raise

def update_issue_status(issue_id, new_status):
    if new_status not in ["open", "closed"]:
        raise ValueError("Invalid status")

    try:
        cursor.execute(
            "UPDATE issues SET status = %s WHERE id = %s RETURNING id;",
            (new_status, issue_id)
        )
        updated = cursor.fetchone()
        db.commit()
        return updated is not None
    except Exception as e:
        db.rollback()
        logger.error(f"DB error updating issue status: {e}")
        raise

def get_issues(status=None):
    if status and status not in ["open", "closed"]:
        raise ValueError("Invalid status filter")
    try:
        if status:
            cursor.execute("SELECT * FROM issues WHERE status = %s;", (status,))
        else:
            cursor.execute("SELECT * FROM issues;")
        rows = cursor.fetchall()
        return [
            {
                "id": row.get("id"),
                "message": row.get("message"),
                "category": row.get("category", "unknown"),
                "timestamp": row.get("timestamp", None),
                "status": row.get("status", "open"),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"DB error fetching issues: {e}")
        raise

def get_issue_by_id(issue_id: int):
    try:
        cursor.execute("SELECT * FROM issues WHERE id = %s;", (issue_id,))
        issue = cursor.fetchone()
        if not issue:
            return None
        return {
            "id": issue.get("id"),
            "message": issue.get("message"),
            "category": issue.get("category", "unknown"),
            "timestamp": issue.get("timestamp", None),
            "status": issue.get("status", "open"),
        }
    except Exception as e:
        logger.error(f"DB error fetching issue by ID {issue_id}: {e}")
        raise

db = get_db_connection()
cursor = db.cursor()
