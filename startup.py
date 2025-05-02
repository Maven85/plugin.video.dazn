# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from base64 import b64decode
from bottle import request, response, route, run
from urllib.parse import unquote_plus
import json, xbmc, xbmcaddon, xbmcgui

from resources.lib.api import Request


#
# WEB SERVER
#
def init_config(t):
    global w
    w = t


class WebServer():


    def __init__(self):
        init_config(self)

        self.addon = xbmcaddon.Addon()
        self.addonname = self.addon.getAddonInfo('name')
        self.laUrls = {}

        self.requests = Request(self.addon)
        self.port = 8014

        run(host='0.0.0.0', port=self.port, debug=False, quiet=True)


    def get_license(self, asset_id, license_headers, cdm_payload):
        return content_license(asset_id, license_headers, cdm_payload)


    def stop_kodi(self):
        # IT'S NOT THE BEST SOLUTION... BUT IT WORKS.
        self.requests.exchange('http://localhost:{}'.format(self.port))


@route('/api/<asset_id>/<license_url>/licenseurl', method='POST')
def proxy_license_url(asset_id, license_url):
    response.set_header('content-type', 'application/json')
    w.laUrls.update({asset_id: b64decode(license_url).decode('utf-8')})
    return json.dumps({'success': True})


@route('/api/<asset_id>/license', method='POST')
def proxy_license(asset_id):
    response.set_header('content-type', 'application/octet-stream')
    return w.get_license(asset_id, dict(request.headers), request.body.read())


#
# LICENSE
#
def content_license(asset_id, license_headers, cdm_payload):
    if w.laUrls.get(asset_id):
        try:
            license_headers.pop('host') if 'host' in license_headers else license_headers.pop('Host')
            cdm_request = w.requests.exchange(w.laUrls[asset_id], data=cdm_payload, headers=license_headers)
            try:
                j = json.loads(cdm_request.data)
                if j.get('odata.error'):
                    xbmcgui.Dialog().notification(w.addonname, f"{j.get('odata.error').get('message', {}).get('value', 'unknown')}", xbmcgui.NOTIFICATION_ERROR)
                    raise Exception(f"ERROR: {j.get('odata.error').get('message', {}).get('value', 'unknown')}")
            except:
                pass
            return cdm_request.data
        except Exception as e:
            pass
    xbmcgui.Dialog().notification(w.addonname, f"No license url found for asset id {asset_id}.", xbmcgui.NOTIFICATION_ERROR)
    return


#
# MAIN PROCESS
#
def start():

    t = WebServer()

    # START SERVER (+ STOP SERVER BEFORE CLOSING KODI)
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
    t.stop_kodi()


if __name__ == "__main__":
    xbmcaddon.Addon().setSetting('startup', 'true')
    start()
