import argparse
import requests
import logging
import sys
import os

BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_ENDPOINT = "http://localhost:8000/logs"

logging.basicConfig(level=logging.INFO)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Setting up the project.")
    parser.add_argument("--clean", action="store_true", help="Clean logfiles contents.")
    parser.add_argument("--build-images", action="store_true", help="Build docker images required for the project.")
    parser.add_argument("--insert-logfile", metavar="regexp", nargs="?", const="", default=None, help="Path to the logfile to parse and insert (--insert-logfile='<file_path>') Can place multiple logfiles separated by `,` Each logfile can be 10 mb max.")

    return parser.parse_args(sys.argv[1:])

#TODO: create setup script logic
def env_setup():
    os.makedirs(DATA_DIR, exist_ok=True)
    
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

# TODO
def clean_parsed_logfile_contents():
    pass

if __name__ == "__main__":
    switches = parse_arguments()
    if switches.setup:
        env_setup()
    if switches.clean:
        clean_parsed_logfile_contents()
    elif switches.insert_logfile:
        insert_log(switches.insert_logfile)
    elif switches.cleanup:
        os.system("docker-compose down -v")
    if switches is None:
        os.system("docker-compose up --build")
    