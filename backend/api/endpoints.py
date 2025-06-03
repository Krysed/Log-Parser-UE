from fastapi import APIRouter, UploadFile, File, HTTPException, Path, Query, Body
from typing import Optional
from datetime import datetime, timezone
from core.db import db, cursor, insert_parsed_logs_to_db, insert_issue, insert_event
from core.es import es, insert_logfile_to_es
from core.parser import parse_log_file
from core.logger import logger
from core.parser import get_log_hash

import json
import os

BASE_DIR = os.getcwd()
LOG_DIR = "/app/data/logs"

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Accept the incoming logfiles
@router.post("/logs")
async def collect_logfile(file: UploadFile = File(...)):
    content = await file.read()
    file_basename = (file.filename).split(os.path.sep)
    if len(file_basename) > 1:
        file.filename = file_basename[-1]
    filename = os.path.join(LOG_DIR, file.filename)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    with open(filename, "wb") as f:
        f.write(content)
    logger.info(f"Uploaded file: {filename}")

    parsed_entries = parse_log_file(filename)
    logger.info(f"Parsed logfile: {file.filename}")

    basename = os.path.basename(filename)
    with open(os.path.join(LOG_DIR, f"parsed_{basename}"), "wb") as f:
        for entry in parsed_entries:
            line = json.dumps(entry, default=str) + "\n"
            f.write(line.encode("utf-8"))

    insert_parsed_logs_to_db(parsed_entries)
    # TODO: Uncomment this:
    # insert_logfile_to_es(filename)
    return {
        "filename": basename,
        "parsed": len(parsed_entries)
    }

# TODO: 
def collect_operational_logs():
    pass





# es:
@router.get("/logs/{log_entry_id}")
def get_log_by_id(log_entry_id: str):
    try:
        res = es.get(index="logs", id=log_entry_id)
        return res["_source"]
    except Exception as e:
        logger.error(f"Error retrieving log entry {log_entry_id}: {e}")
        raise HTTPException(status_code=404, detail="Log entry not found")

@router.get("/logs/{log_id}/line_number")
def get_log_line(log_id: str):
    res = es.get(index="logs-index", id=log_id)
    return {"line_number": res["_source"]["line_number"]}

@router.get("/logs/{log_id}/datetime")
def get_log_datetime(log_id: str):
    try:
        res = es.get(index="logs-index", id=log_id)
        return {"datetime": res["_source"].get("@timestamp")}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Log with ID {log_id} not found: {e}")



@router.get("/issues/{issue_id}")
def get_issue(issue_id: int):
    cursor.execute("SELECT * FROM issues WHERE id = %s;", (issue_id,))
    issue = cursor.fetchone()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {
        "id": issue[0],
        "message": issue[1],
        "category": issue[2],
        "timestamp": issue[3],
        "status": issue[4]
    }

@router.get("/issues")
def list_issues(status: Optional[str] = Query(None)):
    if status and status not in ["open", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    if status:
        cursor.execute("SELECT * FROM issues WHERE status = %s;", (status,))
    else:
        cursor.execute("SELECT * FROM issues;")

    issues = cursor.fetchall()
    return [{"id": i[0], "message": i[1], "category": i[2], "timestamp": i[3], "status": i[4]} for i in issues]

router.patch("/issues/{issue_id}")
def update_issue_status(
    issue_id: int,
    new_status: str = Body(..., embed=True)
):
    if new_status not in ["open", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    cursor.execute("UPDATE issues SET status = %s WHERE id = %s RETURNING id;",
                   (new_status, issue_id))
    updated = cursor.fetchone()
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"message": f"Issue {issue_id} status updated to '{new_status}'"}

@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int = Path(...)):
    cursor.execute("DELETE FROM issues WHERE id = %s RETURNING id;", (issue_id,))
    deleted = cursor.fetchone()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"message": f"Issue {issue_id} deleted"}



@router.post("/issues")
def create_issue(
    message: str = Body(...),
    category: str = Body(...),
    status: str = Body(default="open"),
    type_: str = Body(default="error")
):
    try:
        issue_hash = get_log_hash(message)
        timestamp = datetime.now(timezone.utc).strftime("%Y.%m.%d-%H:%M:%S")

        issue_id = insert_issue(issue_hash, message, timestamp, category, status)
        insert_event(issue_hash, message, timestamp, category="custom", type_=type_, issue_id=issue_id)
        db.commit()
        return {"message": "Issue inserted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating issue: {e}")
        raise HTTPException(status_code=500, detail="Failed to create issue")
