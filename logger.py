import logging.config

import ecs_logging


def configure_logging():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "ecs": {"()": ecs_logging.StdlibFormatter},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "ecs",
                "stream": "ext://sys.stdout",
                "level": "DEBUG",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["console"]},
    }
    logging.config.dictConfig(logging_config)
