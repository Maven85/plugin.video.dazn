# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from six.moves import urllib
from io import StringIO
import gzip
import xbmc

import json as real_json

try:
    basestring
except NameError:
    basestring = str


class ErrorHandler(urllib.request.HTTPDefaultErrorHandler):


    def http_error_default(self, req, fp, code, msg, hdrs):
        infourl = urllib.response.addinfourl(fp, hdrs, req.get_full_url())
        infourl.status = code
        infourl.code = code
        return infourl


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):


    def http_error_302(self, req, fp, code, msg, headers):
        infourl = urllib.response.addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        infourl.code = code
        return infourl


    http_error_300 = http_error_302
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302


class Response():


    def __init__(self):
        self.headers = {}
        self.code = -1
        self.text = u''
        self.status_code = -1


    def read(self):
        return self.text


    def json(self):
        return real_json.loads(self.text)


class Request:


    def __init__(self, plugin):
        self.plugin = plugin


    def _request(self, method, url,
                 params=None,
                 data=None,
                 headers=None,
                 cookies=None,
                 files=None,
                 auth=None,
                 timeout=None,
                 allow_redirects=True,
                 proxies=None,
                 hooks=None,
                 stream=None,
                 verify=None,
                 cert=None,
                 json=None):
        if not headers:
            headers = {}

        url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")

        handlers = []

        import sys
        # starting with python 2.7.9 urllib verifies every https request
        if False == verify and sys.version_info >= (2, 7, 9):
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=ssl_context))

        # handlers.append(urllib.request.HTTPCookieProcessor())
        # handlers.append(ErrorHandler)
        if not allow_redirects:
            handlers.append(NoRedirectHandler)
        opener = urllib.request.build_opener(*handlers)

        if params:
            url = '{0}?{1}'.format(url, urllib.parse.urlencode(params))
        request = urllib.request.Request(url)
        if headers:
            for key in headers:
                request.add_header(key, headers[key])
        if data or json:
            if self.plugin.get_dict_value(headers, 'content-type').startswith('application/x-www-form-urlencoded') and data:
                # transform a string into a map of values
                if isinstance(data, basestring):
                    _data = data.split('&')
                    data = {}
                    for item in _data:
                        name, value = item.split('=')
                        data[name] = value

                request.data = urllib.parse.urlencode(data)
            elif self.plugin.get_dict_value(headers, 'content-type').startswith('application/json') and data:
                request.data = urllib.parse.urlencode(data)
            elif json:
                request.data = urllib.parse.urlencode(json)
            else:
                if not isinstance(data, basestring):
                    data = str(data)

                if isinstance(data, str):
                    data = data.encode('utf-8')
                request.data = data
        elif method.upper() in ['POST', 'PUT']:
            request.data = 'null'.encode('utf-8')
        request.get_method = lambda: method
        result = Response()
        response = None
        try:
            response = opener.open(request)
        except urllib.error.HTTPError as e:
            # HTTPError implements addinfourl, so we can use the exception to construct a response
            if isinstance(e, urllib.response.addinfourl):
                response = e
        except Exception as e:
            result.text = e
            return result

        # process response
        result.headers.update(response.headers)
        result.status_code = response.getcode()
        if method.upper() == 'HEAD':
            return result
        elif response.headers.get('Content-Encoding', '').startswith('gzip'):
            buf = StringIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            result.text = f.read()
        else:
            result.text = response.read()

        return result


    def get(self, url, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        return self._request('GET', url, **kwargs)


    def post(self, url, data=None, json=None, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        return self._request('POST', url, data=data, json=json, **kwargs)


    def put(self, url, data=None, json=None, **kwargs):
        return _request('PUT', url, data=data, json=json, **kwargs)


    def delete(self, url, **kwargs):
        return self._request('DELETE', url, **kwargs)


    def head(self, url, **kwargs):
        return self._request('HEAD', url, **kwargs)