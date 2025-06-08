from datetime import datetime
from .logger import logger
import hashlib
import base64
import json
import re
import os

def parse_line(line: str, line_number: int, filename: str):
    if is_not_relevent_line(line):
        return 
    category = None
    log_severity = None
    timestamp, message = timestamp_match(line)
    message = line.strip() if message is None else message

    if re.match(r"^[=\-\*_]{5,}$", message): # if its a separator, return early and set category as a "Separator"
        return {
            "severity": None,
            "category": "Separator",
            "message": message,
            "timestamp": timestamp,
            "line_number": line_number,
            "log_entry_id": generate_log_id_hash(timestamp, os.path.basename(filename), line_number, line),
        }

    nested_category, nested_severity, nested_message = extract_nested_log_info(line)
    if nested_category and nested_severity and nested_message:
        category = nested_category
        log_severity = nested_severity
        message = nested_message
    else:
        category = parse_category_from_line(line)
        line_lower = line.lower()
        if "error(s)" in line_lower or "warning(s)" in line_lower:
            log_severity = None
        elif "error" in line_lower:
            if "warning" in line_lower:
                log_severity = "Warning"
            else:
                log_severity = "Error"
        elif "warning" in line_lower:
            log_severity = "Warning"
        elif re.match(r"\s+at\s+", line) or "traceback" or "callstack" in line_lower:
            log_severity = "Traceback"

    if "Trying again in" in message: # only one Trying again in x seconds. will remain. Instead of multiple 6 12 etc. seconds.
        message = parse_retry_message(message)
    message = remove_bracket_prefixes(message)
    message = cut_after_timestamp_block(message)

    if category:
        message = strip_prefix_if_present(message, category)
    if log_severity:
        message = strip_prefix_if_present(message, log_severity)
    message = remove_trailing_log_marker(message)
    message = remove_initial_tags(message)

    # If category is LogClass, override it with first word in message as is grained down log category
    if category == "LogClass":
        message_parts = message.split()
        if message_parts:
            category = message_parts[0]
            message = " ".join(message_parts[1:]).strip()

    basename = os.path.basename(filename)
    log = {
            "datetime": timestamp,
            "filename": basename,
            "line_number": line_number,
            "line": line.strip()
    }
    log_entry_id = generate_log_id_hash(log["datetime"], log["filename"], log["line_number"], log["line"])

    return {
        "severity": log_severity,
        "category": category,
        "message": message,
        "timestamp": timestamp,
        "line_number": line_number,
        "log_entry_id": log_entry_id,
    }


def parse_log_file(path: str) -> list:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    parsed_entries = []
    current_error = None
    traceback_array = []
    traceback_after_sep = 0
    collecting_traceback = False

    for i, line in enumerate(lines):
        parsed = parse_line(line, i + 1, path)
        if parsed is None:
            continue
        if parsed["message"] == "":
            continue
        if "Error(s)" in line and "Warning(s)" in line: # This kind of line we skip
            continue

        line_lower = line.lower()
        if ("traceback (most recent call last)" in line_lower or "commandletexception" in line_lower or "btraceack" in line_lower or "=== critical error: ===" in line_lower):
            collecting_traceback = True
            traceback_array = [parsed]
            continue

        if collecting_traceback:
            if "executing staticshutdownaftererror" in line_lower:
                traceback_array.append(parsed)
                parsed_entries.append(finalize_traceback(traceback_array))
                traceback_array = []
                collecting_traceback = False
                continue
            if "unhandled exception:" in line_lower or "fatal error!" in line_lower:
                traceback_array.append(parsed)
                continue
            if parsed.get("category") == "Separator":
                traceback_array.append(parsed)
                traceback_after_sep = 2
                continue
            stripped_line = line.strip()
            if (stripped_line == "" or ("error" not in line_lower and not line_lower.strip().startswith("at ")) and traceback_after_sep < 1):
                collecting_traceback = False

                if traceback_array:
                    parsed_entries.append(finalize_traceback(traceback_array))
                    traceback_array = []
                continue

            else:
                traceback_array.append(parsed)
                traceback_after_sep -= 1

                is_last_line = (i == len(lines) - 1)
                if is_last_line and traceback_array:
                    # Finalize traceback at EOF
                    parsed_entries.append(finalize_traceback(traceback_array))
                    traceback_array = []
                    collecting_traceback = False
                continue

        if parsed["severity"] == "Error":
            if current_error:
                parsed_entries.append(current_error)
            current_error = parsed
            current_error["traceback"] = []
        elif parsed["severity"] == "Warning":
            if current_error:
                parsed_entries.append(current_error)
                current_error = None
            parsed_entries.append(parsed)

    if current_error:
        parsed_entries.append(current_error)

    for entry in parsed_entries:
        entry["message_hash"] = get_log_hash(entry["message"])
        if entry["severity"] == "Error":
            content = entry["message"]
            if "Traceback" in entry:
                for tb in entry["traceback"]:
                    content += tb["message"]
                entry["event_hash"] = get_log_hash(content)
    return parsed_entries

