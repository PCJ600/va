from queue import Queue
import threading
import time
import traceback
import json

from mq import RabbitMQConsumer
from http_response import response_iot_task
from host_config import init_host_conf, get_host_conf
from task_handler import dispatch_iot_task
from log import get_logger
logger = get_logger(__name__)

iot_handler = None

def consume_iot_task_callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode())
        logger.debug("Received message: %r", data)
        dispatch_iot_task(data)
    except:
        logger.error("iot receive message fail %r", traceback.format_exc())


class IOTHandler:
    def __init__(self):
        self.consumer = None

    def create_iot_consumer(self):
        t = threading.Thread(target=self.create_iot_consumer_task, name="create_iot_consumer_task", daemon=True)
        t.start()

    def create_iot_consumer_task(self):
        host_conf = get_host_conf()
        logger.info("ready to create iot consumer, host_conf: %r", host_conf)

        va_id = host_conf.get('appliance_id')
        iot_host = host_conf.get('iot_host')
        iot_port = host_conf.get('iot_port')
        iot_username = host_conf.get('iot_username')
        iot_password = host_conf.get('iot_password')
        exchange_name = 'va_task'
        queue_name = 'va_task_' + va_id
        routing_key = queue_name
        try:
            self.consumer = RabbitMQConsumer(host=iot_host, port=iot_port, username=iot_username, password=iot_password, queue_name=queue_name,
                    exchange_name=exchange_name, routing_key=routing_key, consume_callback=consume_iot_task_callback)
            # TODO: reconnect if host conf changed.
            while True:
                self.consumer.connect()
                time.sleep(10)
        except:
            logger.error("create iot consumer err: %r", traceback.format_exc())


def init_iot_connection():
    global iot_handler
    iot_handler = IOTHandler()
    iot_handler.create_iot_consumer()

if __name__ == "__main__":
    init_iot_connection()
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        exit(0)
