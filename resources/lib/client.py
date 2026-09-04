# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from concurrent.futures import ThreadPoolExecutor
from time import time
from xbmc import Monitor


# A rail whose header is not in the resource strings only carries its title
# in the rail itself, which costs one request per rail just for a heading.
RAIL_TITLE_CACHE_TTL = 7 * 24 * 3600
RAIL_TITLE_WORKERS = 6
# A heading is not worth stalling the whole directory for, so cap the wait
# instead of letting urllib3 retry a dead connection three times.
RAIL_TITLE_TIMEOUT = 5
RAIL_TITLE_RETRIES = 0

# The epg endpoint sometimes answers with data that is not usable yet.
EPG_TRIES = 2
EPG_RETRY_WAIT = 1


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

        self.HEADERS = self.plugin.get_basic_request_headers().copy()
        self.HEADERS.update({'content-type': 'application/json'})

        self.STARTUP = 'https://startup.core.indazn.com/v1/main/web'
        self.ENTRIES = 'https://dazn-content-proxy.sd.indazn.com/spaces/vhp9jnid12wf/environments/master/entries'
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
        self.SEARCH = self.plugin.get_setting('api_endpoint_search')


    def content_data(self, url, params={}, headers={}):
        data = self.request(url, params=params, headers=headers)
        if data.get('odata.error', None):
            self.errorHandler(data)
        return data


    def rails(self, id_, params_=''):
        params = {
            'country': self.COUNTRY,
            'groupId': id_
        }
        if params_:
            params.update({'params': params_})
        if self.ENTITLEMENT_ID:
            params.update({'userEntitlements': self.ENTITLEMENT_ID})
        content_data = self.content_data(self.RAILS, params=params, headers=self.HEADERS)
        self.railTitles(content_data.get('Rails', []), params_)
        return content_data


    def railTitles(self, rails, params_):
        missing = []
        for rail in rails:
            resource = self.plugin.get_resource(rail.get('Id'), prefix='browseui_railHeader')
            if resource.get('found'):
                rail['Title'] = resource.get('text')
            else:
                rail['Title'] = rail.get('Id')
                missing.append(rail)
        if not missing:
            return

        cached = self.plugin.get_cache(self.plugin.rail_cache)
        now = time()
        outdated = []
        for rail in missing:
            key = f"{rail.get('Id')}|{rail.get('Params', params_)}"
            entry = cached.get(key, {})
            if entry.get('title') and entry.get('stamp', 0) > now - RAIL_TITLE_CACHE_TTL:
                rail['Title'] = entry['title']
            else:
                outdated.append((key, rail))
        if not outdated:
            return

        # These used to run one after the other while the directory was
        # already waiting on them, so fetch them concurrently.
        with ThreadPoolExecutor(max_workers=min(RAIL_TITLE_WORKERS, len(outdated))) as pool:
            titles = list(pool.map(lambda i: self.railTitle(i[1].get('Id'), i[1].get('Params', params_)), outdated))

        entries = {k: v for k, v in cached.items() if v.get('stamp', 0) > now - RAIL_TITLE_CACHE_TTL}
        for (key, rail), title in zip(outdated, titles):
            if title:
                rail['Title'] = title
                entries[key] = {'title': title, 'stamp': now}
        if not entries == cached:
            self.plugin.cache(self.plugin.rail_cache, entries)


    def railTitle(self, id_, params_=''):
        params = {
            'languageCode': self.LANGUAGE,
            'country': self.COUNTRY,
            'id': id_,
            'params': params_
        }
        try:
            # Deliberately without errorHandler(): this runs off the main
            # thread, where opening a dialog or refreshing the token is not
            # safe. A failed lookup falls back to the rail id, which is what
            # the sequential version did as well.
            data = self.request(self.RAIL, params=params, headers=self.HEADERS,
                                timeout=RAIL_TITLE_TIMEOUT, retries=RAIL_TITLE_RETRIES)
        except Exception as e:
            self.plugin.log(f'[{self.plugin.addon_id}] rail title error: {id_} ({e})')
            return None
        return data.get('Title') if isinstance(data, dict) else None


    def rail(self, id_, params_=''):
        params = {
            'languageCode': self.LANGUAGE,
            'country': self.COUNTRY,
            'id': id_,
            'params': params_
        }
        return self.content_data(self.RAIL, params=params, headers=self.HEADERS)


    def entries(self, id_, type):
        params = {
            'content_type': type,
            'locale': f'{self.LANGUAGE.lower()}-{self.COUNTRY.upper()}',
            'include': '10',
            'limit': '1000',
            'fields.platform[in]': 'Web',
            'fields.countries[in]': self.COUNTRY.upper(),
            'fields.pageIds[in]': id_,
            'select': 'fields.loggedInBannerItems,fields.slideIntervalDuration,sys.id,sys.type',
            'fields.environment': 'Prod'
        }
        return self.content_data(self.ENTRIES, params=params, headers=self.HEADERS)


    def epg(self, params_):
        params = {
            'languageCode': self.LANGUAGE,
            'country': self.COUNTRY,
            'startDate': params_,
            'endDate': params_
        }
        # The endpoint can answer with data that is not usable yet, so the
        # request is retried once. It used to be retried unconditionally and
        # waited a second after both tries, which cost every epg page a
        # second request plus two seconds of waiting even when the first
        # answer was already complete. Retry only when it was not, and skip
        # the wait after the last try. parser.epg_items() needs StartDate to
        # build the page at all and Tiles to put anything in it.
        epg_data = {}
        i = 0
        while i < EPG_TRIES and not self.MONITOR.abortRequested():
            epg_data = self.content_data(self.EPG, params=params, headers=self.HEADERS)
            i += 1
            if epg_data.get('StartDate') and epg_data.get('Tiles'):
                break
            if i < EPG_TRIES:
                self.MONITOR.waitForAbort(EPG_RETRY_WAIT)
        return epg_data


    def live_tv(self):
        params = {
            'platform': 'web',
            'id': 'Livetvschedule',
            'languageCode': self.LANGUAGE,
            'country': self.COUNTRY,
            'brand': 'dazn'
        }
        live_tv_data = self.content_data(self.RAIL, params=params, headers=self.HEADERS)
        return live_tv_data


    def event(self, id_):
        params = {
            'languageCode': self.LANGUAGE,
            'country': self.COUNTRY,
            'id': id_
        }
        return self.content_data(self.EVENT, params=params, headers=self.HEADERS)


    def resources(self):
        params = {
            'languageCode': self.LANGUAGE,
            'region': self.COUNTRY,
            'platform': 'web'
        }
        data = self.content_data(self.RESOURCES, params=params, headers=self.HEADERS)
        # Only replace the cached copy with something usable. A failed request
        # used to overwrite a good file with an empty one, which left every
        # label in the ui as its raw key until the next successful fetch.
        if data.get('Strings'):
            self.plugin.cache(self.RESOURCES, data)
            self.plugin.set_setting('resources_language', self.LANGUAGE)


    def playback_data(self, id_, pin):
        headers = self.HEADERS.copy()
        headers.update({
            'authorization': f'Bearer {self.TOKEN}',
            'x-dazn-device': self.DEVICE_ID,
        })
        if self.plugin.validate_pin(pin):
            headers.update({'x-age-verification-pin': pin})
        params = {
            'AppVersion': '0.144.3',
            'DrmType': 'WIDEVINE',
            'Format': 'MPEG-DASH',
            'PlayerId': '@dazn/peng-html5-core/web/web',
            'Platform': 'smarttv',
            'LanguageCode': self.LANGUAGE,
            'Model': 'unknown',
            'Secure': 'true',
            'Manufacturer': 'unknown',
            'PlayReadyInitiator': 'false',
            'Capabilities': 'mta',
            'MtaLanguageCode': '',
            'AssetId': id_
        }
        return self.request(self.PLAYBACK, params=params, headers=headers)


    def playback(self, id_, pin):
        data = self.playback_data(id_, pin)
        if data.get('odata.error', None):
            self.errorHandler(data)
            if self.TOKEN:
                data = self.playback_data(id_, pin)
        return data


    def userProfile(self):
        headers = self.HEADERS.copy()
        headers.update({'authorization': f'Bearer {self.TOKEN}'})
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
        if self.plugin.resources_outdated(self.LANGUAGE):
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
            headers.update({
                'x-dazn-ua': f'{self.plugin.get_user_agent()} signin/undefined hyper/0.14.0 (web; production; de)',
                'accept-language': 'de-DE,de;q=0.9',
                'origin': self.plugin.api_base[0:-1]
            })
            data = {
                'Email': credentials['email'],
                'Password': credentials['password'],
                'DeviceId': self.DEVICE_ID,
                'Platform': 'web'
            }
            data = self.request(self.SIGNIN, data=data, headers=headers)
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
            headers.update({'authorization': f'Bearer {self.TOKEN}'})
            data = {
                'DeviceId': self.DEVICE_ID
            }
            r = self.request(self.SIGNOUT, data=data, headers=headers)
        self.TOKEN = ''
        self.plugin.set_setting('token', self.TOKEN)
        self.plugin.set_setting('device_id', '')


    def refreshToken(self):
        headers = self.HEADERS.copy()
        headers.update({'authorization': f'Bearer {self.TOKEN}'})
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
        headers.update({'authorization': f'Bearer {self.TOKEN}'})
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
        self.SEARCH = endpoints_dict.get('api_endpoint_search')


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


    def search(self, searchterm):
        params = {
            'searchTerm': searchterm,
            'langCode': self.LANGUAGE,
            'country': self.COUNTRY
        }
        return self.request(self.SEARCH, params, headers=self.HEADERS)


    def request(self, url, params={}, data={}, headers={}, verify_ssl_certs=True, timeout=None, retries=None):
        res = self.requests.exchange(url, params=params, json=data, headers=headers, verify_ssl_certs=verify_ssl_certs, timeout=timeout, retries=retries)

        if res.data and \
                (self.plugin.get_dict_value(res.headers, 'content-type').startswith('application/json') or \
                 self.plugin.get_dict_value(res.headers, 'content-type').startswith('application/vnd.contentful.delivery.v1+json')):
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
