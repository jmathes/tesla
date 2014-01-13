import urllib
import urllib2
import json
import time
import random
import logging
from os import environ

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)

PREFIX = "https://portal.vn.teslamotors.com/"

def C2F(c):
    return (9./5) * c + 32

def F2C(f):
    return (f - 32) * (5./9)

def my_cars(email=None, password=None):
    if email is None:
        email = environ['TESLA_EMAIL']
    if password is None:
        password = environ['TESLA_PASSWORD']
    account = Account(email, password)
    return account.vehicles()

def my_car(email=None, password=None):
    return my_cars(email, password)[0]

class CommandFailure(RuntimeError):
    pass

class ShhhError(RuntimeError):
    pass

class Account(urllib2.BaseHandler):
    def __init__(self, email, password):
        self._email = email
        self._password = password
        self._opener = urllib2.build_opener(self)
        self._cookies = {}
        self._cmd("login")
        self._cmd("login", {'user_session[email]': self._email, 'user_session[password]' : self._password})

    def https_response(self, request, response):
        def is_ignored(cookie):
            return ( False
                or any([cookie.strip().startswith(name) for name in ['path', 'HttpOnly', 'secure', 'expires']])
                )
        cookie_header = response.headers.getheaders('Set-Cookie')
        if cookie_header:
            new_cookies = [
                cookie.strip().split('=') if '=' in cookie else [cookie, None]
                for cookie
                in (cookie_header[0]).split(";")
                if not is_ignored(cookie)
                ]
            self._cookies.update(new_cookies)
        return response

    def https_request(self, request):
        request.add_header('Cookie',
           "; ".join(["%s=%s" % cookie for cookie in self._cookies.iteritems()]))
        return request

    def vehicles(self):
        car_info_list = self._json('vehicles')
        return [Car(self, car_info) for car_info in car_info_list]

    def _cmd(self, cmd, data=None):
        url = PREFIX + cmd
        for i in xrange(10):
            try:
                if data is not None:
                    response = self._opener.open(url, urllib.urlencode(data))
                else:
                    response = self._opener.open(url)
                return response
            except urllib2.HTTPError, e:
                time.sleep(0.5)
        raise e

    def _json(self, cmd, data=None):
        error = None
        for retry in xrange(5):
            try:
                result = json.loads(self._cmd(cmd, data).readlines()[0])
                return result
            except urllib2.HTTPError, e:
                error = e
        if e is not None:
            raise e


