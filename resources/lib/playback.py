# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from base64 import b64encode
from urllib.parse import quote_plus


class Playback:


    def __init__(self, plugin, requests, data, context, dolby):
        self.plugin = plugin
        self.requests = requests

        self.context = context
        self.dolby = dolby

        self.ManifestUrl = ''
        self.LaUrl = ''
        self.CdnToken = ''
        self.Cdns = []
        self.AssetId = ''
        self.get_detail(data.get('Asset', {}), data.get('PlaybackPrecision', {}), data.get('PlaybackDetails', []))


    def clean_name(self, cdns):
        return [cdn.replace('live', '').replace('vod', '').rstrip('-') for cdn in cdns]


    def get_detail(self, asset, precision, details):
        if asset.get('Id'):
            self.AssetId = asset.get('Id')
        if precision.get('Cdns'):
            self.Cdns = self.clean_name(precision['Cdns'])
        if self.Cdns:
            cdn = self.plugin.get_cdn(self.Cdns)
            if cdn is not None:
                self.parse_detail(details, cdn)


    def parse_detail(self, details, cdn):
        for i in details:
            if cdn == self.clean_name([i['CdnName']])[0] or not cdn:
                manifestUrl = None
                if i.get('DaiVod') and i.get('DaiVod').get('ContentSourceId') and i.get('DaiVod').get('VideoId'):
                    contentSourceId = i.get('DaiVod').get('ContentSourceId')
                    videoId = i.get('DaiVod').get('VideoId')
                    url = f'https://dai.google.com/ondemand/dash/content/{contentSourceId}/vid/{videoId}/streams'
                    res = self.requests.exchange(url, headers={'user-agent': self.plugin.get_user_agent()}, method='POST')
                    if res.status == 201:
                        manifestUrl = res.json().get('stream_manifest')
                elif self.context == 'play' and self.dolby == True and i.get('DaiLive') and i.get('DaiLive').get('LiveStreamEventCode') and i.get('DaiLive').get('DaiDlid'):
                    liveStreamEventCode = i.get('DaiLive').get('LiveStreamEventCode')
                    url = f'https://dai.google.com/ssai/event/{liveStreamEventCode}/streams'
                    data = {'dai-dlid': i.get('DaiLive').get('DaiDlid')}
                    res = self.requests.exchange(url, headers={'user-agent': self.plugin.get_user_agent()}, fields=data)
                    if res.status == 201:
                        manifestUrl = res.json().get('stream_manifest')
                if manifestUrl is None:
                    url = i['ManifestUrl']
                    if i.get('CdnToken'):
                        url = f"{url}{'&' if url.find('?') > -1 else '?'}{i['CdnToken']['Name']}={quote_plus(i['CdnToken']['Value'])}"
                    res = self.requests.exchange(url, headers={'user-agent': self.plugin.get_user_agent()}, method='HEAD')
                    if res.status == 200 and self.plugin.get_dict_value(res.headers, 'content-type').startswith('application/dash+xml'):
                        manifestUrl = url
                if manifestUrl:
                    self.ManifestUrl = manifestUrl
                    self.LaUrl = i['LaUrl']
                    proxy_base_url = (
                        f"http://"
                        f"{self.plugin.get_setting('proxy_host') if self.plugin.get_setting('proxy_use') == 'true' else 'localhost'}"
                        f":"
                        f"{self.plugin.get_setting('proxy_port') if self.plugin.get_setting('proxy_use') == 'true' else 8014}"
                        f"/api/"
                        f"{self.AssetId}"
                    )
                    self.requests.exchange(
                        f"{proxy_base_url}/manifesturl",
                        headers={'user-agent': self.plugin.get_user_agent()},
                        json={'url': self.ManifestUrl},
                        method='POST'
                    )
                    self.requests.exchange(
                        f"{proxy_base_url}/licenseurl",
                        headers={'user-agent': self.plugin.get_user_agent()},
                        json={'url': self.LaUrl},
                        method='POST'
                    )
                    if i.get('CdnToken'):
                        self.CdnToken = f"{i['CdnToken']['Name']}={quote_plus(i['CdnToken']['Value'])}"
                    break
