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
        conf["token"] = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJjaWQiOiI3N2ExYzk1Ni0xYzhkLTQ3ZmItODAzNi1jOTcwYTRmMmVlNzMiLCJkb21haW4iOiJwZXRlci5iYWNrZW5kLmNvbSIsImV4cCI6MTc2NjM5NzAyOH0.VkMdIjKRQONyy246gylDfUcqE_Be6PTAI4onMesZXRYa3YlnaFib6nOheS2Gze0EPV5EUXYShPoGBVkRdK-42GQCUn0Kw5bFHeRgpde8t2YFxdcNT4gpYwMiKUcUE2EdNI7yyC55kjIpRekjDqsScYzIjktmlSx78vOI9Xaj494jzik5bNpLmNFnVbrkAkKk-oMELEWC4solg-2vY4Gsup2GJIga7SBdP-aIrvGabyv1J6IgxKsUu7rmZyBVSk-Ekg1oig7h2-8qUiQOk6ep8Nam4Dm2KKqwWouWoUm20N6Gy0WEz0-eyez45jFt9UCynz33rv703omtTVGZodmQkA"
        conf["backend_host"] = 'peter.backend.com'
        self.conf = conf

    def getHostConfig(self):
        cfg = {}
        with self.lock:
            cfg = copy.deepcopy(self.conf)
        return cfg

    def updateHostConfig(self, host_conf):
        with self.lock:
            self.conf = host_conf

g_host_conf = None

def init_host_conf():
    global g_host_conf
    g_host_conf = HostConfig()

def get_host_conf():
    global g_host_conf
    if g_host_conf is None:
        init_host_conf()
    return g_host_conf.getHostConfig()

if __name__ == '__main__':
    init_host_conf()
    logger.info("host conf: %r", g_host_conf.conf)
