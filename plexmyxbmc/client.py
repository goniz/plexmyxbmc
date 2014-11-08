#!/usr/bin/python2
from threading import Lock
from plexapi.myplex import MyPlexUser

from plexmyxbmc.config import Configuration, default_system_config_path
from plexmyxbmc.registration import ClientRegistration, ClientInfo
from plexmyxbmc.xbmc_rpc import XbmcRPC, XBMC
from plexmyxbmc.discovery import PlexGDM
from plexmyxbmc.client_api import ThreadedAPIServer, PlexClientHandler


class PlexClient(object):
    def __init__(self):
        self.config = Configuration(default_system_config_path())
        self.config.verify()
        self.c_info = ClientInfo.from_config(self.config)
        self.registration_thread = ClientRegistration(self.c_info)
        self._xbmc_rpc = XbmcRPC(
            self.config['xbmc_host'], self.config['xbmc_port'],
            self.config['xbmc_username'], self.config['xbmc_password']
        )
        self._xbmc = XBMC(self._xbmc_rpc)
        self._user = MyPlexUser(self.config['plex_username'], self.config['plex_password'])
        self._server = self.get_coolest_server()
        self.httpd = ThreadedAPIServer(('', self.config['port']), PlexClientHandler)
        self.httpd.allow_reuse_address = True
        self.httpd.plex = self
        #self.httpd.timeout = 5
        self._keep_running = False
        self._last_key = None
        self._lock = Lock()

    def __del__(self):
        self.stop()
        self.join()

    def _serve_loop(self):
        while self._keep_running is True:
            self.httpd.handle_request()

    def serve(self):
        self.registration_thread.start()
        self._keep_running = True
        try:
            self._serve_loop()
        except KeyboardInterrupt:
            self._keep_running = False

    def stop(self):
        self._keep_running = False
        self.registration_thread.stop()

    def join(self):
        self.registration_thread.join()

    def get_coolest_server(self):
        gdm = PlexGDM(self._user)
        servers = gdm.discover()
        print 'Found %d Plex Media Servers on LAN, chose %s' % (
            len(servers),
            servers[0].friendlyName
        )
        return servers[0]

    @property
    def server(self):
        return self._server

    @property
    def user(self):
        return self._user

    @property
    def xbmc(self):
        return self._xbmc

    @property
    def last_key(self):
        with self._lock:
            return self._last_key

    @last_key.setter
    def last_key(self, key):
        with self._lock:
            self._last_key = key
