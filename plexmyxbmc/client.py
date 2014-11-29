#!/usr/bin/python2
from threading import Lock, Event
from plexapi.myplex import MyPlexUser
from plexapi.exceptions import NotFound

import plexmyxbmc
from plexmyxbmc.config import get_config
from plexmyxbmc.registration import ClientRegistration, ClientInfo
from plexmyxbmc.xbmc_rpc import XbmcJSONRPC
from plexmyxbmc.xbmc import XBMCPlexPlayer
from plexmyxbmc.server import MyPlexServer
from plexmyxbmc.client_api import ThreadedAPIServer, PlexClientHandler
from plexmyxbmc.subscription import PlexSubManager
from plexmyxbmc.threads import ThreadMonitor


class PlexClient(object):
    def __init__(self):
        self.config = get_config()
        self.config.verify()
        self.c_info = ClientInfo.from_config(self.config)
        self._monitor = ThreadMonitor()
        # self._monitor.start()
        self.registration_thread = ClientRegistration(self.c_info)
        # this call will block if XBMC is unresponsive, will resume when XBMC is UP
        self._xbmc_rpc = XbmcJSONRPC(self.config['xbmc_host'], self.config['xbmc_port']).wait()
        self._xbmc = XBMCPlexPlayer(self._xbmc_rpc, self)
        self.xbmc.notify('Plex', 'PlexMyXBMC Connected')
        self._user = MyPlexUser(self.config['plex_username'], self.config['plex_password'])
        self.xbmc.notify('Plex', 'Logged in as "%s"' % self.config['plex_username'])
        self.xbmc.notify('Plex', 'Searching for connectable servers...', duration=10*1000)
        self._server = self.get_coolest_server()
        self.xbmc.notify('Plex', 'using PMS %s' % self._server.friendlyName)
        self.sub_mgr = PlexSubManager(self)
        self.httpd = ThreadedAPIServer(('', self.config['port']), PlexClientHandler)
        self.httpd.allow_reuse_address = True
        self.httpd.plex = self
        self._keep_running = Event()
        self._keep_running.clear()
        self._lock = Lock()

    def __del__(self):
        self.stop()
        self.join()

    def _serve_loop(self):
        while self._keep_running.is_set() is True:
            self.httpd.handle_request()

    def serve(self):
        self.registration_thread.start()
        self._keep_running.set()
        try:
            self._serve_loop()
        except KeyboardInterrupt:
            self._keep_running.clear()

    def stop(self):
        self._keep_running.clear()
        self.registration_thread.stop()
        self._xbmc_rpc.stop()
        # self._monitor.stop()

    def join(self):
        if self.registration_thread.isAlive():
            self.registration_thread.join()
        if self._monitor.isAlive():
            self._monitor.join()

    def get_coolest_server(self):
        servers = self._user.servers()
        servers = map(MyPlexServer, servers)
        print 'MyPlex registered servers'
        print '\t\n'.join(map(str, servers))

        local_servers = map(lambda x: x.connect_local(), servers)
        local_servers = filter(None, local_servers)
        if local_servers:
            print 'Found %d local Plex Media Servers' % len(local_servers)
            print 'Chose first local server:', local_servers[0].friendlyName
            return local_servers[0]

        external_servers = map(lambda x: x.connect_external(), servers)
        external_servers = filter(None, external_servers)
        if external_servers:
            print 'Found %d external Plex Media Servers' % len(external_servers)
            print 'Chose first external server:', external_servers[0].friendlyName
            return external_servers[0]

        raise NotFound()

    def authenticated_url(self, url):
        url = self._server.url(url) if url.startswith('/') else url
        token = 'X-Plex-Token=' + self._user.authenticationToken
        return url + ('&' if '?' in url else '?') + token

    @property
    def headers(self):
        plex_headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Access-Control-Allow-Origin": "*",
            "X-Plex-Version": plexmyxbmc.__version__,
            "X-Plex-Client-Identifier": self.config['uuid'],
            "X-Plex-Provides": "player",
            "X-Plex-Product": "PlexMyXBMC",
            "X-Plex-Device-Name": self.config['name'],
            "X-Plex-Platform": "Linux",
            "X-Plex-Model": "PlexMyXBMC",
            "X-Plex-Device": "PC",
            "X-Plex-Username": self._user.username,
            "X-Plex-Token": self._user.authenticationToken,
        }
        return plex_headers

    @property
    def server(self):
        return self._server

    @property
    def user(self):
        return self._user

    @property
    def xbmc(self):
        return self._xbmc

