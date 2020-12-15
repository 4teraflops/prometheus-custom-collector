import time
import json
from config import webhook_url, admin_id
from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily
from prometheus_client import start_http_server
import requests
from loguru import logger
import sqlite3

logger.add(f'log/{__name__}.log', format='{time} {level} {message}', level='DEBUG', rotation='10 MB', compression='zip')

urls = [
    'https://acqpc.bisys.ru/status?format=json',
    'https://mobile.ckassa.ru/status?format=json',
    'https://acqpc.bisys.ru/status?format=json',
    'https://autopays.ru/status?format=json'
]


def do_alarm(t_alarmtext):
    headers = {"Content-type": "application/json"}
    payload = {"text": f"{t_alarmtext}", "chat_id": f"{admin_id}"}
    requests.post(url=webhook_url, data=json.dumps(payload), headers=headers)


def get_data_from_nginx(url):
    s = requests.Session()
    r = s.get(url)
    return r.json()


def get_finmonstate():
    db_path = '/home/support/soft/webserver/src/db.sqlite'  # prom path
    #db_path = 'C:/Users/User/PycharmProjects/webhook_server/src/db.sqlite'  # dev path
    conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
    cursor = conn.cursor()

    try:
        finmonstate = cursor.execute(
            "SELECT state FROM finmon_states WHERE date_time = (SELECT max(date_time) FROM finmon_states WHERE date_time >= datetime('now', '-2 day'))"
        ).fetchall()[0][0]
    except IndexError:
        finmonstate = 0
    #logger.info(f'finmonstate: {finmonstate}')
    conn.commit()
    return finmonstate


def get_fiscalcount():
    db_path = '/home/support/soft/webserver/src/db.sqlite'
    #db_path = 'C:/Users/User/PycharmProjects/webhook_server/src/db.sqlite'
    conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
    cursor = conn.cursor()

    try:
        fiscalcount = cursor.execute(
            "SELECT count FROM fiscalization_states WHERE date_time = (SELECT max(date_time) FROM fiscalization_states WHERE date_time >= datetime('now', '+5 hours', '-3 hours'))"
        ).fetchall()[0][0]
    except IndexError:
        fiscalcount = 0
    conn.commit()
    return fiscalcount


@logger.catch()
class CustomCollector(object):
    def __init__(self):
        pass

    def collect(self):
        #  Все доступные аплинки
        nginx_upstreams = GaugeMetricFamily("nginx_upstreams", '1/0 = UP/DOWN', labels=['upstream', 'name'])
        for url in urls:  # Итерация по списку урлов
            request = get_data_from_nginx(url)
            # logger.info(f'url: {url}\nrequest: {request}')
            for server in request["servers"]["server"]:  # Итерация по списку доступных апстримов
                # logger.info(f'server: {server}')
                upstream = server["upstream"]
                hostname = server["name"]
                if server["status"] == 'up':  # заменяем на цифры, чтоб прометей принял
                    state = 1
                else:
                    state = 0
                nginx_upstreams.add_metric([upstream, hostname], state)

        #  Состояние загрузки данных по финмон
        finmon = GaugeMetricFamily("finmon_status", "1/0 = UP/DOWN")
        finmon_state = get_finmonstate()
        finmon.add_metric([], finmon_state)
        #  Кол-во платежей в очереди на фискализацию
        fiscal = GaugeMetricFamily("processing_fiscalization_queue", 'count')
        fiscalcount = get_fiscalcount()
        fiscal.add_metric([], fiscalcount)

        yield finmon
        yield nginx_upstreams
        yield fiscal


if __name__ == '__main__':
    try:
        start_http_server(8000)
        REGISTRY.register(CustomCollector())
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Program stopped')
    except Exception as e:
        t_alarmtext = f'prometheus-custom-collector (app.py):\n {str(e)}'
        do_alarm(t_alarmtext)
        logger.error(f'Other except error Exception', exc_info=True)
