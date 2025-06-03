from datetime import datetime
from .logger import logger
import hashlib
import re
import os

def parse_line(line: str, line_number: int):
    timestamp = None
    category = None
    log_type = None
    message = line.strip()

    timestamp_match = re.match(r"\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}):(\d+)\](\[\s*\d+\])?", line)
    if timestamp_match:
        try:
            timestamp = datetime.strptime(timestamp_match.group(1), "%Y.%m.%d-%H.%M.%S")
            message = line[timestamp_match.end():].strip()
        except Exception as e:
            logger.error(f"Error occured: {e}")

    category_match = re.search(r"(Log\w+):", line)
    if category_match:
        category = category_match.group(1)

    line_lower = line.lower()
    if "error(s)" in line_lower:
        log_type = None
    elif "error" in line_lower:
        if "warning" in line_lower:
            log_type = "warning"
        else:
            log_type = "error"
    elif "warning" in line_lower:
        log_type = "warning"
    elif re.match(r"\s+at\s+", line) or "traceback" in line_lower:
        log_type = "traceback"

    if log_type and message.startswith(log_type.capitalize()):
        type_len = len(log_type)
        if message[type_len:type_len+1] in [":", " "]:
            message = message[type_len:].lstrip(": ").lstrip()

    if category and message.startswith(category):
        category_len = len(category)
        if message[category_len:category_len+1] in [":", " "]:
            message = message[category_len:].lstrip(": ").lstrip()

    return {
        "type": log_type,
        "category": category,
        "message": message,
        "timestamp": timestamp,
        "line_number": line_number,
        "hash": get_log_hash(line),
    }


def parse_log_file(path: str) -> list:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    parsed_entries = []
    current_error = None
    traceback_array = []
    collecting_traceback = False

    for i, line in enumerate(lines):
        parsed = parse_line(line, i + 1)
        line_lower = line.lower()

        if "Error(s)" in line and "Warning(s)" in line:
            continue

        if ("traceback (most recent call last)" in line_lower or "commandletexception" in line_lower or "btraceack" in line_lower):
            collecting_traceback = True
            traceback_array = [parsed]
            continue

        if collecting_traceback:
            if (line.strip() == "" or ("error" not in line_lower and not line_lower.strip().startswith("at "))):
                collecting_traceback = False

                if "commandletexception" in traceback_array[0]["message"].lower():
                    issue_message = traceback_array[0]["message"]
                else:
                    issue_message = traceback_array[-1]["message"]

                collected_traceback = {
                    "type": "error",
                    "message": issue_message,
                    "timestamp": traceback_array[-1]["timestamp"],
                    "category": traceback_array[-1].get("category"),
                    "line_number": i + 1,
                    "traceback": [entry for entry in traceback_array],
                }
                logger.debug(f"current error: {current_error}")
                parsed_entries.append(collected_traceback)
                traceback_array = []
            else:
                traceback_array.append(parsed)
                continue


        if parsed["type"] == "error":
            if current_error:
                parsed_entries.append(current_error)
            current_error = parsed
            current_error["traceback"] = []
        elif parsed["type"] == "warning":
            if current_error:
                parsed_entries.append(current_error)
                current_error = None
            parsed_entries.append(parsed)

    if current_error:
        parsed_entries.append(current_error)

    for entry in parsed_entries:
        if entry["type"] == "error":
            entry["issue_hash"] = get_issue_hash(entry)
            entry["event_hash"] = get_event_hash(entry)
    return parsed_entries

def get_log_hash(log):
    return hashlib.sha256(log.encode('utf-8')).hexdigest()

def get_issue_hash(entry):
    return hashlib.sha256(entry["message"].encode("utf-8")).hexdigest()

def get_event_hash(entry):
    content = entry["message"]
    if "traceback" in entry:
        for tb in entry["traceback"]:
            content += tb["message"]
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
