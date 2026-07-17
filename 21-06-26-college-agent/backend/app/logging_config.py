import json
import logging
import logging.handlers
from datetime import datetime, UTC
from pathlib import Path


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(log_dir: str = "logs", log_level: str = "INFO"):
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.handlers = []

    console_handler = logging.StreamHandler()
    console_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)

    logging.getLogger("app.api").setLevel(logging.DEBUG)
    logging.getLogger("app.services").setLevel(logging.DEBUG)

    logging.info("Logging configured successfully")
