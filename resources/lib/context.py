# -*- coding: utf-8 -*-

from __future__ import unicode_literals


class Context:


    def __init__(self, plugin):
        self.cm = []
        self.plugin = plugin


    def epg_date(self):
        d = {
            'mode': 'epg',
            'id': 'date'
        }
        self.cm.append((self.plugin.get_string(30230), f'ActivateWindow(Videos, {self.plugin.build_url(d)})'))
        return self.cm


    def live(self, item):
        d = {
            'mode': 'play_context_from_beginning',
            'title': item['title'],
            'id': item.get('id', ''),
            'params': item.get('params', ''),
            'verify_age': item.get('verify_age', False),
            'art': {
                'thumb': item.get('thumb', self.plugin.addon_icon)
            }
        }
        self.cm.append((self.plugin.get_string(12021), f'RunPlugin({self.plugin.build_url(d)})'))
        return self.cm


    def highlights(self, item, mode):
        d = {
            'mode': mode,
            'title': item['title'],
            'id': item.get('id', ''),
            'params': item.get('params', '')
        }
        self.cm.append((self.plugin.get_string(30231), f'Container.Update({self.plugin.build_url(d)})'))
        return self.cm


    def related(self, cm_items):
        for i in cm_items:
            if(i['displaytypelabel']):
                type_ = i['displaytypelabel']
            else:
                type_ = self.plugin.get_resource(f"{i['displaytype'].lower()}Title", 'browseui_')
                if type_.get('found') == False:
                    type_ = self.plugin.get_resource(f"{i['displaytype'].lower()}", 'browseui_')
                if type_.get('found'):
                    type_ = type_.get('text')
                else:
                    type_ = i.get('displaytype')

            d = {
                'mode': 'play_context',
                'title': i['title'],
                'id': i.get('id', ''),
                'params': i.get('params', ''),
                'art': {
                    'thumb': i.get('thumb', self.plugin.addon_icon)
                }
            }
            self.cm.append((type_, f'RunPlugin({self.plugin.build_url(d)})'))
        return self.cm


    def goto(self, item):
        if item.get('sport', None):
            i = item['sport']
            d = {
                'mode': 'rails',
                'title': i['Title'],
                'id': 'sport',
                'params': i['Id']
            }
            self.cm.append((self.plugin.get_string(30214), f'Container.Update({self.plugin.build_url(d)})'))

        if item.get('competition', None):
            i = item['competition']
            d = {
                'mode': 'rails',
                'title': i['Title'],
                'id': 'competition',
                'params': i['Id']
            }
            self.cm.append((self.plugin.get_string(30215), f'Container.Update({self.plugin.build_url(d)})'))

        return self.cm
