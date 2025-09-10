# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from resources.lib.proxy import Proxy
import xbmc, xbmcaddon

if __name__ == '__main__':
    xbmcaddon.Addon().setSetting('startup', 'true')

    proxy = Proxy()
    proxy.start()

    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break

    proxy.stop()
