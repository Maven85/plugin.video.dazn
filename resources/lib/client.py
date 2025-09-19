# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from json import dumps
from xbmc import Monitor


class Client:


    def __init__(self, plugin, credential, requests):
        self.plugin = plugin
        self.credential = credential
        self.requests = requests

        self.DEVICE_ID = self.plugin.get_setting('device_id')
        self.TOKEN = self.plugin.get_setting('token')
        self.COUNTRY = self.plugin.get_setting('country')
        self.LANGUAGE = self.plugin.get_setting('language')
        self.PORTABILITY = self.plugin.get_setting('portability')
        self.MAX_REGISTRABLE_DEVICES = self.plugin.get_setting('max_registrable_devices')
        self.ENTITLEMENT_ID = self.plugin.get_setting('entitlement_id')
        self.ENTITLEMENTS = self.plugin.get_setting('entitlements').split(',')
        self.ERRORS = 0
        self.MONITOR = Monitor()

        self.HEADERS = {
            'Content-Type': 'application/json',
            'Referer': self.plugin.api_base,
            'User-Agent': self.plugin.get_user_agent()
        }

        self.STARTUP = 'https://startup.core.indazn.com/v1/main/web'
        self.RAIL = self.plugin.get_setting('api_endpoint_rail')
        self.RAILS = self.plugin.get_setting('api_endpoint_rails')
        self.EPG = self.plugin.get_setting('api_endpoint_epg')
        self.EVENT = self.plugin.get_setting('api_endpoint_event')
        self.PLAYBACK = self.plugin.get_setting('api_endpoint_playback')
        self.SIGNIN = self.plugin.get_setting('api_endpoint_signin')
        self.SIGNOUT = self.plugin.get_setting('api_endpoint_signout')
        self.REFRESH = self.plugin.get_setting('api_endpoint_refresh_access_token')
        self.PROFILE = self.plugin.get_setting('api_endpoint_userprofile')
        self.RESOURCES = self.plugin.get_setting('api_endpoint_resource_strings')
        self.DEVICES = self.plugin.get_setting('api_endpoint_devices')


    def content_data(self, url, params={}, headers={}):
        data = self.request(url, params=params, headers=headers)
        if data.get('odata.error', None):
            self.errorHandler(data)
        return data


    def rails(self, id_, params_=''):
        params = {}
        params['country'] = self.COUNTRY
        params['groupId'] = id_
        if params_:
            params['params'] = params_
        if self.ENTITLEMENT_ID:
            params['userEntitlements'] = self.ENTITLEMENT_ID
        content_data = self.content_data(self.RAILS, params=params, headers=self.HEADERS)
        for rail in content_data.get('Rails', []):
            id_ = rail.get('Id')
            resource = self.plugin.get_resource(id_, prefix='browseui_railHeader')
            title = resource.get('text')
            if resource.get('found') == False:
                rail_data = self.railFromCache(id_, rail.get('Params', params_))
                title = rail_data.get('Title', rail.get('Id')) if isinstance(rail_data, dict) else rail.get('Id')
            else:
                title = resource.get('text')
            rail['Title'] = title
        return content_data


    def railFromCache(self, id_, params_=''):
        return self.plugin.railCache.cacheFunction(self.rail, id_, params_)


    def rail(self, id_, params_=''):
        params = {}
        params['languageCode'] = self.LANGUAGE
        params['country'] = self.COUNTRY
        params['id'] = id_
        params['params'] = params_
        return self.content_data(self.RAIL, params=params, headers=self.HEADERS)


    def epg(self, params_):
        params = {}
        params['languageCode'] = self.LANGUAGE
        params['country'] = self.COUNTRY
        params['startDate'] = params_
        params['endDate'] = params_
        epg_data = {}
        i = 0
        while i < 2 and not self.MONITOR.abortRequested():
            epg_data = self.content_data(self.EPG, params=params, headers=self.HEADERS)
            i += 1
            self.MONITOR.waitForAbort(1)
        return epg_data


    def event(self, id_):
        params = {}
        params['languageCode'] = self.LANGUAGE
        params['country'] = self.COUNTRY
        params['id'] = id_
        return self.content_data(self.EVENT, params=params, headers=self.HEADERS)


    def resources(self):
        params = {}
        params['languageCode'] = self.LANGUAGE
        params['region'] = self.COUNTRY
        params['platform'] = 'web'
        self.plugin.cache(self.RESOURCES, self.content_data(self.RESOURCES, params=params, headers=self.HEADERS))


    def playback_data(self, id_):
        headers = self.HEADERS.copy()
        headers['authorization'] = f'Bearer {self.TOKEN}'
        headers['x-dazn-device'] = self.DEVICE_ID
        params = {}
        params['AppVersion'] = '0.70.2'
        params['DrmType'] = 'WIDEVINE'
        params['Format'] = 'MPEG-DASH'
        params['PlayerId'] = '@dazn/peng-html5-core/web/web'
        params['Platform'] = 'web'
        params['LanguageCode'] = self.LANGUAGE
        params['Model'] = 'unknown'
        params['Secure'] = 'true'
        params['Manufacturer'] = 'unknown'
        params['PlayReadyInitiator'] = 'false'
        params['Capabilities'] = 'mta'
        params['MtaLanguageCode'] = ''
        params['AssetId'] = id_
        return self.request(self.PLAYBACK, params=params, headers=headers)


    def playback(self, id_, pin):
        if self.plugin.validate_pin(pin):
            self.HEADERS['x-age-verification-pin'] = pin
        data = self.playback_data(id_)
        if data.get('odata.error', None):
            self.errorHandler(data)
            if self.TOKEN:
                data = self.playback_data(id_)
        return data


    def userProfile(self):
        headers = self.HEADERS.copy()
        headers['authorization'] = f'Bearer {self.TOKEN}'
        data = self.request(self.PROFILE, headers=headers)
        if data.get('odata.error', None):
            self.errorHandler(data)
        else:
            if 'PortabilityAvailable' in self.PORTABILITY:
                self.COUNTRY = self.plugin.portability_country(self.COUNTRY, data['UserCountryCode'])
                if not self.LANGUAGE.lower() == data['UserLanguageLocaleKey'].lower():
                    self.LANGUAGE = data['UserLanguageLocaleKey']
                    self.setLanguage(data['SupportedLanguages'])
            self.plugin.set_setting('viewer_id', data['ViewerId'])
            self.plugin.set_setting('language', self.LANGUAGE)
            self.plugin.set_setting('country', self.COUNTRY)
            self.plugin.set_setting('portability', self.PORTABILITY)


    def setLanguage(self, languages):
        self.LANGUAGE = self.plugin.language(self.LANGUAGE, languages)
        self.resources()


    def setToken(self, auth, result):
        self.plugin.log(f'[{self.plugin.addon_id}] signin: {result}')
        if auth and result in ['SignedIn', 'SignedInInactive']:
            self.TOKEN = auth['Token']
            self.MAX_REGISTRABLE_DEVICES = self.plugin.get_max_registrable_devices(self.TOKEN)
            self.ENTITLEMENT_ID = self.plugin.get_entitlement_id(self.TOKEN)
            self.ENTITLEMENTS = self.plugin.get_entitlements(self.TOKEN)
        else:
            if result in ['HardOffer', 'SignedInPaused']:
                self.plugin.dialog_ok(self.plugin.get_resource('error_10101').get('text'))
            self.signOut()
        self.plugin.set_setting('token', self.TOKEN)
        self.plugin.set_setting('max_registrable_devices', f'{self.MAX_REGISTRABLE_DEVICES}')
        self.plugin.set_setting('entitlement_id', self.ENTITLEMENT_ID)
        self.plugin.set_setting('entitlements', ','.join(self.ENTITLEMENTS))


    def signIn(self):
        credentials = self.credential.get_credentials()
        if credentials:
            headers = self.HEADERS.copy()
            headers['x-dazn-ua'] = f'{self.plugin.get_user_agent()} signin/4.59.26.22300 hyper/0.14.0 (web; production; de)'
            data = {
                'Email': credentials['email'],
                'Password': credentials['password'],
                'DeviceId': self.DEVICE_ID,
                'Platform': 'web'
            }
            data = self.request(self.SIGNIN, data=data, headers=headers, verify_ssl_certs=False)
            if data.get('odata.error', None):
                self.errorHandler(data)
            else:
                self.setToken(data['AuthToken'], data.get('Result', 'SignInError'))
                if self.plugin.get_setting('save_login') == 'true' and self.plugin.get_setting('token'):
                    self.credential.set_credentials(credentials['email'], credentials['password'])
        else:
            self.plugin.dialog_ok(self.plugin.get_resource('signin_tvNoSignUpPerex').get('text'))


    def signOut(self):
        if self.TOKEN:
            headers = self.HEADERS.copy()
            headers['authorization'] = f'Bearer {self.TOKEN}'
            data = {
                'DeviceId': self.DEVICE_ID
            }
            r = self.request(self.SIGNOUT, data=data, headers=headers)
        self.TOKEN = ''
        self.plugin.set_setting('token', self.TOKEN)
        self.plugin.set_setting('device_id', '')


    def refreshToken(self):
        headers = self.HEADERS.copy()
        headers['authorization'] = f'Bearer {self.TOKEN}'
        data = {
            'DeviceId': self.DEVICE_ID
        }
        data = self.request(self.REFRESH, data=data, headers=headers)
        if data.get('odata.error', None):
            self.signOut()
            self.errorHandler(data)
        else:
            self.setToken(data['AuthToken'], data.get('Result', 'RefreshAccessTokenError'))


    def playableDevices(self):
        headers = self.HEADERS.copy()
        headers['authorization'] = f'Bearer {self.TOKEN}'
        data = self.request(self.DEVICES, headers=headers)
        if data.get('odata.error', None):
            self.errorHandler(data)
            return None
        else:
            playableDevices = 0
            for device in data.get('devices'):
                if device.get('playable'):
                    playableDevices += 1

            return playableDevices


    def initStartupData(self):
        params = {
            'Platform': 'web',
            'LandingPageKey': 'generic',
            'Brand': 'dazn'
        }
        return self.request(self.STARTUP, params=params, headers=self.HEADERS)


    def initApiEndpoints(self, endpoints_dict):
        self.RAIL = endpoints_dict.get('api_endpoint_rail')
        self.RAILS = endpoints_dict.get('api_endpoint_rails')
        self.EPG = endpoints_dict.get('api_endpoint_epg')
        self.EVENT = endpoints_dict.get('api_endpoint_event')
        self.PLAYBACK = endpoints_dict.get('api_endpoint_playback')
        self.SIGNIN = endpoints_dict.get('api_endpoint_signin')
        self.SIGNOUT = endpoints_dict.get('api_endpoint_signout')
        self.REFRESH = endpoints_dict.get('api_endpoint_refresh_access_token')
        self.PROFILE = endpoints_dict.get('api_endpoint_userprofile')
        self.RESOURCES = endpoints_dict.get('api_endpoint_resource_strings')
        self.DEVICES = endpoints_dict.get('api_endpoint_devices')


    def initRegion(self, startup_data):
        region = startup_data.get('Region', {})
        if region:
            self.PORTABILITY = region['CountryPortabilityStatus']
            self.COUNTRY = region['Country']
            self.LANGUAGE = region['Language']
            self.setLanguage(startup_data['SupportedLanguages'])

        return region


    def startUp(self, region):
        if region.get('isAllowed', False):
            if self.TOKEN:
                self.refreshToken()
            else:
                self.signIn()
        else:
            self.TOKEN = ''
            self.plugin.log(f'[{self.plugin.addon_id}] version: {self.plugin.addon_version} region: {region}')
            self.plugin.dialog_ok(self.plugin.get_resource('error_2003_notAvailableInCountry').get('text'))


    def request(self, url, params={}, data={}, headers={}, verify_ssl_certs=True):
        res = self.requests.exchange(url, params=params, json=data, headers=headers, verify_ssl_certs=verify_ssl_certs)

        if res.data and self.plugin.get_dict_value(res.headers, 'content-type').startswith('application/json'):
            return res.json()
        else:
            if not res.status == 204:
                self.plugin.log(f'[{self.plugin.addon_id}] error: {url} ({res.status}, {self.plugin.get_dict_value(res.headers, "content-type")})')
            if res.status == -1:
                self.plugin.log(f'[{self.plugin.addon_id}] error: {res.data}')
            return {}


    def errorHandler(self, data):
        self.ERRORS += 1
        msg = data['odata.error']['message']['value']
        code = str(data['odata.error']['code'])
        self.plugin.log(f'[{self.plugin.addon_id}] version: {self.plugin.addon_version} country: {self.COUNTRY} language: {self.LANGUAGE} portability: {self.PORTABILITY}')
        self.plugin.log(f'[{self.plugin.addon_id}] error: {msg} ({code})')

        error_codes = ['10006', '10008', '10450']
        pin_codes = ['10155', '10161', '10163']

        if code == '10000' and self.ERRORS < 3:
            self.refreshToken()
        elif (code == '401' or code == '10033') and self.ERRORS < 3:
            self.signIn()
        elif code == '3001':
            startup_data = self.initStartupData()
            region = self.initRegion(startup_data)
            self.startUp(region)
        elif code == '10049':
            self.plugin.dialog_ok(self.plugin.get_resource('signin_errormessage').get('text'))
        elif code == '10450' and self.ERRORS < 3:
            if self.playableDevices() >= int(self.MAX_REGISTRABLE_DEVICES):
                self.plugin.dialog_ok(self.plugin.get_resource('error2_65_450_403_header').get('text'))
            else:
                self.refreshToken()
        elif code == '10801':
            self.plugin.dialog_ok(self.plugin.get_resource('error2_65_801_403_header').get('text'))
        elif code in error_codes:
            self.plugin.dialog_ok(self.plugin.get_resource(f'error_{code}').get('text'))
        elif code in pin_codes:
            self.TOKEN = ''
            self.plugin.dialog_ok(self.plugin.get_resource(f'error_{code}').get('text'))
