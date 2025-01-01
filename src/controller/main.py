import time

from host_config import init_host_conf
from iot_handler import init_iot_connection
from log import get_logger
logger = get_logger(__name__)

def main():
    host_config.init_host_conf()

    iot_handler.init_iot_connection()

    # Start multiple threads to handle iot task

    while True:
        time.sleep(10)
    
if __name__ == '__main__':
    main()
