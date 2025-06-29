# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from urllib.parse import urlencode

from json import dumps
import xbmc
import xbmcgui
import xbmcplugin


class Items:


    def __init__(self, plugin):
        self.cache = True
        self.video = False
        self.plugin = plugin


    def list_items(self, focus=False, upd=False, epg=False):
        if self.video:
            xbmcplugin.setContent(self.plugin.addon_handle, self.plugin.content)
        xbmcplugin.endOfDirectory(self.plugin.addon_handle, cacheToDisc=self.cache, updateListing=upd)

        if self.plugin.force_view:
            view_id = self.plugin.view_id
            if self.video:
                view_id = self.plugin.view_id_videos
            if epg:
                view_id = self.plugin.view_id_epg
            xbmc.executebuiltin(f'Container.SetViewMode({view_id})')

        if focus:
            try:
                wnd = xbmcgui.Window(xbmcgui.getCurrentWindowId())
                wnd.getControl(wnd.getFocusId()).selectItem(focus)
            except:
                pass


    def add_item(self, item, epg=False):
        verify_age = item.get('verify_age', False)

        data = {
            'mode': item['mode'],
            'title': item['title'],
            'id': item.get('id', ''),
            'params': item.get('params', ''),
            'verify_age': verify_age,
            'dolby': True if len(item.get('dolby_config', [])) > 0 else False
        }

        art = {
            'thumb': item.get('thumb', self.plugin.addon_icon),
            'poster': item.get('thumb', self.plugin.addon_icon),
            'fanart': item.get('fanart', self.plugin.addon_fanart)
        }

        labels = {
            'title': item['title'],
            'plot': item.get('plot', item['title']),
            'premiered': item.get('date', ''),
            'episode': item.get('episode', 0)
        }

        if verify_age:
            labels['mpaa'] = 'PG-18'

        title = item['title']
        if epg == False and item.get('type', None) in ['CatchUp', 'Highlights', 'OnDemand'] and item.get('articlenav') != 'Show' and item.get('date', None):
            title = f"{title} ({item['date']})"
        listitem = xbmcgui.ListItem(title)
        listitem.setArt(art)
        listitem = self.plugin.set_videoinfo(listitem, labels)

        if 'play' in item['mode']:
            self.cache = False
            self.video = True
            folder = False
            listitem = self.plugin.set_streaminfo(listitem, {'duration': item.get('duration', 0)})
            listitem.setProperty('IsPlayable', item.get('playable', 'false'))
        else:
            folder = True

        if item.get('cm', None):
            listitem.addContextMenuItems(item['cm'])

        xbmcplugin.addDirectoryItem(self.plugin.addon_handle, self.plugin.build_url(data), listitem, folder)


    def play_item(self, item, name, art, context):
        # path = (
        #    f"http://"
        #    f"{self.plugin.get_setting('proxy_host') if self.plugin.get_setting('proxy_use') == 'true' else 'localhost'}"
        #    f":"
        #    f"{self.plugin.get_setting('proxy_port') if self.plugin.get_setting('proxy_use') == 'true' else 8014}"
        #    f"/api/"
        #    f"{item.AssetId}"
        #    f"/manifest"
        # )
        path = item.ManifestUrl
        resolved = True if path else False
        listitem = xbmcgui.ListItem()
        listitem.setContentLookup(False)
        listitem.setMimeType('application/dash+xml')
        listitem.setProperty('inputstream', 'inputstream.adaptive')
        license_headers = urlencode({
            'authorization': f"Bearer {self.plugin.get_setting('token')}",
            'content-type': 'application/octet-stream',
            'user-agent': self.plugin.get_user_agent()
        })
        license_url = (
            f"http://"
            f"{self.plugin.get_setting('proxy_host') if self.plugin.get_setting('proxy_use') == 'true' else 'localhost'}"
            f":"
            f"{self.plugin.get_setting('proxy_port') if self.plugin.get_setting('proxy_use') == 'true' else 8014}"
            f"/api/"
            f"{item.AssetId}"
            f"/license"
        )
        kodi_version = self.plugin.get_kodi_version()
        if kodi_version >= 22:
            drm_cfg = {
                'com.widevine.alpha': {
                    'license': {
                        'server_url': license_url,
                        'req_headers': license_headers
                    }
                }
            }
            listitem.setProperty('inputstream.adaptive.drm', dumps(drm_cfg))
        elif kodi_version == 21:
            drm_cfg = {
                'DRM KeySystem': 'com.widevine.alpha',
                'License server url': license_url,
                'License headers': license_headers
            }
            listitem.setProperty('inputstream.adaptive.drm_legacy', '|'.join(drm_cfg.values()))
        else:
            drm_cfg = {
                'License server url': license_url,
                'License headers': license_headers,
                'License post data': 'R{SSM}',
                'License response data': ''
            }
            listitem.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            listitem.setProperty('inputstream.adaptive.license_key', '|'.join(drm_cfg.values()))
            listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        if kodi_version >= 22:
            listitem.setProperty('inputstream.adaptive.common_headers', urlencode({'user-agent': self.plugin.get_user_agent()}))
        else:
            listitem.setProperty('inputstream.adaptive.manifest_headers', urlencode({'user-agent': self.plugin.get_user_agent()}))
            listitem.setProperty('inputstream.adaptive.stream_headers', urlencode({'user-agent': self.plugin.get_user_agent()}))
        if item.CdnToken:
            listitem.setProperty('inputstream.adaptive.stream_params', item.CdnToken)
        listitem.setProperty('inputstream.adaptive.chooser_bandwidth_max', self.plugin.get_max_bw())
        if context != 'play' and resolved:
            listitem.setArt(art)
            listitem = self.plugin.set_videoinfo(listitem, dict(title=name))
            if 'beginning' in context:
                listitem.setProperty('inputstream.adaptive.play_timeshift_buffer', 'true')
            player = xbmc.Player()
            player.play(path, listitem)
        else:
            listitem.setPath(path)
            xbmcplugin.setResolvedUrl(self.plugin.addon_handle, resolved, listitem)