def timestamp_match(line):
    timestamp = None
    message = None
    timestamp_match = re.match(r"\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}):(\d+)\](\[\s*\d+\])?", line)
    if timestamp_match:
        try:
            timestamp = datetime.strptime(timestamp_match.group(1), "%Y.%m.%d-%H.%M.%S")
            message = line[timestamp_match.end():].strip()
        except Exception as e:
            logger.error(f"Error occured: {e}")
    return timestamp, message

def strip_prefix_if_present(message: str, prefix: str) -> str:
    if prefix and (message.startswith(prefix) or message.startswith(prefix.lower())):
        prefix_len = len(prefix)
        next_char = message[prefix_len:prefix_len + 1]
        if next_char in [":", " "]:
            return message[prefix_len:].lstrip(": ").lstrip()
    return message.strip()

def parse_retry_message(message: str) -> str:
    return re.sub(r"(Trying again in )\d+(\s+seconds)", r"\1x\2", message)

def is_not_relevent_line(line: str) -> bool:
    non_relevant_lines = ["Display: Warning/Error Summary (Unique only)",
                          "Display: NOTE: Only first 50 warnings displayed.",
                          "To disable this warning set",
                          "Login successful"]
    for l in non_relevant_lines:
        if l in line:
            return True

def parse_category_from_line(line: str) -> str | None:
    cleaned_line = remove_bracket_prefixes(line).lstrip()
    # Explicit catch exception names
    exception_match = re.match(r"(\w*Exception):", cleaned_line, re.IGNORECASE)
    if exception_match:
        return exception_match.group(1)

    match = re.match(r"(Log[A-Za-z0-9]+):", cleaned_line)
    if match:
        return match.group(1)

    if cleaned_line.endswith(":") and "Exception" in cleaned_line:
        first_word = cleaned_line.split()[0]
        if first_word.endswith(":") and "Exception" in first_word:
            return first_word[:-1]

    if cleaned_line.startswith("Display:"):
        parts = cleaned_line.split(":")
        for part in parts:
            part = part.strip()
            if part.startswith("Log") and part[3:].isalpha():
                return part

    lowered = line.lower()
    if "warning:" in lowered:
        try:
            after = lowered.split("warning:")[1].strip()
            if after:
                words = after.split()
                return " ".join(words[:2]).capitalize()
        except IndexError:
            pass
    if "error:" in lowered:
        try:
            after = lowered.split("error:")[1].strip()
            if after:
                words = after.split()
                return " ".join(words[:2]).capitalize()
        except IndexError:
            pass

    return None

# for logs of type : LogInit: Display: LogClass: Warning: Type mismatch in ...
def extract_nested_log_info(line: str) -> tuple[str | None, str | None, str]:
    match = re.match(r"Log\w+:\s*\w+:\s*(Log\w+):\s*(Warning|Error|Display|Info):\s*(.*)", line)
    if match:
        category = match.group(1)
        severity = match.group(2)
        message = match.group(3)
        return category, severity, message
    return None, None, line

def cut_after_timestamp_block(message: str) -> str:
    match = re.search(r"\[\d+s:\d+ms:\d+us\]", message)
    if match:
        return message[match.end():].lstrip()
    return message

def remove_trailing_log_marker(message: str) -> str:
    return re.sub(r"\s*\[log\]$", "", message, flags=re.IGNORECASE).strip()

def remove_bracket_prefixes(message: str) -> str:
    while True:
        message = message.lstrip()
        if message.startswith('['):
            end_idx = message.find(']')
            if end_idx == -1:
                break 
            message = message[end_idx+1:].lstrip()
        elif message.lower().startswith('error:'):
            message = message[len('error:'):].lstrip()
        elif message.lower().startswith('[error]:'):
            message = message[len('[error]:'):].lstrip()
        else:
            break
    return message

def remove_initial_tags(message: str) -> str:
    message = re.sub(r"^(?:\[(SDK|Core|DLSS)\]:\s*)+", "", message, re.IGNORECASE) 
    message = re.sub(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*", "", message) # remove timestamp from the message
    message = re.sub(r"^(?:\[(AssetLog|Compiler)\]\s*)+", "", message, re.IGNORECASE) 
    return message.strip()

def finalize_traceback(traceback_array: list) -> dict:
    if not traceback_array:
        return {}

    if "editor terminated with exit code 1" in traceback_array[0]["message"].lower() or "=== critical error: ===" in traceback_array[0]["message"].lower():
        issue_message = traceback_array[0]["message"]
        category_index = 0
    else:
        issue_message = traceback_array[-1]["message"]
        category_index = -1

    return {
        "severity": "Error",
        "message": issue_message,
        "timestamp": traceback_array[-1]["timestamp"],
        "category": traceback_array[category_index].get("category"),
        "line_number": traceback_array[0]["line_number"],
        "traceback": traceback_array,
        "log_entry_id": traceback_array[-1].get("log_entry_id"),
    }

def get_log_hash(log):
    return hashlib.sha256(log.encode('utf-8')).hexdigest()

def generate_log_id_hash(timestamp: str, filename: str, line_number: int, line: str) -> str:
    payload = {
        "datetime": timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp,
        "filename": filename,
        "line_number": line_number,
        "line": line,
    }
    raw_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    sha1_digest = hashlib.sha1(raw_string.encode()).digest()
    compact_digest = sha1_digest[:15]
    b64_id = base64.urlsafe_b64encode(compact_digest).decode().rstrip('=')

    return b64_id
