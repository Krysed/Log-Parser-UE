import logging

# Logger config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/detected_issues.log")
        ]
    )

logger = logging.getLogger("log-analyzer")
