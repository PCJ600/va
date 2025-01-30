from queue import Queue
import threading
import traceback
import psutil
import socket
import os
import time
from expiring_dict import ExpiringDict

from http_response import response_iot_task
from host_config import get_host_conf
from log import get_logger
logger = get_logger(__name__)

IOT_COMMON_TASK_Q = Queue()
IOT_COLLECT_TASK_Q = Queue()
IOT_DUPLICATE_TASK_Q = Queue()

class TaskCache:
    def __init__(self):
        self.tasks = ExpiringDict(120)
        self.lock = threading.Lock()

    def add_task(self, task_id):
        with self.lock:
            now = int(time.time())
            self.tasks[task_id] = {"ts": now}

    def duplicate_task(self, task_id):
        duplicate = False
        with self.lock:
            if task_id in self.tasks:
                duplicate = True
        return duplicate

TASKS = TaskCache()


def dispatch_iot_task(task_data):
    try:
        task_id = task_data.get("task_id")
        task_type = task_data.get("task_type")
        if task_id is None:
            logger.info("can't find task id, ignored")
            return

        if TASKS.duplicate_task(task_id):
            logger.info("duplicate iot task %r", task_id)
            return

        # dispatch iot task to queue
        logger.info("dispatch iot task %r", task_id)
        TASKS.add_task(task_id)
        if task_type in {"upgradeAppliance", "configureService"}:
            IOT_COMMON_TASK_Q.put(task_data)
        elif task_type == "collectApplianceMetrics":
            IOT_COLLECT_TASK_Q.put(task_data)
        else:
            logger.info("unknown task_type: %r, ignored", task_type)
    except:
        logger.error("dispatch iot task fail %r", traceback.format_exc())


def get_ipv4():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    try:
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            if addr[1] == socket.SOCK_STREAM:
                if ':' not in addr[4][0]:
                    return addr[4][0]
    except socket.gaierror:
        pass
    return local_ip if '.' in local_ip and not local_ip.startswith('127.') else '127.0.0.1'
 


g_service_settings = {}
def configure_service(task_data):
    try:
        logger.info("configure service task_data: %r", task_data)
        svc_code = task_data.get('service_code')
        settings_dict = task_data.get('body')
        if svc_code not in g_service_settings:
            g_service_settings[svc_code] = settings_dict
        else:
            for key, val in settings_dict.items():
                g_service_settings[svc_code][key] = val

        # response
        task_id = task_data.get("task_id")
        payload = {
            "task_id": task_id,
            "task_status": "success",
            "error_message": "",
            "task_result": {}
        }
        if response_iot_task(payload) < 0:
            logger.error("response collect va metrics task failed")
    except:
        logger.error("configure service task fail %r", traceback.format_exc())



def upgrade_appliance(task_data):
    logger.info("handle upgrade appliance task: %r", task_data)

    


def collect_va_metrics(task_data):
    logger.info("handle collect va metrics task: %r", task_data)

    va_info = {}
    try:
        va_info["recordTime"] = int(time.time())
        va_info["hostname"] = socket.gethostname()
        va_info["ipv4"] = get_ipv4()
        va_info["cpu"] = {"total": psutil.cpu_count(), "usage": psutil.cpu_percent()}
        va_info["memory"] = {"usage": psutil.virtual_memory().used, "total": psutil.virtual_memory().total}
        cmd = "cat /proc/cpuinfo | grep 'model name' | head -n 1 | awk -F: '{print $2}'"
        with os.popen(cmd, 'r') as p:
            va_info["cpuModel"] = p.read().rstrip('\n').lstrip()
        logger.info("response va metrics: %r", va_info)

        # response metric data to backend
        task_id = task_data.get("task_id")
        payload = {
            "task_id": task_id,
            "task_status": "success",
            "error_message": "success",
            "task_result": va_info
        }
        ret = response_iot_task(payload)
        if ret < 0:
            logger.error("response collect va metrics task failed")

    except:
        logger.error("collect va metrics exception: %r", traceback.format_exc())



def iot_common_task():
    while True:
        task_data = IOT_COMMON_TASK_Q.get()
        task_type = task_data.get("task_type")
        try:
            if task_type == "upgradeAppliance":
                upgrade_appliance(task_data)
            elif task_type == "configureService":
                configure_service(task_data)
            else:
                logger.error("iot common task failed, invalid task_type: %r", task_type)
        except:
            logger.error("iot common task faild: %r", traceback.format_exc())


def iot_collect_task():
    while True:
        task_data = IOT_COLLECT_TASK_Q.get()
        task_type = task_data.get("task_type")
        try:
            if task_type == "collectApplianceMetrics":
                collect_va_metrics(task_data)
            else:
                logger.error("iot collect task failed, invalid task_type: %r", task_type)
        except:
            logger.error("iot collect task failed: %r", traceback.format_exc())


def iot_duplicate_task():
    while True:
        task_data = IOT_DUPLICATE_TASK_Q.get()
        task_id = task_data.get("task_id")
        try:
            payload = {
                "task_id": task_id,
                "task_status": "ignored",
                "error_message": "ignored",
                "task_result": {}
            }
            ret = response_iot_task(payload)
            if ret < 0:
                logger.error("response iot duplicate task failed")

        except:
            logger.error("iot duplicate task failed: %r", traceback.format_exc())


def start_iot_task_consumer_threads():
    thread_list = []
    t1 = threading.Thread(target=iot_common_task, name='iot_common_task', daemon=True)
    t1.start()
    thread_list.append(t1)
    t2 = threading.Thread(target=iot_collect_task, name="iot_collect_task", daemon=True)
    t2.start()
    thread_list.append(t2)
    t3 = threading.Thread(target=iot_duplicate_task, name="iot_duplicate_task", daemon=True)
    t3.start()
    thread_list.append(t3)

    for t in thread_list:
        t.join()

if __name__ == '__main__':
    task_data = {"task_id": "0"}
    collect_va_metrics(task_data)
