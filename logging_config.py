import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "chatbot.log"

class IgnoreConnectionResetError(logging.Filter):
    def filter(self, record):
        return not (
            record.name == "asyncio"
            and record.exc_info
            and isinstance(record.exc_info[1], ConnectionResetError)
        )

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=5,             
    encoding="utf-8",
)

console_handler = logging.StreamHandler()

file_handler.addFilter(IgnoreConnectionResetError())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        file_handler,
        console_handler
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)