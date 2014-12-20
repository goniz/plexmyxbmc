#!/usr/bin/python2
from threading import Lock, Event
import requests
import socket
import plexapi
from plexapi.myplex import MyPlexUser
from plexapi.exceptions import NotFound

from plexmyxbmc.config import get_config
from plexmyxbmc.registration import ClientRegistration, ClientInfo
from plexmyxbmc.xbmc_rpc import XbmcJSONRPC
from plexmyxbmc.xbmc import XBMCPlexPlayer
from plexmyxbmc.server import MyPlexServer
from plexmyxbmc.client_api import ThreadedAPIServer, PlexClientHandler
from plexmyxbmc.subscription import PlexSubManager
from plexmyxbmc.threads import ThreadMonitor
from plexmyxbmc.event_processing import PlexEventsManager
from plexmyxbmc.log import get_logger
from plexmyxbmc.sync import PlexSyncManager, PlexStorageManager


class PlexClient(object):
    def __init__(self):
        self.config = get_config()
        self.config.verify()
        self._logger = get_logger(self.__class__.__name__)
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
        self.xbmc.notify('Plex', 'Master server is {0}'.format(self.config['plex_server']))
        try:
            self._server = self.get_coolest_server()
            self.xbmc.notify('Plex', 'using PMS %s' % self._server.friendlyName)
        except:
            self.xbmc.notify('Plex', 'failed to connect to master server')
            raise

        self.sub_mgr = PlexSubManager(self)
        self.event_mgr = PlexEventsManager(self)
        self.httpd = ThreadedAPIServer(self, ('', self.config['port']), PlexClientHandler)
        self.httpd.allow_reuse_address = True
        self.storage_mgr = PlexStorageManager(self, self.config['local_sync_cache'])
        self.sync_mgr = PlexSyncManager(self, self.storage_mgr)
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
        self.event_mgr.start()
        self.sync_mgr.start()
        self.publish_resources()
        self._keep_running.set()
        try:
            self._serve_loop()
        except KeyboardInterrupt:
            self._keep_running.clear()

    def stop(self):
        self._keep_running.clear()
        self.registration_thread.stop()
        self.event_mgr.stop()
        self._xbmc_rpc.stop()
        self.sync_mgr.stop()
        # self._monitor.stop()

    def join(self):
        if self.registration_thread.isAlive():
            self.registration_thread.join()
        if self._monitor.isAlive():
            self._monitor.join()
        if self.event_mgr.isAlive():
            self.event_mgr.join()
        if self.sync_mgr.isAlive():
            self.sync_mgr.join()

    def get_coolest_server(self):
        servers = self._user.servers()
        self._logger.info('MyPlex registered servers: %s', ', '.join(map(lambda x: x.name, servers)))

        master_server = self.config.get('plex_server', '')
        for server in servers:
            if server.name != master_server:
                continue

            return MyPlexServer(server).connect()
        raise NotFound('could not find master server {0}'.format(master_server))

    def authenticated_url(self, url):
        """

        :type url: str
        """
        url = self._server.url(url) if url.startswith('/') else url
        token = 'X-Plex-Token=' + self._user.authenticationToken
        return url + ('&' if '?' in url else '?') + token

    @property
    def headers(self):
        plex_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            'Access-Control-Expose-Headers': 'X-Plex-Client-Identifier',
            "Access-Control-Allow-Origin": "*",
            "X-Plex-Device": "PC",
            "X-Plex-Username": self._user.username,
            "X-Plex-Token": self._user.authenticationToken,
        }
        plex_headers.update(plexapi.BASE_HEADERS)
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

    @property
    def local_address(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('www.google.com', 80))
        addr, port = s.getsockname()
        s.close()
        return addr, self.config['port']

    def publish_resources(self):
        addr, port = self.local_address
        connection = 'http://{0}:{1}/'.format(addr, port)
        data = {'Connection[][uri]': connection}
        url = 'https://plex.tv/devices/{0}'.format(self.config['uuid'])
        resp = requests.put(url, data=data, headers=self.headers)
        if resp.status_code == 200:
            self._logger.info('published device resources to plex.tv successfully')
        else:
            self._logger.warn('failed to publish devices resources to plex.tv')