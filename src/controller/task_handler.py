from iot_handler import TASK_Q
from queue import Queue
import threading
import traceback
from log import get_logger
logger = get_logger(__name__)

def collect_va_metrics(task_data):
    logger.info("receive collect va metrics task: %r", task_data)

def start_iot_task_consumer_thread():
    while True:
        task_data = TASK_Q.get()
        task_type = task_data.get("taskType")
        try:
            if task_type == "collectApplianceMetrics":
                collect_va_metrics(task_data)
            else:
                logger.error("task type %r invalid, can not handle this", task_type)
        except:
            logger.error("iot task consumer exception %r", traceback.format_exc())

