from elasticsearch import Elasticsearch
from datetime import datetime, timezone
from .logger import logger
from .parser import timestamp_match, generate_log_id_hash
import os

DEFAULT_INDEX="logs"

def get_es_connection():
    return Elasticsearch(os.getenv("ELASTIC_URL", "http://elasticsearch:9200"))

def insert_logfile_to_es(logfile):
    with open(logfile, 'r') as f:
        lines = f.readlines()
    basename = os.path.basename(logfile)
    for i, line in enumerate(lines):
        timestamp , _= timestamp_match(line)
        log = {
            "datetime": timestamp,
            "filename": basename,
            "line_number": i + 1,
            "line": line.strip()
        }
        log_id = generate_log_id_hash(log["datetime"], log["filename"], log["line_number"], log["line"])

        doc = {
            "line": line.strip(),
            "line_number": i + 1,
            "filename": basename,
            "@timestamp": datetime.now(timezone.utc).isoformat()
        }
        es.index(index=DEFAULT_INDEX, id=log_id, body=doc)

def fetch_log_entry(log_entry_id: str):
    try:
        res = es.get(index=DEFAULT_INDEX, id=log_entry_id)
        return res["_source"]
    except Exception as e:
        logger.error(f"Error retrieving log entry {log_entry_id}: {e}")
        return None

def fetch_log_line_number(log_id: str):
    try:
        res = es.get(index=DEFAULT_INDEX, id=log_id)
        return res["_source"].get("line_number")
    except Exception as e:
        logger.error(f"Error retrieving line number for log {log_id}: {e}")
        return None

def fetch_log_datetime(log_id: str):
    try:
        res = es.get(index=DEFAULT_INDEX, id=log_id)
        return res["_source"].get("@timestamp")
    except Exception as e:
        logger.error(f"Error retrieving timestamp for log {log_id}: {e}")
        return None

es = get_es_connection()
