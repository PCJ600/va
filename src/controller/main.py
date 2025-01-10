#!/usr/bin/env python3

import time

from host_config import init_host_conf

from iot_handler import init_iot_connection
from task_handler import start_iot_task_consumer_thread
from log import get_logger
logger = get_logger(__name__)

def main():
    init_iot_connection()
    start_iot_task_consumer_thread()

    while True:
        time.sleep(10)
    
if __name__ == '__main__':
    main()
