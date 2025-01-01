import logging
import logging.config

# 日志配置字典
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout',
        },
        # TODO: add file handler here
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)

def get_logger(name=__name__):
    return logging.getLogger(name)

if __name__ == '__main__':
	logger = get_logger(__name__)
	logger.info("test logger")
