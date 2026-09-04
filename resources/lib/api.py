# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from ssl import TLSVersion
from urllib.parse import urlencode

from ..modules.urllib3 import PoolManager, ProxyManager
from ..modules.urllib3.util import create_urllib3_context


# The pool managers used to be used as a context manager, which closed every
# pooled connection on exit, so every single request paid a full tcp and tls
# handshake again. Keep them open instead and cache them on module level, so
# that with reuselanguageinvoker the handshake is paid once per host and kodi
# session. urllib3 discards connections the server has closed in the meantime
# before it hands them out again, see connectionpool._get_conn().
# They are built lazily because creating one loads the whole system
# certificate store, which is not cheap and was done twice per invocation.
_pool_managers = {}

# Rail titles are looked up concurrently, and with the default of one the
# pool discards every connection beyond the first instead of keeping it.
MAXSIZE = 8


class Request:


    def __init__(self, addon, proxy_use, max_tls_version=TLSVersion.TLSv1_3):

        self.proxy_use = proxy_use
        self.proxy_host = addon.getSetting('proxy_host')
        self.proxy_port = addon.getSetting('proxy_port')
        self.max_tls_version = max_tls_version


    def pool(self, verify_ssl_certs=True):
        if self.proxy_use == True:
            key = f'proxy|{self.proxy_host}|{self.proxy_port}'
        else:
            key = f'pool|{verify_ssl_certs}|{self.max_tls_version}'

        pool_manager = _pool_managers.get(key)
        if pool_manager is None:
            if self.proxy_use == True:
                pool_manager = ProxyManager(f'http://{self.proxy_host}:{self.proxy_port}', maxsize=MAXSIZE)
            else:
                ctx = create_urllib3_context()
                ctx.load_default_certs()
                if verify_ssl_certs == False:
                    ctx.post_handshake_auth = False
                ctx.maximum_version = self.max_tls_version
                pool_manager = PoolManager(ssl_context=ctx, maxsize=MAXSIZE)
            _pool_managers[key] = pool_manager

        return pool_manager


    def exchange(self, url, headers=None, params=None, data=None, json=None, fields=None, method=None, verify_ssl_certs=True):
        if self.proxy_use == True and url.startswith('https'):
                url = url.replace('https', 'http')
                if not params:
                    url = f"{url}{'&' if url.find('?') > -1 else '?'}originschema=https"
                else:
                    params.update({'originschema': 'https'})

        pool = self.pool(verify_ssl_certs)
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
