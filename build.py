import subprocess
import argparse
import requests
import logging
import sys
import os

WORKSPACE_DIR = os.getcwd()
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
REQUIREMENTS_PATH = os.path.join(WORKSPACE_DIR, "requirements.txt")
LOGS_ENDPOINT = "http://localhost:8000/logs"

logging.basicConfig(level=logging.INFO)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", default=False,help="Clean logfiles, remove attached volumes. Use when want to do a clean start of te project.")
    parser.add_argument("--insert-logfile", metavar="regexp", nargs="?", const="", default=None, help="Path to the logfile to parse and insert (--insert-logfile='<file_path>') Can place multiple logfiles separated by `,` Each logfile can be 10 mb max.")

    return parser.parse_args(sys.argv[1:])

def insert_log(logfiles):
    files = logfiles.split(',')
    for file in files:
        if os.path.exists(os.path.join(file)):
            logging.info(f"logfile: {file} exists.")
            with open(file, "rb")as f:
                file_to_upload = {"file": (file, f)}
                response = requests.post(LOGS_ENDPOINT, files=file_to_upload)
            logging.info(f"Response status code: {response.status_code}")
        else:
            logging.warning(f"File at path: {file}\nDoes not exist.")

def clean_parsed_logfile_contents():
    if os.path.exists(LOGS_DIR):
        for file in os.listdir(LOGS_DIR):
            if os.path.isfile(file):
                try:
                    os.remove(file)
                    logging.info(f"Deleted: {file}")
                except Exception as e:
                    logging.error(f"Exception caught: {e}")
    else:
        logging.info(f"{LOGS_DIR} does not exist. Creating.")
        os.makedirs(LOGS_DIR, exist_ok=True)
    subprocess.run(["docker-compose", "down", "-v"])
    logging.info("Cleaned up docker containers")

if __name__ == "__main__":
    switches = parse_arguments()
    if switches.clean:
        clean_parsed_logfile_contents()
    elif switches.insert_logfile:
        insert_log(switches.insert_logfile)
    else:
        logging.info(f"Please sellect appropriate flag while running the script:\n--clean\n--insert-logfile=<logfile_path>")
    