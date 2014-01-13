import urllib
import urllib2
import json
import time
import random
from os import environ

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
        if data is not None:
            response = self._opener.open(PREFIX + cmd, urllib.urlencode(data))
        else:
            response = self._opener.open(PREFIX + cmd)
        return response

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
    AVAILABLE_QUERIES = [
        'mobile_enabled',
        'charge_state',
        'climate_state',
        'drive_state',
        'gui_settings',
        'vehicle_state',
    ]
    def __init__(self, account, data):
        self._account = account
        data[u'option_codes'] = data[u'option_codes'].split(u',')
        self.general = data
        self.id = data['id']
        self.vin = data['vin']
        self._attr_metadata = {}
        for query in self.AVAILABLE_QUERIES:
            self._attr_metadata[query] = {
                'last_update': 0,
                'expiry': 30,
                'extractor': (lambda x: x),
            }
            self.__dict__[query] = None
        self._attr_metadata['mobile_enabled']['extractor'] = (lambda x: x['result'])

    def diagnostic(self, refresh=True):
        diagnostic = {}
        try:
            for query in self.AVAILABLE_QUERIES:
                if refresh:
                    self.refresh(query)
                diagnostic[query] = self.__getattribute__(query)
            return diagnostic
        except ShhhError:
            return self.general

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
                or attr == 'AVAILABLE_QUERIES'
                or attr not in self.AVAILABLE_QUERIES):
            return super(Car, self).__getattribute__(attr)
        now = time.time()
        metadata = self._attr_metadata[attr]
        if now - metadata['last_update'] > metadata['expiry']:
            path = "vehicles/%s/" % self.id
            if attr != 'mobile_enabled':
                path += "command/"
            self.__dict__[attr] = metadata['extractor'](self._cmd(path + attr))
            if attr == 'climate_state' and self.gui_settings['gui_temperature_units'] == 'F':
                self.__dict__[attr][u'driver_temp_setting'] = C2F(self.__dict__[attr][u'driver_temp_setting'])
                self.__dict__[attr][u'passenger_temp_setting'] = C2F(self.__dict__[attr][u'passenger_temp_setting'])
            metadata['last_update'] = now
        return super(Car, self).__getattribute__(attr)

    def locate(self):
        self.refresh('drive_state')
        return (self.drive_state['longitude'], self.drive_state['latitude'])

    def _cmd(self, cmd, **kwargs):
        url = "/vehicles/%s/command/%s" % (self.id, cmd)
        if kwargs:
            url += "?" + urllib.urlencode(kwargs)
        result = self._communicate(url)
        if not result['result']:
            raise CommandFailure(result['reason'])

    @property
    def asleep(self):
        car_data_list = self._account._json('vehicles')
        for data in car_data_list:
            if data['vin'] == self.vin and data['id'] == self.id:
                self.general['state'] = data['state']
                break
        return self.general['state'] == 'asleep'

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




