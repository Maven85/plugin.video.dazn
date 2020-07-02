# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from .simple_requests.api import Request


class Client:


    def __init__(self, plugin):
        self.plugin = plugin

        self.DEVICE_ID = self.plugin.get_setting('device_id')
        self.TOKEN = self.plugin.get_setting('token')
        self.MPX = self.plugin.get_setting('mpx')
        self.COUNTRY = self.plugin.get_setting('country')
        self.LANGUAGE = self.plugin.get_setting('language')
        self.PORTABILITY = self.plugin.get_setting('portability')
        self.POST_DATA = {}
        self.ERRORS = 0

        self.HEADERS = {
            'Content-Type': 'application/json',
            'Referer': self.plugin.api_base
        }

        self.PARAMS = {
            '$format': 'json'
        }

        self.STARTUP = self.plugin.api_base + 'v5/Startup'
        self.RAIL = self.plugin.api_base + 'v2/Rail'
        self.RAILS = self.plugin.api_base + 'v7/Rails'
        self.EPG = self.plugin.api_base + 'v1/Epg'
        self.EVENT = self.plugin.api_base + 'v2/Event'
        self.PLAYBACK = 'https://api.playback.indazn.com/v3/Playback'
        self.SIGNIN = self.plugin.api_base + 'v5/SignIn'
        self.SIGNOUT = self.plugin.api_base + 'v1/SignOut'
        self.REFRESH = self.plugin.api_base + 'v5/RefreshAccessToken'
        self.PROFILE = self.plugin.api_base + 'v1/UserProfile'
        self.RESOURCES = self.plugin.api_base + 'v1/ResourceStrings'


    def content_data(self, url):
        data = self.request(url)
        if data.get('odata.error', None):
            self.errorHandler(data)
        return data


    def rails(self, id_, params=''):
        self.PARAMS['Country'] = self.COUNTRY
        self.PARAMS['groupId'] = id_
        self.PARAMS['params'] = params
        content_data = self.content_data(self.RAILS)
        self.plugin.log('content_data = {0}'.format(content_data))
        for rail in content_data.get('Rails', []):
            id_ = rail.get('Id')
            resource = self.plugin.get_resource(id_, prefix='browseui_railHeader')
            title = resource.get('text')
            self.plugin.log('resource = {0}'.format(resource))

            if resource.get('found') == False:
                rail_data = self.railFromCache(id_, rail.get('Params', params))
                self.plugin.log('rail_data = {0}'.format(rail_data))
                title = rail_data.get('Title', rail.get('Id')) if isinstance(rail_data, dict) else rail.get('Id')
            else:
                title = resource.get('text')
            rail['Title'] = title
        return content_data


    def railFromCache(self, id_, params=''):
        cached_data = self.plugin.cache.get('rail.{0}'.format(id_))
        if cached_data:
            return cached_data
        else:
            json_data = self.rail(id_, params)
            self.plugin.cache.update({'rail.{0}'.format(id_): json_data})
            return json_data


    def rail(self, id_, params=''):
        self.PARAMS['LanguageCode'] = self.LANGUAGE
        self.PARAMS['Country'] = self.COUNTRY
        self.PARAMS['id'] = id_
        self.PARAMS['params'] = params
        return self.content_data(self.RAIL)


    def epg(self, params):
        self.PARAMS['languageCode'] = self.LANGUAGE
        self.PARAMS['country'] = self.COUNTRY
        self.PARAMS['date'] = params
        return self.content_data(self.EPG)


    def event(self, id_):
        self.PARAMS['LanguageCode'] = self.LANGUAGE
        self.PARAMS['Country'] = self.COUNTRY
        self.PARAMS['Id'] = id_
        return self.content_data(self.EVENT)


    def resources(self):
        self.PARAMS['languageCode'] = self.LANGUAGE
        self.PARAMS['region'] = self.COUNTRY
        self.PARAMS['platform'] = 'web'
        self.plugin.write_file(self.RESOURCES, self.content_data(self.RESOURCES))


    def playback_data(self, id_):
        self.HEADERS['Authorization'] = 'Bearer ' + self.TOKEN
        self.HEADERS['x-dazn-device'] = self.DEVICE_ID
        self.PARAMS['LanguageCode'] = self.LANGUAGE
        self.PARAMS['AssetId'] = id_
        self.PARAMS['Format'] = 'MPEG-DASH'
        self.PARAMS['PlayerId'] = 'DAZN-' + self.DEVICE_ID
        self.PARAMS['Secure'] = 'true'
        self.PARAMS['PlayReadyInitiator'] = 'false'
        return self.request(self.PLAYBACK)


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
        self.HEADERS['Authorization'] = 'Bearer ' + self.TOKEN
        data = self.request(self.PROFILE)
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
        self.plugin.log('[{0}] signin: {1}'.format(self.plugin.addon_id, result))
        if auth and result == 'SignedIn':
            self.TOKEN = auth['Token']
            self.MPX = self.plugin.get_mpx(self.TOKEN)
        else:
            if result in ['HardOffer', 'SignedInInactive', 'SignedInPaused']:
                self.plugin.dialog_ok(self.plugin.get_resource('error_10101').get('text'))
            self.signOut()
        self.plugin.set_setting('token', self.TOKEN)
        self.plugin.set_setting('mpx', self.MPX)


    def signIn(self):
        credentials = self.plugin.get_credentials()
        if credentials:
            self.POST_DATA = {
                'Email': credentials['email'],
                'Password': credentials['password'],
                'DeviceId': self.DEVICE_ID,
                'Platform': 'web'
            }
            data = self.request(self.SIGNIN)
            if data.get('odata.error', None):
                self.errorHandler(data)
            else:
                self.setToken(data['AuthToken'], data.get('Result', 'SignInError'))
        else:
            self.plugin.dialog_ok(self.plugin.get_resource('signin_tvNoSignUpPerex').get('text'))


    def signOut(self):
        self.HEADERS['Authorization'] = 'Bearer ' + self.TOKEN
        self.POST_DATA = {
            'DeviceId': self.DEVICE_ID
        }
        r = self.request(self.SIGNOUT)
        self.TOKEN = ''
        self.plugin.set_setting('token', self.TOKEN)
        self.plugin.set_setting('mpx', '')


    def refreshToken(self):
        self.HEADERS['Authorization'] = 'Bearer ' + self.TOKEN
        self.POST_DATA = {
            'DeviceId': self.DEVICE_ID
        }
        data = self.request(self.REFRESH)
        if data.get('odata.error', None):
            self.signOut()
            self.errorHandler(data)
        else:
            self.setToken(data['AuthToken'], data.get('Result', 'RefreshAccessTokenError'))


    def initRegion(self):
        self.POST_DATA = {
            'LandingPageKey': 'generic',
            'Languages': '{0}, {1}'.format(self.plugin.gui_language(), self.LANGUAGE),
            'Platform': 'web',
            'Manufacturer': '',
            'PromoCode': ''
        }
        data = self.request(self.STARTUP)
        region = data.get('Region', {})
        if region:
            self.PORTABILITY = region['CountryPortabilityStatus']
            self.COUNTRY = region['Country']
            self.LANGUAGE = region['Language']
            self.setLanguage(data['SupportedLanguages'])

        return region


    def startUp(self, region):
        if region.get('isAllowed', False):
            if self.TOKEN:
                self.refreshToken()
            else:
                self.signIn()
        else:
            self.TOKEN = ''
            self.plugin.log('[{0}] version: {1} region: {2}'.format(self.plugin.addon_id, self.plugin.addon_version, region))
            self.plugin.dialog_ok(self.plugin.get_resource('error_2003_notAvailableInCountry').get('text'))


    def request(self, url):
        requests = Request(self.plugin)
        if self.POST_DATA:
            r = requests.post(url, headers=self.HEADERS, data=self.POST_DATA, params=self.PARAMS)
            self.POST_DATA = {}
        else:
            r = requests.get(url, headers=self.HEADERS, params=self.PARAMS)

        if self.plugin.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            return r.json()
        else:
            if not r.status_code == 204:
                self.plugin.log('[{0}] error: {1} ({2}, {3})'.format(self.plugin.addon_id, url, str(r.status_code), r.headers.get('Content-Type', '')))
            if r.status_code == -1:
                self.plugin.log('[{0}] error: {1}'.format(self.plugin.addon_id, r.text))
            return {}


    def errorHandler(self, data):
        self.ERRORS += 1
        msg = data['odata.error']['message']['value']
        code = str(data['odata.error']['code'])
        self.plugin.log('[{0}] version: {1} country: {2} language: {3} portability: {4}'.format(self.plugin.addon_id, self.plugin.addon_version, self.COUNTRY, self.LANGUAGE, self.PORTABILITY))
        self.plugin.log('[{0}] error: {1} ({2})'.format(self.plugin.addon_id, msg, code))

        error_codes = ['10006', '10008']
        pin_codes = ['10155', '10161', '10163']

        if code == '10000' and self.ERRORS < 3:
            self.refreshToken()
        elif (code == '401' or code == '10033') and self.ERRORS < 3:
            self.signIn()
        elif code == '3001':
            self.startUp()
        elif code == '10049':
            self.plugin.dialog_ok(self.plugin.get_resource('signin_errormessage').get('text'))
        elif code in error_codes:
            self.plugin.dialog_ok(self.plugin.get_resource('error_{0}'.format(code)).get('text'))
        elif code in pin_codes:
            self.TOKEN = ''
            self.plugin.dialog_ok(self.plugin.get_resource('error_{0}'.format(code)).get('text'))
