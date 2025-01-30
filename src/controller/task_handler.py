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

IOT_HEARTBEAT_TASK_Q = Queue()
IOT_COMMON_TASK_Q = Queue()
IOT_COLLECT_TASK_Q = Queue()
IOT_DUPLICATE_TASK_Q = Queue()

class TaskCache:
    def __init__(self):
        self.tasks = ExpiringDict(60)
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

        if TASKS.duplicate_task(task_id) and task_type != 'heartbeat':
            logger.info("duplicate iot task %r", task_id)
            return

        # dispatch iot task to different queue, don't cache heartbeat task
        logger.info("dispatch iot task %r", task_id)
        if task_type == "heartbeat":
            IOT_HEARTBEAT_TASK_Q.put(task_data)
            return

        TASKS.add_task(task_id)
        if task_type == "collectApplianceMetrics":
            IOT_COLLECT_TASK_Q.put(task_data)
        else:
            IOT_COMMON_TASK_Q.put(task_data)
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

        task_id = task_data.get("task_id")
        response_iot_task(task_id)
    except:
        logger.error("configure service task fail %r", traceback.format_exc())


g_service_info = {}
def install_service(task_data):
    try:
        svc_code = task_data.get('service_code')
        target_version = task_data.get('target_version')
        image_path = task_data.get('image_path')
        image_sha256 = task_data.get('image_sha256')

        # assume install done
        if svc_code not in g_service_info:
            g_service_info[svc_code] = {}
        g_service_info[svc_code]['version'] = target_version
        g_service_info[svc_code]['image_path'] = image_path
        g_service_info[svc_code]['image_sha256'] = image_sha256
        g_service_info[svc_code]['status'] = 'Running'
        if svc_code in g_service_settings:
            g_service_info[svc_code]['settings'] = g_service_settings.get(svc_code)

        task_id = task_data.get("task_id")
        response_iot_task(task_id)
        logger.info("install service %r done, version: %r", svc_code, target_version)
    except:
        logger.error("install service task fail %r", traceback.format_exc())


def uninstall_service(task_data):
    try:
        svc_code = task_data.get('service_code')

        # assume uninstall done
        if svc_code in g_service_info:
            del g_service_info[svc_code]

        task_id = task_data.get("task_id")
        response_iot_task(task_id)
        logger.info("uninstall service %r done", svc_code)
    except:
        logger.error("uninstall service task fail %r", traceback.format_exc())


# TODO
def upgrade_appliance(task_data):
    logger.info("handle upgrade appliance task: %r", task_data)

# TODO
def collect_va_metrics(task_data):
    logger.info("handle collect va metrics task: %r", task_data)

    va_info = {}
    try:
        va_info["record_time"] = int(time.time())
        va_info["hostname"] = socket.gethostname()
        va_info["ipv4"] = get_ipv4()
        va_info["cpu"] = {"total": psutil.cpu_count(), "usage": psutil.cpu_percent()}
        va_info["memory"] = {"usage": psutil.virtual_memory().used, "total": psutil.virtual_memory().total}
        va_info["storage"] = {"usage": 1048576, "total": 10485760}
        cmd = "cat /proc/cpuinfo | grep 'model name' | head -n 1 | awk -F: '{print $2}'"
        with os.popen(cmd, 'r') as p:
            va_info["cpuModel"] = p.read().rstrip('\n').lstrip()
        logger.info("response va metrics: %r", va_info)

        # response metric data to backend
        task_id = task_data.get("task_id")
        response_iot_task(task_id, task_result=va_info)
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
            elif task_type == "uninstallService":
                uninstall_service(task_data)
            elif task_type == "installService":
                install_service(task_data)
            else:
                logger.error("iot common task failed, invalid task_type: %r", task_type)
        except:
            logger.error("iot common task failed: %r", traceback.format_exc())


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


def iot_heartbeat_task():
    while True:
        task_data = IOT_HEARTBEAT_TASK_Q.get()
        task_id = task_data.get("task_id")
        try:
            task_result = {
                'services': g_service_info
            }
            response_iot_task(task_id, task_result=task_result)

        except:
            logger.error("iot heartbeat task failed: %r", traceback.format_exc())

def iot_duplicate_task():
    while True:
        task_data = IOT_DUPLICATE_TASK_Q.get()
        task_id = task_data.get("task_id")
        try:
            response_iot_task(task_id, task_status='ignored')
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
    t4 = threading.Thread(target=iot_heartbeat_task, name="iot_heartbeat_task", daemon=True)
    t4.start()
    thread_list.append(t4)

    for t in thread_list:
        t.join()

if __name__ == '__main__':
    task_data = {"task_id": "0"}
    collect_va_metrics(task_data)
