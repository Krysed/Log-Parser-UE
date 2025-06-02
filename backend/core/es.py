from elasticsearch import Elasticsearch
from datetime import datetime, timezone
import os

def get_es_connection():
    return Elasticsearch(os.getenv("ELASTIC_URL", "http://elasticsearch:9200"))

def insert_logfile_to_es(logfile):
    with open(logfile, 'r') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        doc = {
            "line": line.strip(),
            "line_number": i + 1,
            "filename": os.path.basename(logfile),
            "@timestamp": datetime.now(timezone.utc).isoformat()
        }
        es.index(index="logs", body=doc)

es = get_es_connection()
