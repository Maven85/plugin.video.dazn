# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from ssl import TLSVersion
from urllib.parse import urlencode
from urllib3 import PoolManager, ProxyManager
from urllib3.util import create_urllib3_context
import xbmc


class Request:


    def __init__(self, addon):
        self.ctx = create_urllib3_context()
        self.ctx.load_default_certs()
        self.ctx.maximum_version = TLSVersion.TLSv1_2
        self.ctx.post_handshake_auth = True if addon.getSetting('verify_ssl_certificates') == 'true' else False

        self.proxy_use = addon.getSetting('proxy_use') == 'true'
        self.proxy_host = addon.getSetting('proxy_host')
        self.proxy_port = addon.getSetting('proxy_port')


    def exchange(self, url, params=None, data=None, headers=None, json=None, method=None):
        if self.proxy_use == True and url.startswith('https'):
            url = url.replace('https', 'http')
            if not params:
                url = '{}{}{}'.format(url, '&' if url.find('?') > -1 else '?', 'originschema=https')
            else:
                params.update({'originschema': 'https'})

        with ProxyManager('http://{}:{}'.format(self.proxy_host, self.proxy_port)) if self.proxy_use == True else PoolManager(ssl_context=self.ctx) as pool:
            if data or json:
                if params:
                    url = '{}?{}'.format(url, urlencode(params))
                if json:
                    r = pool.request('POST', url, headers=headers, json=json)
                else:
                    r = pool.request('POST', url, headers=headers, body=data)
            elif method is None:
                r = pool.request('GET', url, fields=params, headers=headers)
            else:
                r = pool.request(method, url, fields=params, headers=headers)

            return r
