# encoding: utf-8

from http.server import BaseHTTPRequestHandler, HTTPServer
from json import dumps, loads
from threading import Thread
from socketserver import ThreadingMixIn
from ssl import TLSVersion
import xbmc, xbmcaddon, xbmcgui

from resources.lib.api import Request


class RequestHandler(BaseHTTPRequestHandler):

    addon = xbmcaddon.Addon()
    addon_id = addon.getAddonInfo('id')
    addonname = addon.getAddonInfo('name')
    requests = Request(addon, False, TLSVersion.TLSv1_2)
    mUrls = {}
    laUrls = {}


    def do_GET(self):
        path = self.path
        xbmc.log(f'[{self.addon_id}]: HTTP GET request received to {path}')

        self.send_response(404)
        self.end_headers()


    def do_POST(self):
        path = self.path
        xbmc.log(f'[{self.addon_id}]: HTTP POST request received to {path}')

        if path.endswith('/manifesturl') == False and \
               path.endswith('/licenseurl') == False and \
               path.endswith('/license') == False:
            self.send_response(404)
            self.end_headers()
            return

        asset_id = path.split('/')[2]
        body = self.rfile.read1()
        content_type = None
        res_body = None
        if path.endswith('/manifesturl') or \
               path.endswith('/licenseurl'):
            url = loads(body.decode('utf-8')).get('url')
            if path.endswith('/manifesturl'):
                self.mUrls.update({asset_id: url})
            elif path.endswith('/licenseurl'):
                self.laUrls.update({asset_id: url})
            content_type = 'application/json'
            res_body = dumps({'success': True}).encode('utf-8')
        else:
            if self.laUrls.get(asset_id):
                try:
                    license_headers = dict(self.headers)
                    license_headers.pop('host') if 'host' in license_headers else license_headers.pop('Host')
                    cdm_request = self.requests.exchange(self.laUrls[asset_id], data=body, headers=license_headers)
                    if cdm_request.status != 200:
                        xbmcgui.Dialog().notification(self.addonname, 'License request failed', xbmcgui.NOTIFICATION_ERROR)
                        raise Exception('License request failed')

                    content_type = 'application/dash+xml'
                    res_body = cdm_request.data
                except Exception as e:
                    xbmc.log(f'exception = {e}', xbmc.LOGERROR)
                    self.send_response(500)
                    self.end_headers()
                    return
            else:
                xbmcgui.Dialog().notification(self.addonname, f'No license url found for asset id {asset_id}.', xbmcgui.NOTIFICATION_ERROR)
                self.send_response(500)
                self.end_headers()
                return

        self.send_response(200)
        self.send_header('content-type', content_type)
        self.end_headers()
        self.wfile.write(res_body)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Proxy:


    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')
        self.started = False
        self.host = '127.0.0.1'
        self.port = 8014


    def start(self):
        if self.started:
            return

        self._server = ThreadedHTTPServer((self.host, self.port), RequestHandler)
        self._server.allow_reuse_address = True
        self._httpd_thread = Thread(target=self._server.serve_forever)
        self._httpd_thread.start()
        self.started = True
        xbmc.log(f'[{self.addon_id}]: proxy started {self.host}:{self.port}')


    def stop(self):
        if not self.started:
            return

        self._server.shutdown()
        self._server.server_close()
        self._server.socket.close()
        self._httpd_thread.join()
        self.started = False
        xbmc.log(f'[{self.addon_id}]: proxy stopped')
