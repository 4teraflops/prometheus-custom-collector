import time
from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily
from prometheus_client import start_http_server
import requests
from loguru import logger

logger.add(f'log/{__name__}.log', format='{time} {level} {message}', level='DEBUG', rotation='10 MB', compression='zip')

urls = [
    'https://acqpc.bisys.ru/status?format=json',
    'https://mobile.ckassa.ru/status?format=json',
    'https://acqpc.bisys.ru/status?format=json'
]


def get_data_from_nginx(url):
    s = requests.Session()
    r = s.get(url)
    return r.json()


@logger.catch()
class CustomCollector(object):
    def __init__(self):
        pass

    def collect(self):
        g = GaugeMetricFamily("nginx_upstreams", 'Help text', labels=['upstream', 'name'])
        for url in urls:  # Итерация по списку урлов
            request = get_data_from_nginx(url)
            #logger.info(f'url: {url}\nrequest: {request}')
            for server in request["servers"]["server"]:  # Итерация по списку доступных апстримов
                #logger.info(f'server: {server}')
                upstream = server["upstream"]
                hostname = server["name"]
                if server["status"] == 'up':  # заменяем на цифры, чтоб прометей принял
                    state = 1
                elif server["status"] == 'down':
                    state = 0
                g.add_metric([upstream, hostname], state)

        #g.add_metric(["api.skassa.ru"], 1)
        yield g


if __name__ == '__main__':
    try:
        start_http_server(8000)
        REGISTRY.register(CustomCollector())
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Program stopped')
