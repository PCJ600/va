from iot_handler import TASK_Q
from queue import Queue
import threading
import traceback
import psutil
import socket
import os
import time

from http_response import response_iot_task
from host_config import get_host_conf
from log import get_logger
logger = get_logger(__name__)

IOT_RESP_URL='/va/{va_id}/task/'

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
 

def collect_va_metrics(task_data):
    logger.info("receive collect va metrics task: %r", task_data)

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
        task_id = task_data.get("taskId")
        payload = {
            "taskId": task_id,
            "taskStatus": "success",
            "errorMessage": "success",
            "taskResult": va_info
        }

        host_conf = get_host_conf()
        host = host_conf.get("backend_host")
        path = IOT_RESP_URL.format(va_id=host_conf.get("appliance_id"))
        token = host_conf.get("token")
        ret = response_iot_task(host, path, 'POST', token, payload)
        if ret < 0:
            logger.error("response collect va metrics task failed")

    except:
        logger.error("collect va metrics exception: %r", traceback.format_exc())

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


if __name__ == '__main__':
    task_data = {"taskId": "0"}
    collect_va_metrics(task_data)
