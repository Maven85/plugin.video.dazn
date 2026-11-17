# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from resources.lib.proxy import Proxy
import xbmc, xbmcaddon


class SettingsMonitor(xbmc.Monitor):

    def __init__(self):
        super().__init__()
        self.api_manual = xbmcaddon.Addon().getSetting('api_manual')

    def onSettingsChanged(self):
        # Switching between manual and automatic API endpoints must resolve them again.
        api_manual = xbmcaddon.Addon().getSetting('api_manual')
        if api_manual != self.api_manual:
            self.api_manual = api_manual
            xbmcaddon.Addon().setSetting('startup', 'true')


if __name__ == '__main__':
    xbmcaddon.Addon().setSetting('startup', 'true')

    proxy = Proxy()
    proxy.start()

    monitor = SettingsMonitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break

    proxy.stop()
