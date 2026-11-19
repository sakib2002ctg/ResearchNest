import logging
from pathlib import Path

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)

# Outbound URL logs can include search text and provider credentials.
for outbound_logger in ("httpx", "httpcore"):
    logging.getLogger(outbound_logger).setLevel(logging.WARNING)

# Shared logger for the application
logger = logging.getLogger("researchnest")
