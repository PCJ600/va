import threading
import copy

from log import get_logger
logger = get_logger(__name__)


class HostConfig:
    def __init__(self):
        self.conf = {}
        self.lock = threading.Lock()
        self.initHostConfig()

    # TODO: get host config from file.
    def initHostConfig(self):
        conf = {}
        conf["appliance_id"] = "974bf535-7930-474e-8da6-780cafff284d"
        conf["iot_host"] = 'localhost'
        conf["iot_port"] = 5672
        conf["iot_username"] = 'admin'
        conf["iot_password"] = 'V2SG@xdr'
        self.conf = conf

    def getHostConfig(self):
        cfg = {}
        with self.lock:
            cfg = copy.deepcopy(self.conf)
        return cfg


g_host_conf = None

def init_host_conf():
    global g_host_conf
    g_host_conf = HostConfig()

def get_host_conf():
    return g_host_conf.getHostConfig()

if __name__ == '__main__':
    init_host_conf()
    logger.info("host conf: %r", g_host_conf.conf)
