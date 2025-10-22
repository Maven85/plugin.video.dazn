# -*- coding: utf-8 -*-

from __future__ import unicode_literals


class Entry:


    def __init__(self, plugin, i):
        self.item = {}
        self.plugin = plugin
        self.item['mode'] = 'rails'
        self.item['title'] = None
        self.item['id'] = None
        self.item['plot'] = None
        data = i.get('navigationInfo', {}).get('categoryData', {})
        if data:
            if data.get('railsQueryParam'):
                self.item['id'] = [i.split(':')[1] for i in data['railsQueryParam'].split(';') if i.startswith('ContentType')][0]
                self.item['params'] = data['railsQueryParam']
            if data.get('title'):
                self.item['title'] = data['title']
