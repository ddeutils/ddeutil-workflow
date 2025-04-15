from ..conf import config

LOGGING_CONFIG = {  # pragma: no cov
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
        "custom_formatter": {
            "format": config.log_format,
            "datefmt": config.log_datetime_format,
        },
    },
    "root": {
        "level": "DEBUG" if config.debug else "INFO",
    },
    "handlers": {
        "default": {
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "stream_handler": {
            "formatter": "custom_formatter",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "file_handler": {
            "formatter": "custom_formatter",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 1024 * 1024 * 1,
            "backupCount": 3,
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default", "file_handler"],
            "level": "DEBUG" if config.debug else "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["stream_handler", "file_handler"],
            "level": "DEBUG" if config.debug else "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["stream_handler", "file_handler"],
            "level": "DEBUG" if config.debug else "INFO",
            "propagate": False,
        },
        # "uvicorn.asgi": {
        #     "handlers": ["stream_handler", "file_handler"],
        #     "level": "TRACE",
        #     "propagate": False,
        # },
    },
}
