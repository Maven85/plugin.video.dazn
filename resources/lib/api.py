# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from ssl import TLSVersion
from urllib.parse import urlencode

from ..modules.urllib3 import PoolManager, ProxyManager
from ..modules.urllib3.util import create_urllib3_context


class Request:


    def __init__(self, addon, proxy_use, max_tls_version=TLSVersion.TLSv1_3):

        self.proxy_use = proxy_use
        self.proxy_host = addon.getSetting('proxy_host')
        self.proxy_port = addon.getSetting('proxy_port')
        self.proxy_manager = ProxyManager(f'http://{self.proxy_host}:{self.proxy_port}')

        self.ctx = create_urllib3_context()
        self.ctx.load_default_certs()
        self.ctx.maximum_version = max_tls_version
        self.pool_manager_1 = PoolManager(ssl_context=self.ctx)

        self.ctx = create_urllib3_context()
        self.ctx.load_default_certs()
        self.ctx.post_handshake_auth = False
        self.ctx.maximum_version = max_tls_version
        self.pool_manager_2 = PoolManager(ssl_context=self.ctx)  


    def exchange(self, url, headers=None, params=None, data=None, json=None, fields=None, method=None, verify_ssl_certs=True):
        if self.proxy_use == True and url.startswith('https'):
                url = url.replace('https', 'http')
                if not params:
                    url = f"{url}{'&' if url.find('?') > -1 else '?'}originschema=https"
                else:
                    params.update({'originschema': 'https'})

        with self.proxy_manager if self.proxy_use == True else self.pool_manager_1 if verify_ssl_certs else self.pool_manager_2 as pool:
            if data or json or fields:
                if params:
                    url = f'{url}?{urlencode(params)}'
                if json:
                    r = pool.request('POST', url, headers=headers, json=json)
                elif fields:
                    r = pool.request_encode_body('POST', url, headers=headers, fields=fields, encode_multipart=False)
                else:
                    r = pool.request('POST', url, headers=headers, body=data)
            elif method is None:
                r = pool.request('GET', url, fields=params, headers=headers)
            else:
                r = pool.request(method, url, fields=params, headers=headers)

            return r
