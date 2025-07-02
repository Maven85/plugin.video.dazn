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


@route('/api/<asset_id>/manifesturl', method='POST')
def proxy_manifest_url(asset_id):
    manifest_url = loads(request.body.read()).get('url')
    response.set_header('content-type', 'application/json')
    w.mUrls.update({asset_id: manifest_url})
    return dumps({'success': True})


@route('/api/<asset_id>/licenseurl', method='POST')
def proxy_license_url(asset_id):
    license_url = loads(request.body.read()).get('url')
    response.set_header('content-type', 'application/json')
    w.laUrls.update({asset_id: license_url})
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
            manifest_base_url = manifest_url.rsplit('/', 1)[0]
            baseurl_found = False
            if xml.get('MPD').get('BaseURL'):
                baseurl_found = True
                if xml.get('MPD').get('BaseURL').startswith('http') == False:
                    xml['MPD']['BaseURL'] = build_url(manifest_base_url, xml.get('MPD').get('BaseURL'))
            elif xml.get('MPD').get('Period'):
                if type(xml.get('MPD').get('Period')) == list:
                    for i in xml.get('MPD').get('Period'):
                        if i.get('BaseURL'):
                            baseurl_found = True
                            if i.get('BaseURL').startswith('http') == False:
                                i['BaseURL'] = build_url(manifest_base_url, i.get('BaseURL'))
                elif xml.get('MPD').get('Period').get('BaseURL'):
                    baseurl_found = True
                    if xml.get('MPD').get('Period').get('BaseURL').startswith('http') == False:
                        xml['MPD']['Period']['BaseURL'] = build_url(manifest_base_url, xml.get('MPD').get('Period').get('BaseURL'))
            if baseurl_found == False and xml.get('MPD').get('Period'):
                if xml.get('MPD').get('Period').get('AdaptationSet') and type(xml.get('MPD').get('Period').get('AdaptationSet')) == list:
                    for i in xml.get('MPD').get('Period').get('AdaptationSet'):
                        if i.get('Representation'):
                            if type(i.get('Representation')) == list:
                                for j in i.get('Representation'):
                                    if j.get('SegmentTemplate'):
                                        if j.get('SegmentTemplate').get('@media') and j.get('SegmentTemplate').get('@media').startswith('http') == False:
                                            j.get('SegmentTemplate')['@media'] = build_url(manifest_base_url, j.get('SegmentTemplate')['@media'])
                                        if j.get('SegmentTemplate').get('@initialization') and j.get('SegmentTemplate').get('@initialization').startswith('http') == False:
                                            j.get('SegmentTemplate')['@initialization'] = build_url(manifest_base_url, j.get('SegmentTemplate')['@initialization'])
                            else:
                                if i.get('Representation').get('SegmentTemplate'):
                                    if i.get('Representation').get('SegmentTemplate').get('@media') and i.get('Representation').get('SegmentTemplate').get('@media').startswith('http') == False:
                                        i.get('Representation').get('SegmentTemplate')['@media'] = build_url(manifest_base_url, i.get('Representation').get('SegmentTemplate')['@media'])
                                    if i.get('Representation').get('SegmentTemplate').get('@initialization') and i.get('Representation').get('SegmentTemplate').get('@initialization').startswith('http') == False:
                                        i.get('Representation').get('SegmentTemplate')['@initialization'] = build_url(manifest_base_url, i.get('Representation').get('SegmentTemplate')['@initialization'])

            # xbmc.log(f'{xmltodict.unparse(xml, pretty=True)}')
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
            xbmc.log(f'exception = {e}')
            pass
    xbmcgui.Dialog().notification(w.addonname, f'No license url found for asset id {asset_id}.', xbmcgui.NOTIFICATION_ERROR)
    return


def build_url(manifest_base_url, relative_url):
    while relative_url.startswith('../'):
        manifest_base_url = manifest_base_url.rsplit('/', 1)[0]
        relative_url = relative_url.replace('../', '', 1)

    return f'{manifest_base_url}/{relative_url}'


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
