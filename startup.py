# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import xbmcaddon

addon = xbmcaddon.Addon()

if __name__ == '__main__':
    addon.setSetting('startup', 'true')
