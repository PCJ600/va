import requests
import logging
import traceback
import urllib3
from urllib.parse import urljoin
from host_config import get_host_conf

from log import get_logger
logger = get_logger(__name__)

IOT_RESP_URL='/va/{va_id}/tasks/'

def do_http_request(host, path, method, token, **kwargs):
    if not host or not path or not method or not token:
        logger.error("request parameters err %r", (host, path, method))
        return None
    try:
        session = requests.session()
        session.headers.update({
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
            })
        url = urljoin("https://" + host, path)
        logger.info("request url: %s", url)
        return session.request(method, url, **kwargs)

    except:
        logger.error("request error %r", traceback.format_exc())
        return None

# return 0 if resp OK, else return 1
def do_http_request_with_payload(host, path, method, token, payload):
    if payload:
        r = do_http_request(host, path, method, token, verify=False, json=payload)
    else:
        r = do_http_request(host, path, method, token, verify=False)
    if (r is not None) and r.status_code >= 200 and r.status_code < 300:
        logger.debug("iot task response OK, resp: %r", r)
        return 0
    else:
        logger.error("iot task response %r", r)
        return 1


def __response_iot_task(payload):
    host_conf = get_host_conf()
    host = host_conf.get("backend_host")
    path = IOT_RESP_URL.format(va_id=host_conf.get("appliance_id"))
    token = host_conf.get("token")
    return do_http_request_with_payload(host, path, 'POST', token, payload)

def response_iot_task(task_id, task_status="success", error_message="", task_result={}):
    payload = {
        "task_id": task_id,
        "task_status": task_status,
        "error_message": error_message,
        "task_result": task_result
    }
    if __response_iot_task(payload) < 0:
        logger.error("resp %r failed", task_id)


urllib3.disable_warnings()


if __name__ == '__main__':
    token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJjaWQiOiI3N2ExYzk1Ni0xYzhkLTQ3ZmItODAzNi1jOTcwYTRmMmVlNzMiLCJkb21haW4iOiJwZXRlci5iYWNrZW5kLmNvbSIsImV4cCI6MTc2NjM5NzAyOH0.VkMdIjKRQONyy246gylDfUcqE_Be6PTAI4onMesZXRYa3YlnaFib6nOheS2Gze0EPV5EUXYShPoGBVkRdK-42GQCUn0Kw5bFHeRgpde8t2YFxdcNT4gpYwMiKUcUE2EdNI7yyC55kjIpRekjDqsScYzIjktmlSx78vOI9Xaj494jzik5bNpLmNFnVbrkAkKk-oMELEWC4solg-2vY4Gsup2GJIga7SBdP-aIrvGabyv1J6IgxKsUu7rmZyBVSk-Ekg1oig7h2-8qUiQOk6ep8Nam4Dm2KKqwWouWoUm20N6Gy0WEz0-eyez45jFt9UCynz33rv703omtTVGZodmQkA"
    payload = {"message": "hello"}
    ret = response_iot_task(payload)
    logger.info("ret: %d", ret)
