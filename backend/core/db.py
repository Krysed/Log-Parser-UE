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
def insert_issue(message_hash, log_entry_id, message, timestamp, category, severity, line_number=None, status="open"):
    cursor.execute("SELECT id FROM issues WHERE message_hash = %s", (message_hash,))
    existing = cursor.fetchone()
    if existing:
        return existing["id"], False

    cursor.execute("""
        INSERT INTO issues (message_hash, log_entry_id, message, timestamp, category, severity, line_number, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (message_hash, log_entry_id, message, timestamp, category, severity, line_number, status))
    new_id = cursor.fetchone()["id"]
    return new_id, True

def insert_traceback(event_id, message, line_number, hash):
    cursor.execute("SELECT id FROM error_traceback WHERE hash = %s", (hash,))
    existing = cursor.fetchone()
    if existing:
        return 
    cursor.execute("""
        INSERT INTO error_traceback (issue_id, message, line_number, hash)
        VALUES (%s, %s, %s, %s)
    """, (event_id, message, line_number, hash))

def insert_parsed_logs_to_db(log_entries):
    for entry in log_entries:
        try:
            traceback_exists = entry.get("traceback") and len(entry["traceback"]) > 0
            severity = entry.get("severity", "warning")
            
            issue_id, is_new_issue = insert_issue(
                message_hash=entry["message_hash"],
                log_entry_id=entry["log_entry_id"],
                message=entry["message"],
                timestamp=entry["timestamp"],
                category=entry["category"],
                severity=severity,
                line_number=entry.get("line_number")
            )

            if is_new_issue and traceback_exists:
                for i, tb_message in enumerate(entry["traceback"]):
                    insert_traceback(
                        event_id=issue_id,
                        message=tb_message["message"] if isinstance(tb_message, dict) else str(tb_message),
                        line_number=entry.get("line_number", 0) + i,
                        hash=get_log_hash(tb_message["message"])
                    )
                    logger.debug(f"Inserted traceback line for issue_id={issue_id}")

        except Exception as e:
            logger.error(f"Caught exception: {e}\nDB insert failed at line {entry.get('line_number')}")
            db.rollback()

    db.commit()

def delete_specified_issue(issue_id):
    try:        
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
                "log_entry_id": row.get("log_entry_id"),
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

def get_issue_by_id(issue_id: str):
    try:
        cursor.execute("SELECT * FROM issues WHERE id = %s;", (issue_id,))
        issue = cursor.fetchone()
        if not issue:
            return None
        return {
            "id": issue.get("id"),
            "log_entry_id": issue.get("log_entry_id"),
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
