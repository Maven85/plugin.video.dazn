# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from base64 import b64decode
from bottle import request, response, route, run
from json import dumps, loads
import xbmc, xbmcaddon, xbmcgui
import xmltodict

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
        self.mUrls = {}
        self.laUrls = {}

        self.requests = Request(self.addon, False)
        self.port = 8014

        run(host='0.0.0.0', port=self.port, debug=False, quiet=True)


    def get_manifest(self, asset_id, manifest_headers):
        return content_manifest(asset_id, manifest_headers)


    def get_license(self, asset_id, license_headers, cdm_payload):
        return content_license(asset_id, license_headers, cdm_payload)


    def stop_kodi(self):
        # IT'S NOT THE BEST SOLUTION... BUT IT WORKS.
        self.requests.exchange(f'http://localhost:{self.port}')


@route('/api/<asset_id>/<manifest_url>/manifesturl', method='POST')
def proxy_manifest_url(asset_id, manifest_url):
    response.set_header('content-type', 'application/json')
    w.mUrls.update({asset_id: b64decode(manifest_url).decode('utf-8')})
    return dumps({'success': True})


@route('/api/<asset_id>/<license_url>/licenseurl', method='POST')
def proxy_license_url(asset_id, license_url):
    response.set_header('content-type', 'application/json')
    w.laUrls.update({asset_id: b64decode(license_url).decode('utf-8')})
    return dumps({'success': True})


@route('/api/<asset_id>/manifest', method='GET')
def proxy_manifest(asset_id):
    response.set_header('content-type', 'application/dash+xml')
    return w.get_manifest(asset_id, dict(request.headers))


@route('/api/<asset_id>/license', method='POST')
def proxy_license(asset_id):
    response.set_header('content-type', 'application/octet-stream')
    return w.get_license(asset_id, dict(request.headers), request.body.read())


#
# MANIFEST
#
def content_manifest(asset_id, manifest_headers):
    if w.mUrls.get(asset_id):
        try:
            manifest_url = w.mUrls[asset_id]
            manifest_headers = {'user-agent': manifest_headers.get('User-Agent') if manifest_headers.get('User-Agent') else manifest_headers.get('user-agent')}
            res = w.requests.exchange(manifest_url, headers=manifest_headers)
            try:
                j = loads(res.data)
                if j.get('odata.error'):
                    xbmcgui.Dialog().notification(w.addonname, f"{j.get('odata.error').get('message', {}).get('value', 'unknown')}", xbmcgui.NOTIFICATION_ERROR)
                    raise Exception(f"ERROR: {j.get('odata.error').get('message', {}).get('value', 'unknown')}")
            except:
                pass
            xml = xmltodict.parse(res.data)
            if xml.get('MPD').get('BaseURL'):
                if xml.get('MPD').get('BaseURL').startswith('http') == False:
                    xml['MPD']['BaseURL'] = f"{manifest_url.split('/web', 1)[0]}/{xml.get('MPD').get('BaseURL')}"
            elif xml.get('MPD').get('Period'):
                if type(xml.get('MPD').get('Period')) == list:
                    for i in xml.get('MPD').get('Period'):
                        if i.get('BaseURL') and i.get('BaseURL').startswith('http') == False:
                            i['BaseURL'] = f"{manifest_url.split('/web', 1)[0]}/{i.get('BaseURL')}"
                else:
                    if xml.get('MPD').get('Period').get('BaseURL').startswith('http') == False:
                        xml['MPD']['Period']['BaseURL'] = f"{manifest_url.split('/web', 1)[0]}/{xml.get('MPD').get('Period').get('BaseURL')}"
            return xmltodict.unparse(xml, pretty=True)
        except Exception as e:
            xbmc.log(f'exception = {e}')
            pass
    xbmcgui.Dialog().notification(w.addonname, f'No manifest url found for asset id {asset_id}.', xbmcgui.NOTIFICATION_ERROR)
    return


#
# LICENSE
#
def content_license(asset_id, license_headers, cdm_payload):
    if w.laUrls.get(asset_id):
        try:
            license_headers.pop('host') if 'host' in license_headers else license_headers.pop('Host')
            cdm_request = w.requests.exchange(w.laUrls[asset_id], data=cdm_payload, headers=license_headers)
            try:
                j = loads(cdm_request.data)
                if j.get('odata.error'):
                    xbmcgui.Dialog().notification(w.addonname, f"{j.get('odata.error').get('message', {}).get('value', 'unknown')}", xbmcgui.NOTIFICATION_ERROR)
                    raise Exception(f"ERROR: {j.get('odata.error').get('message', {}).get('value', 'unknown')}")
            except:
                pass
            return cdm_request.data
        except Exception as e:
            pass
    xbmcgui.Dialog().notification(w.addonname, f'No license url found for asset id {asset_id}.', xbmcgui.NOTIFICATION_ERROR)
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


if __name__ == '__main__':
    xbmcaddon.Addon().setSetting('startup', 'true')
    start()
