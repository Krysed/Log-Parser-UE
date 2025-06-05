from fastapi import APIRouter, UploadFile, File, HTTPException, Path, Query, Body
from typing import Optional
from datetime import datetime, timezone
from core.db import db, insert_parsed_logs_to_db, insert_issue, delete_specified_issue, update_issue_status, get_issues, get_issue_by_id
from core.es import insert_logfile_to_es, fetch_log_entry, fetch_log_datetime, fetch_log_line_number
from core.parser import parse_log_file, generate_log_id_hash, get_log_hash
from core.logger import logger

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
    try:
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
        insert_logfile_to_es(filename)
        return {
            "filename": basename,
            "parsed": len(parsed_entries)
        }
    except Exception as e:
        logger.error(f"Caught exception: {e}")

# Elasticsearch
@router.get("/logs/{log_entry_id}")
def get_log_by_id(log_entry_id: str):
    result = fetch_log_entry(log_entry_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    return result

@router.get("/logs/{log_entry_id}/line_number")
def get_log_line(log_entry_id: str):
    line_number = fetch_log_line_number(log_entry_id)
    if line_number is None:
        raise HTTPException(status_code=404, detail="Line number not found")
    return {"line_number": line_number}

@router.get("/logs/{log_entry_id}/datetime")
def get_log_datetime(log_entry_id: str):
    datetime_value = fetch_log_datetime(log_entry_id)
    if datetime_value is None:
        raise HTTPException(status_code=404, detail="Timestamp not found")
    return {"datetime": datetime_value}

# Postgres 
@router.get("/issues/{issue_id}")
def get_issue(issue_id: int):
    issue = get_issue_by_id(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue

@router.get("/issues")
def list_issues(status: Optional[str] = Query(None)):
    try:
        return get_issues(status)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"API error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve issues")

@router.patch("/issues/{issue_id}")
def patch_issue_status(issue_id: int, new_status: str = Body(..., embed=True)):
    try:
        updated = update_issue_status(issue_id, new_status)
        if not updated:
            raise HTTPException(status_code=404, detail="Issue not found")
        return {"message": f"Issue {issue_id} status updated to '{new_status}'"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update issue status")

@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int = Path(...)):
    try:
        deleted = delete_specified_issue(issue_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Issue not found")
        return {"message": f"Issue {issue_id} deleted."}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete issue and events")

@router.post("/issues")
def create_issue(
    message: str = Body(...),
    category: str = Body(...),
    status: str = Body(default="open"),
    severity: str = Body(default="Error"),
    line_number: Optional[int] = Body(default=None)
):
    try:
        log_entry_id = generate_log_id_hash(message)
        timestamp = datetime.now(timezone.utc).strftime("%Y.%m.%d-%H:%M:%S")

        issue_id, _ = insert_issue(get_log_hash(message), log_entry_id, message, timestamp, category, severity, line_number, status)
        db.commit()
        return {"message": f"Issue {log_entry_id} - inserted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating issue: {e}")
        raise HTTPException(status_code=500, detail="Failed to create issue")