class Car(object):
    def __init__(self, account, data):
        self._account = account
        data[u'option_codes'] = data[u'option_codes'].split(u',')
        self.id = data['id']
        self.vin = data['vin']
        self.car_state = {
            'general' : {
                'last' : data,
                'timestamp' : time.time(),
                'expiry' : None,
            },
            'mobile_enabled' : {
                'last' : None,
                'timestamp' : 0,
                'expiry' : 5,
            },
            'drive_state' : {
                'last' : None,
                'timestamp' : 0,
                'expiry' : 5,
            },
            'climate_state' : {
                'last' : None,
                'timestamp' : 0,
                'expiry' : 20,
            },
            'gui_settings' : {
                'last' : None,
                'timestamp' : 0,
                'expiry' : 20,
            },
            'charge_state' : {
                'last' : None,
                'timestamp' : 0,
                'expiry' : 20,
            },
            'vehicle_state' : {
                'last' : None,
                'timestamp' : 0,
                'expiry' : 20,
            },
        }
        self._last_awake_update = time.time()

    def run_query(self, query):
        state = self.car_state[query]
        if time.time() - state['timestamp'] < state['expiry'] and self.awake:
            url = "/vehicles/%s/" % self.id
            url += "command/" if query != "mobile_enabled" else ""
            url += query
            state['last'] = self._json(url)
            state['timestamp'] = time.time()
        return state['last']

    def refresh(self, query):
        assert query in self.AVAILABLE_QUERIES
        self._attr_metadata['last_update'] = 0

    def __repr__(self):
        return "<%s.%s %s (vin %s)>" % (self.__module__, self.__class__.__name__, self.id, self.vin)

    def _communicate(self, url):
        if self.asleep:
            raise ShhhError("Not safe to run %s; care is asleep. call wake_up() if you're sure" % url)
        return self._account._json(url)

    def __getattribute__(self, attr):
        if (False
                or attr == 'car_state'
                or attr not in self.car_state
                or not self.car_state[attr]['expiry']):
            return super(Car, self).__getattribute__(attr)
        now = time.time()
        state = self.car_state[attr]
        if time.time() - state['timestamp'] > state['expiry']:
            url = "/vehicles/%s/" % self.id
            url += "command/" if attr != "mobile_enabled" else ""
            url += attr
            state['last'] = self._json(url)
            state['timestamp'] = time.time()
        return state['last']

    def locate(self):
        return (self.drive_state['longitude'], self.drive_state['latitude'])

    def _json(self, url, **kwargs):
        if kwargs:
            url += "?" + urllib.urlencode(kwargs)
        result = self._communicate(url)
        return result

    def _cmd(self, cmd, **kwargs):
        logging.info("_cmd: %s", cmd)
        url = "/vehicles/%s/command/%s" % (self.id, cmd)
        return self._json(url, **kwargs)

    @property
    def awake(self):
        return not self.asleep

    @property
    def asleep(self):
        expiry = 1
        if self.car_state['general']['last']['state'] == 'asleep':
            expiry = 10
        if time.time() - self._last_awake_update > expiry:
            car_data_list = self._account._json('vehicles')
            for data in car_data_list:
                if data['vin'] == self.vin and data['id'] == self.id:
                    self.car_state['general']['last']['state'] = data['state']
                    break
        return self.car_state['general']['last']['state'] == 'asleep'

    def wake_up(self):
        start = time.time()
        while True:
            try:
                self._account._json("/vehicles/%s/mobile_enabled" % self.id)
                break
            except urllib2.HTTPError, e:
                if time.time() - start > 300:
                    raise
                time.sleep(1)

    def charge_port_door_open(self):
        return self._cmd('charge_port_door_open')

    def charge_standard(self):
        return self._cmd('charge_standard')

    def charge_max_range(self):
        return self._cmd('charge_max_range')

    def set_charge_limit(self, percent):
        return self._cmd('set_charge_limit', percent=percent)

    def charge_start(self):
        return self._cmd('charge_start')

    def charge_stop(self):
        return self._cmd('charge_stop')

    def flash_lights(self):
        return self._cmd('flash_lights')

    def honk_horn(self):
        return self._cmd('honk_horn')

    def door_unlock(self):
        return self._cmd('door_unlock')

    def door_lock(self):
        return self._cmd('door_lock')

    def set_temps(self, driver_temp, passenger_temp=None):
        if passenger_temp is None:
            passenger_temp = driver_temp
        if self.gui_settings['gui_temperature_units'] == 'F':
            driver_temp = F2C(driver_temp)
            passenger_temp = F2C(passenger_temp)
        return self._cmd('set_temps', driver_temp=driver_temp, passenger_temp=passenger_temp)

    def auto_conditioning_start(self):
        return self._cmd('auto_conditioning_start')

    def auto_conditioning_stop(self):
        return self._cmd('auto_conditioning_stop')

    def sun_roof_control(self, state):
        # open = 100%, close = 0%, comfort = 80%, and vent = ~15%
        return self._cmd('sun_roof_control', state=state)

    def go_crazy(self, seconds):
        self.wake_up()
        start = time.time()
        try:
            while time.time() - start < seconds:
                which = random.choice([
                    self.flash_lights,
                    self.honk_horn,
                    self.door_unlock,
                    self.door_lock,
                    self.sun_roof_control,
                    ])
                args = []
                if which == self.sun_roof_control:
                    args = [random.choice(['open', 'close', 'comfort', 'vent'])]
                which(*args)
        except KeyboardInterrupt:
            pass
        self.repose()

    def repose(self):
        self.door_lock()
        self.sun_roof_control('close')
        self.flash_lights()
        self.set_temps(68, 68)
        self.auto_conditioning_stop()




