from typing import Any

from uvicorn.config import LOGGING_CONFIG as LOGGING_CONFIG_UVICORN

from ..conf import config

LOGGING_CONFIG: dict[str, Any] = {  # pragma: no cov
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": LOGGING_CONFIG_UVICORN["formatters"]["default"],
        "access": LOGGING_CONFIG_UVICORN["formatters"]["access"],
        "custom": {
            "format": config.log_format,
            "datefmt": config.log_datetime_format,
        },
    },
    "root": {
        "level": "DEBUG" if config.debug else "INFO",
    },
    "handlers": {
        "default": LOGGING_CONFIG_UVICORN["handlers"]["default"],
        "access": LOGGING_CONFIG_UVICORN["handlers"]["access"],
        "stream_custom": {
            "formatter": "custom",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        # "file_handler": {
        #     "formatter": "custom_formatter",
        #     "class": "logging.handlers.RotatingFileHandler",
        #     "filename": "logs/app.log",
        #     "maxBytes": 1024 * 1024 * 1,
        #     "backupCount": 3,
        # },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default"],
            "level": "DEBUG" if config.debug else "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "DEBUG" if config.debug else "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "DEBUG" if config.debug else "INFO",
        },
        "ddeutil.workflow": {
            "handlers": ["stream_custom"],
            "level": "INFO",
            # "propagate": False,
            "propagate": True,
        },
    },
}
