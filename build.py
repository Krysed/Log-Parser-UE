import subprocess
import argparse
import requests
import logging
import venv
import sys
import os

WORKSPACE_DIR = os.getcwd()
VENV_DIR = os.path.join(WORKSPACE_DIR, ".venv")
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
REQUIREMENTS_PATH = os.path.join(WORKSPACE_DIR, "requirements.txt")
LOGS_ENDPOINT = "http://localhost:8000/logs"

logging.basicConfig(level=logging.INFO)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", default=False, help="Setting up the project.")
    parser.add_argument("--clean", action="store_true", default=False,help="Clean logfiles, remove attached volumes. Use when want to do a clean start of te project.")
    parser.add_argument("--build-images", action="store_true", default=False, help="Build docker images required for the project.")
    parser.add_argument("--insert-logfile", metavar="regexp", nargs="?", const="", default=None, help="Path to the logfile to parse and insert (--insert-logfile='<file_path>') Can place multiple logfiles separated by `,` Each logfile can be 10 mb max.")

    return parser.parse_args(sys.argv[1:])

def env_setup():
    os.makedirs(LOGS_DIR, exist_ok=True)
    if not os.path.exists(VENV_DIR):
        logging.info("Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)
        logging.info("Virtual environment created.\nActivate venv using: `source .venv/bin/activate` and run the `python3 build.py --setup` again")
        sys.exit(0)

    if os.path.exists(REQUIREMENTS_PATH):
        logging.info("Installing pip dependencies.")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_PATH])
            logging.info("Requirements installed sucesstully!")
        except Exception as e:
            logging.error(f"Exception caught {e}")
    else:
        logging.warning(f"{REQUIREMENTS_PATH}: path not found.")

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
    if switches.setup:
        env_setup()
    if switches.clean:
        clean_parsed_logfile_contents()
    elif switches.insert_logfile:
        insert_log(switches.insert_logfile)
    if switches is None:
        os.system("docker-compose up --build")
    