# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from urllib.parse import urlencode
from urllib3 import PoolManager
from urllib3.util import create_urllib3_context


class Request:


    def __init__(self, addon):
        self.ctx = create_urllib3_context()
        self.ctx.load_default_certs()
        self.ctx.post_handshake_auth = True if addon.getSetting('verify_ssl_certificates') == 'true' else False


    def exchange(self, url, params=None, data=None, headers=None, json=None, method=None):
        with PoolManager(ssl_context=self.ctx) as pool:
            if data or json:
                if params:
                    url = '{0}?{1}'.format(url, urlencode(params))
                if json:
                    r = pool.request('POST', url, headers=headers, json=json)
                else:
                    r = pool.request('POST', url, headers=headers, body=data)
            elif method is None:
                r = pool.request('GET', url, fields=params, headers=headers)
            else:
                r = pool.request(method, url, fields=params, headers=headers)

            return r
