import logging
import os

# TODO:
def collect_operational_logs():
    pass

os.makedirs("logs", exist_ok=True)

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/detected_issues.log")
        ]
    )


logger = logging.getLogger("log-analyzer")
