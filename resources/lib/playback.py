# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from base64 import b64encode
from urllib.parse import quote_plus


class Playback:


    def __init__(self, plugin, requests, data):
        self.plugin = plugin
        self.requests = requests
        self.ManifestUrl = ''
        self.LaUrl = ''
        self.CdnToken = ''
        self.Cdns = []
        self.AssetId = ''
        self.get_detail(data.get('Asset', {}), data.get('PlaybackPrecision', {}), data.get('PlaybackDetails', []))


    def clean_name(self, cdns):
        return [cdn.replace('live', '').replace('vod', '') for cdn in cdns]


    def get_detail(self, asset, precision, details):
        if asset.get('Id'):
            self.AssetId = asset.get('Id')
        if precision.get('Cdns'):
            self.Cdns = self.clean_name(precision['Cdns'])
        if self.Cdns:
            cdn = self.plugin.get_cdn(self.Cdns)
            if cdn:
                self.parse_detail(details, cdn)
            else:
                for i in self.Cdns:
                    self.parse_detail(details, i)
                    if self.ManifestUrl:
                        break
        if not self.ManifestUrl:
            self.parse_detail(details)


    def parse_detail(self, details, cdn=''):
        for i in details:
            if cdn == self.clean_name([i['CdnName']])[0] or not cdn:
                url = i['ManifestUrl']
                if i.get('CdnToken'):
                    url = '{}{}{}={}'.format(url, '&' if url.find('?') > -1 else '?', i['CdnToken']['Name'], quote_plus(i['CdnToken']['Value']))
                res = self.requests.exchange(url, headers={'user-agent': self.plugin.get_user_agent()}, method='HEAD')
                if res.status == 200 and self.plugin.get_dict_value(res.headers, 'content-type').startswith('application/dash+xml'):
                    self.ManifestUrl = url
                    self.LaUrl = i['LaUrl']
                    if self.plugin.get_setting('proxy_use') == 'true':
                        self.requests.exchange(
                                'http://{}:{}/api/{}/{}/licenseurl'.format(
                                    self.plugin.get_setting('proxy_host'),
                                    self.plugin.get_setting('proxy_port'),
                                    self.AssetId,
                                    b64encode(self.LaUrl.encode('utf-8')).decode('utf-8')),
                                headers={'user-agent': self.plugin.get_user_agent()},
                                method='POST'
                        )
                    if i.get('CdnToken'):
                        self.CdnToken = '{}={}'.format(i['CdnToken']['Name'], quote_plus(i['CdnToken']['Value']))
                    break
