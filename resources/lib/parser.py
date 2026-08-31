# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from .context import Context
from .entry import Entry
from .items import Items
from .playback import Playback
from .rails import Rails
from .tiles import Tiles


class Parser:


    def __init__(self, plugin, requests):
        self.plugin = plugin
        self.requests = requests
        self.items = Items(self.plugin)


    def rails_items(self, data, id_, entry_data):
        if id_ == 'home':
            epg = {
                'mode': 'epg',
                'title': self.plugin.get_resource('header_schedule').get('text'),
                'plot': None,
                'params': 'today'
            }
            epg['cm'] = Context(self.plugin).highlights(epg, mode='epg_highlights')
            self.items.add_item(epg, True)
            live_tv = {
                'mode': 'live-tv',
                'title': 'Live-TV',
                'plot': None
            }
            self.items.add_item(live_tv, False)
        if entry_data:
            for i in entry_data.get('includes', {}).get('Entry', []):
                item = Entry(self.plugin, i['fields']).item
                if item.get('id') and item.get('title'):
                    self.items.add_item(item)
        for i in data.get('Rails', []):
            item = Rails(self.plugin, i).item
            if item.get('id', '') == 'CatchUp':
                item['cm'] = Context(self.plugin).highlights(item, mode='rail_highlights')
            self.items.add_item(item)
        if id_ == 'home':
            search = {
                'mode': 'search',
                'title': self.plugin.get_resource('search_title').get('text'),
                'plot': None
            }
            self.plugin.build_url(search)
            self.items.add_item(search)
        self.items.list_items()


    def rail_items(self, data, mode, list_=True, epg_=False):
        for i in data.get('Tiles', []):
            item = Tiles(self.plugin, i).item
            if item.get('skip'):
                continue
            if 'highlights' in mode:
                if item['type'] == 'Highlights':
                    item['cm'] = Context(self.plugin).goto(item)
                    self.items.add_item(item, epg_)
                elif item.get('related', []):
                    for i in item['related']:
                        context = Context(self.plugin)
                        if i.get('Videos', []):
                            _item = Tiles(self.plugin, i).item
                            _item['cm'] = context.goto(_item)
                            self.items.add_item(_item, epg_)
            else:
                context = Context(self.plugin)
                if item.get('type') == 'Live' and item.get('is_linear') == False:
                    context.live(item)
                if item.get('related', []):
                    cm_items = []
                    for i in item['related']:
                        if i.get('Videos', []):
                            cm_items.append(Tiles(self.plugin, i).item)
                    context.related(cm_items)
                item['cm'] = context.goto(item)
                self.items.add_item(item, epg_)
        if list_:
            focus = data.get('StartPosition', False)
            self.items.list_items(focus)


    def epg_items(self, data, params, mode):
        update = False if params == 'today' else True
        if data.get('StartDate'):
            epg_date = self.plugin.epg_date(data['StartDate'])
            cm = Context(self.plugin).epg_date()


            def date_item(day):
                return {
                    'mode': mode,
                    'title': f"{self.plugin.get_resource(day.strftime('%A'), prefix='calendar_').get('text')} ({day.strftime(self.plugin.date_format)})",
                    'plot': f"{self.plugin.get_resource(epg_date.strftime('%A'), prefix='calendar_').get('text')} ({epg_date.strftime(self.plugin.date_format)})",
                    'params': day.strftime(self.plugin.date_format),
                    'cm': cm
                }


            self.items.add_item(date_item(self.plugin.get_prev_day(epg_date)))
            self.rail_items(data, mode, list_=False, epg_=True)
            self.items.add_item(date_item(self.plugin.get_next_day(epg_date)))
        self.items.list_items(upd=update, epg=True)


    def live_tv_items(self, data, mode, list_=True, epg_=False):
        for i in data.get('Tiles', []):
            item = Tiles(self.plugin, i).item
            if item.get('skip'):
                continue

            context = Context(self.plugin)
            if item.get('type') == 'Live' and item.get('is_linear') == False:
                context.live(item)
            if item.get('related', []):
                cm_items = []
                for i in item['related']:
                    if i.get('Videos', []):
                        cm_items.append(Tiles(self.plugin, i).item)
                context.related(cm_items)
            item['cm'] = context.goto(item)
            self.items.add_item(item, epg_)
        if list_:
            focus = data.get('StartPosition', False)
            self.items.list_items(focus)


    def search_items(self, data):
        for i in data.get('Results', []):
            if len(i.get('Tiles', [])) > 0:
                item = {
                    'mode': 'play',
                    'title': f"[COLOR gold]{self.plugin.get_resource(i['Id']).get('text')} ({len(i['Tiles'])})[/COLOR]",
                    'plot': None
                }
                self.items.add_item(item)
                self.rail_items(i, '', list_=False)

        self.items.list_items()


    def playback(self, data, name='', art=None, context=None, dolby=None):
        self.items.play_item(Playback(self.plugin, self.requests, data, context, dolby), name, art, context)
