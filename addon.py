# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from json import loads
from sys import argv, exit
from urllib.parse import parse_qs

from xbmc import executebuiltin
import xbmcaddon

from resources.lib.api import Request
from resources.lib.client import Client
from resources.lib.common import Common
from resources.lib.credential import Credential
from resources.lib.parser import Parser

handle_ = int(argv[1])
url_ = argv[0]
addon_ = xbmcaddon.Addon()

plugin = Common(
    addon=addon_,
    addon_handle=handle_,
    addon_url=url_
)
requests = Request(addon_, plugin.get_setting('proxy_use') == 'true')
credential = Credential(plugin)
client = Client(plugin, credential, requests)
parser = Parser(plugin, requests)


def router(args):
    plugin.log(f'args = {args}')
    mode = args.get('mode', ['rails'])[0]
    title = args.get('title', [''])[0]
    id_ = args.get('id', ['home'])[0]
    params = args.get('params', [''])[0]
    verify_age = True if args.get('verify_age', [''])[0] == 'True' else False
    dolby = True if args.get('dolby', [''])[0] == 'True' else False
    searchterm = args.get('searchterm', [''])[0]
    if mode == 'rails':
        entries = None
        content_id = 'Home' if id_.lower() == 'home' else None
        if params and id_.lower() == 'competition':
                content_id = [i.split(':')[1] for i in params.split(';') if i.startswith('ContentType')][0] + ':' + [i.split(':')[1] for i in params.split(';') if i.startswith('ContentId')][0]
        if content_id:
            entries = client.entries(content_id, 'CatalogueBanners')
        parser.rails_items(client.rails(id_, params), id_, entries)
    elif 'rail' in mode:
        parser.rail_items(client.rail(id_, params), mode)
    elif 'epg' in mode:
        if id_ == 'date':
            date = plugin.get_date()
        else:
            date = plugin.get_today() if params == 'today' else params
        parser.epg_items(client.epg(date), params, mode)
    elif mode == 'play':
        parser.playback(client.playback(id_, plugin.youth_protection_pin(verify_age)), context=mode, dolby=dolby)
    elif 'play_context' in mode:
        art = loads(args.get('art', [''])[0].replace('\'', '"'))
        parser.playback(client.playback(id_, plugin.youth_protection_pin(verify_age)), title, art, mode)
    elif 'search' in mode:
        if searchterm == '':
            searchterm = plugin.dialog_search()
            if searchterm == '':
                exit(0)
            executebuiltin(f'Container.Update({plugin.build_url(dict(mode=mode,searchterm=searchterm))}, replace)')
        else:
            items = client.search(searchterm)
            parser.search_items(items)
    elif mode == 'logout':
        if plugin.logout():
            credential.clear_credentials()
            client.signOut()
            exit(0)
    elif mode == 'is_settings':
        plugin.open_is_settings()
    else:
        exit(0)


if __name__ == '__main__':
    if plugin.get_setting('save_login') == 'false' and credential.has_credentials():
        credential.clear_credentials()

    paramstring = argv[2][1:]
    args = dict(parse_qs(paramstring))

    if args.get('mode', ['rails'])[0] != 'logout' and (plugin.startup or not client.TOKEN):
        startup_data = client.initStartupData()
        endpoint_dict = plugin.init_api_endpoints(startup_data.get('ServiceDictionary'))
        client.initApiEndpoints(endpoint_dict)
        region = client.initRegion(startup_data)
        playable = plugin.start_is_helper()
        client.DEVICE_ID = plugin.uniq_id()
        if client.DEVICE_ID and playable:
            client.startUp(region)
            if client.TOKEN:
                plugin.set_setting('startup', 'false')
                client.userProfile()
        else:
            client.TOKEN = ''

    if client.TOKEN and client.DEVICE_ID:
        router(args)
    else:
        exit(0)
