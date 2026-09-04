# -*- coding: utf-8 -*-

from __future__ import unicode_literals


class Tiles:


    def __init__(self, plugin, i):
        self.item = {}
        self.plugin = plugin
        self.user_entitlements = self.plugin.user_entitlements()
        self.title = i['Title']
        self.subtitle = i.get('SubTitle', '')
        self.description = i['Description']
        self.start = self.plugin.utc2local(i.get('Start', ''))
        self.end = self.plugin.utc2local(i.get('End', ''))
        self.now = self.plugin.time_now()
        self.sport = i.get('Sport', [])
        self.competition = i.get('Competition', [])
        self.type = i.get('Type', '').replace('UpComing', 'ComingUp')
        self.nav = i.get('NavigateTo', '')
        self.related = i.get('Related', [])
        self.videos = i.get('Videos', [])
        self.verify_age = i.get('VerifyAge', False)
        self.is_linear = i.get('IsLinear', True)
        self.entitlement_ids = i.get('EntitlementIds', [])
        self.dolby_config = i.get('dolbyConfig', [])
        self.displaytype = i.get('DisplayType', '')
        self.displaytypelabel = i.get('DisplayTypeLabel', '')
        if self.nav:
            self.mode = 'rails'
            self.id = i['NavigateTo']
            self.params = i['NavParams']
        else:
            self.mode = 'play'
            self.id = i['AssetId']
            self.params = i['EventId']
        self.articlenav = i.get('ArticleNavigateTo', '')
        self.update_item(i)


    def add_duration(self):
        if 'ComingUp' in self.type:
            self.end = self.start
            self.start = self.now
        elif 'Live' in self.type:
            self.start = self.now
        if self.start and self.end:
            if not self.plugin.hide_total_playtime:
                self.item['duration'] = self.plugin.timedelta_total_seconds(self.plugin.time_stamp(self.end) - self.plugin.time_stamp(self.start))


    def add_thumb(self, i):
        image = i.get('PortraitImage', '') if i.get('PortraitImage') and i.get('Title', '').strip() == '' else i.get('Image')
        if image:
            if self.type == 'Navigation':
                if image['ImageType'] == "image-portrait":
                    self.item['thumb'] = f"{self.plugin.api_img_base}/{image['Id']}/fill/none/top/none/85/334/501/{image['ImageMimeType']}"
                else:
                    self.item['thumb'] = f"{self.plugin.api_img_base}/{image['Id']}/fill/none/top/none/85/512/512/{image['ImageMimeType']}"
            else:
                self.item['thumb'] = f"{self.plugin.api_img_base}/{image['Id']}/fill/none/top/none/85/720/404/{image['ImageMimeType']}"
            self.item['fanart'] = f"{self.plugin.api_img_base}/{image['Id']}/fill/none/top/none/85/1280/720/{image['ImageMimeType']}"
        background = i.get('BackgroundImage', '')
        if background:
            self.item['fanart'] = f"{self.plugin.api_img_base}/{background['Id']}/fill/none/top/none/85/1280/720/{background['ImageMimeType']}"
        promo = i.get('PromoImage', '')
        if promo:
            self.item['thumb'] = f"{self.plugin.api_img_base}/{promo['Id']}/fill/none/top/none/85/720/270/{promo['ImageMimeType']}"


    def update_item(self, i):
        self.item['mode'] = self.mode
        self.item['title'] = self.title
        self.item['plot'] = self.description if self.description != 'OTHER' else ''
        self.item['id'] = self.id
        self.item['type'] = self.type
        self.item['verify_age'] = self.verify_age
        self.item['is_linear'] = self.is_linear
        self.item['entitlement_ids'] = self.entitlement_ids
        self.item['dolby_config'] = self.dolby_config
        self.item['displaytype'] = self.displaytype
        self.item['displaytypelabel'] = self.displaytypelabel

        if self.params:
            self.item['params'] = self.params

        if self.videos:
            self.item['playable'] = 'true'

        if self.start:
            self.item['date'] = self.start[:10]

        if 'Epg' in i.get('Id', ''):
            if self.competition:
                competition = self.competition['Title']
            if self.sport:
                sport = self.sport['Title']
            time_ = self.start[11:][:5]
            if self.type == 'Live':
                self.item['title'] = f'[COLOR red]{time_}[/COLOR] [COLOR blue]{sport}[/COLOR] {self.title} [COLOR blue]{competition}[/COLOR]'
            else:
                self.item['title'] = f'{time_} [COLOR blue]{sport}[/COLOR] {self.title} [COLOR blue]{competition}[/COLOR]'
        elif (self.type == 'ComingUp' or 'Scheduled' in i.get('Id', '')) or (self.type == 'Highlights' or self.type == 'Condensed'):
            if self.type == 'ComingUp':
                day = self.plugin.days(self.type, self.now, self.start)
                sub_title = f'{day} {self.start[11:][:5]}'
            else:
                sub_title = self.plugin.get_resource(f'{self.type[0].lower()}{self.type[1:]}Title', 'browseui_').get('text')
                if sub_title.endswith('Title'):
                    sub_title = self.type
            if sub_title not in self.title:
                self.item['title'] = f'{self.title} ({sub_title})'

        if self.displaytypelabel:
            self.item['title'] = f"{self.item['title']} | {self.displaytypelabel}"

        if 'Epg' not in i.get('Id', '') and self.type in ['CatchUp', 'Highlights', 'OnDemand'] and self.articlenav != 'Show' and self.item.get('date'):
            self.item['title'] = f"{self.item['title']} ({self.item['date']})"

        if self.entitlement_ids:
            entitlements_found = [entitlement_id for entitlement_id in self.entitlement_ids if entitlement_id in self.user_entitlements]
            if len(entitlements_found) == 0:
                if self.plugin.only_playable_content():
                    self.item['skip'] = True
                self.item['title'] = f"[COLOR orange]{self.item['title']}[/COLOR]"

        self.item['related'] = self.related
        self.item['sport'] = self.sport
        self.item['competition'] = self.competition
        self.item['articlenav'] = self.articlenav

        self.add_thumb(i)
        self.add_duration()
