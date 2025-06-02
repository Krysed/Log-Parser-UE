from .logger import logger
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
    cursor.execute("""
        INSERT INTO issues (hash, message, timestamp, category, status)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (hash) DO NOTHING;
    """, (issue_hash, message, timestamp, category, status))

def insert_event(event_hash, message, timestamp, category, type_):
    issue_id = None
    if type_ == "error":
        cursor.execute("SELECT id FROM issues WHERE hash = %s", (event_hash,))
        row = cursor.fetchone()
        if row:
            issue_id = row["id"]

    cursor.execute("""
        INSERT INTO events (hash, message, timestamp, category, type, issue_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (hash) DO NOTHING
        RETURNING id
    """, (event_hash, message, timestamp, category, type_, issue_id))
    row = cursor.fetchone()

    if row:
        return row["id"], True
    else:
        cursor.execute("SELECT id FROM events WHERE hash = %s", (event_hash,))
        row = cursor.fetchone()
        return row["id"] if row else None, False


def insert_traceback(event_id, message, line_number):
    cursor.execute("""
        INSERT INTO error_traceback (error_id, message, line_number)
        VALUES (%s, %s, %s)
    """, (event_id, message, line_number))

def get_or_create_event(event_hash, message, timestamp, category, type_):
    existing = db.query("SELECT id FROM events WHERE event_hash = ?", (event_hash,))
    if existing:
        return existing[0]["id"]
    return insert_event(event_hash, message, timestamp, category, type_)

def insert_parsed_logs_to_db(log_entries):
    for entry in log_entries:
        try:
            traceback_exists = entry.get("traceback") and len(entry["traceback"]) > 0
            is_error_type = entry.get("type") == "error"

            if is_error_type or traceback_exists:
            # if entry["type"] == "error" or entry.get("traceback", []):
                insert_issue(
                    issue_hash=entry["issue_hash"],
                    message=entry["message"],
                    timestamp=entry["timestamp"],
                    category=entry["category"],
                    status="open"
                )

                event_id = insert_event(
                    event_hash=entry["event_hash"],
                    message=entry["message"],
                    timestamp=entry["timestamp"],
                    category=entry["category"],
                    type_="error"
                )
                # TODO: insertując 2 razy jest w bazie jako error ale! jest pomieszane indexowanie. 

                if not event_id:
                    logger.error(f"Failed to insert or fetch event for error log at line {entry.get('line_number')}, skipping traceback insert.")
                else:
                    for i, tb_message in enumerate(entry.get("traceback", [])):
                        insert_traceback(
                            event_id=event_id,
                            message=tb_message["message"] if isinstance(tb_message, dict) else str(tb_message),
                            line_number=entry.get("line_number", None) + i if entry.get("line_number") is not None else None
                        )
                        insert_issue(
                            issue_hash=entry["issue_hash"],
                            message=entry["message"],
                            timestamp=entry["timestamp"],
                            category=entry["category"],
                            status="open"
                        )
                        logger.debug(f"Inserted traceback line for error_id={event_id}")


            elif entry["type"] == "warning":
                insert_event(
                    event_hash=entry["hash"],
                    message=entry["message"],
                    timestamp=entry["timestamp"],
                    category=entry["category"],
                    type_="warning"
                )

        except Exception as e:
            logger.error(f"DB insert failed at line {entry.get('line_number')}: {e}")
            continue

    db.commit()


db = get_db_connection()
cursor = db.cursor()
