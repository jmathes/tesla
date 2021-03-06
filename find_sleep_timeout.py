#!/usr/bin/env python
import tesla
import time
import logging
from os import environ

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)

email = environ['TESLA_EMAIL']
password = environ['TESLA_PASSWORD']
account = tesla.Account(email, password)


car = account.vehicles()[0]
def is_online():
    car = account.vehicles()[0]
    return car.car_state['general']['last']['state'] == 'online'

ub = 1
while is_online():
    ub *= 2
    logging.info(ub)
    time.sleep(ub)

lb = ub / 2


while True:
    logging.info("timeout between %s and %s", lb, ub)
    test = (lb + ub) / 2
    car.wake_up()
    time.sleep(test)
    if is_online():
        lb = test
    else:
        ub = test
    if lb == ub:
        break



