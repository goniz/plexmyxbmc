#!/usr/bin/python2
import time
from threading import Lock, Event, Thread
from urllib import urlencode
from urllib2 import Request, urlopen

from plexmyxbmc.xml import dict2xml_withheader
from plexmyxbmc.config import get_config
from plexmyxbmc.xbmc import PlayerType
from plexmyxbmc.log import get_logger


class PlexSubscriber(object):
    def __init__(self, uuid, host, port=32400, command_id=0):
        self.uuid = uuid
        self.host = host
        self.port = port
        self.cmd_id = command_id
        self.headers = dict()

    def update(self, host=None, port=None, cmd_id=None):
        self.host = self.host if host is None else host
        self.port = self.port if port is None else port
        self.cmd_id = self.cmd_id if cmd_id is None else cmd_id
        return self

    def url(self, relative=''):
        base = 'http://%s:%d/' % (self.host, self.port)
        if relative:
            return base + relative.lstrip('/')
        return base


class PlexSubManager(object):
    def __init__(self, plex):
        self._plex = plex
        self._xbmc = self._plex.xbmc
        self._lock = Lock()
        self._subs = dict()
        self._is_playing = Event()
        self.config = get_config()
        self._logger = get_logger(self.__class__.__name__)
        self._register_xbmc_callbacks()

    def __del__(self):
        self._xbmc.rpc.unregister('Application.OnVolumeChanged', self.notify_all)
        self._xbmc.rpc.unregister('Player.OnPause', self.notify_all)
        self._xbmc.rpc.unregister('Player.OnPlay', self._notify_all_blocking_loop)
        self._xbmc.rpc.unregister('Player.OnStop', self._notify_playback_stopped)

    def _register_xbmc_callbacks(self):
        self._xbmc.rpc.register('Application.OnVolumeChanged', self.notify_all)
        self._xbmc.rpc.register('Player.OnPause', self.notify_all)
        self._xbmc.rpc.register('Player.OnPlay', self._notify_all_blocking_loop)
        self._xbmc.rpc.register('Player.OnStop', self._notify_playback_stopped)

    def _notify_all_blocking_loop(self, msg=None):
        if self._is_playing.is_set() is True:
            # there is already another annoying thread running!
            return

        self._is_playing.set()
        self._logger.debug('Annoying thread started!!')
        # each callback is called with its own `disposable` thread
        # we will abuse this and block it untill playback is stopped
        while self._is_playing.is_set() is True:
            self.notify_all(msg)
            time.sleep(1)
        self._logger.debug('Annoying thread stopped!')

    def _notify_playback_stopped(self, msg=None):
        self._is_playing.clear()
        self.notify_all(msg)

    def notify_all(self, msg=None):
        self.notify_server()
        self.notify_subscribers()

    def notify_all_delayed(self, delay_secs=1):
        def __notify_delayed(submgr, delay):
            time.sleep(delay)
            submgr.notify_all()

        tname = 'DelayedNotify-%d' % (delay_secs, )
        args = (self, delay_secs)
        Thread(name=tname, target=__notify_delayed, args=args).start()

    def add(self, uuid, host, port, command_id, headers=None):
        with self._lock:
            sub = self._subs.get(uuid, None)
            if sub:
                if headers:
                    sub.headers.update(headers)
                return sub.update(host, port, command_id)

            sub = PlexSubscriber(uuid, host, port, command_id)
            if headers:
                sub.headers.update(headers)
            name = sub.headers.get('x-plex-device-name', '')
            platform = sub.headers.get('x-plex-platform', '')
            self._plex.xbmc.notify('Plex', '%s (%s) Connected' % (name, platform))

            self._subs[uuid] = sub
            return sub

    def remove(self, uuid):
        with self._lock:
            sub = self._subs[uuid]
            name = sub.headers.get('x-plex-device-name', '')
            self._plex.xbmc.notify('Plex', '%s disconnected' % (name, ))
            del self._subs[uuid]
            del sub

    def get(self, uuid, default=None):
        with self._lock:
            return self._subs.get(uuid, default)

    def notify_server(self):
        players = self._xbmc.get_active_players()
        if players is None:
            return

        for player in players:
            player_id = int(player['playerid'])
            player_type = PlayerType(player['type'])
            timeline = self._xbmc.get_timeline(player_id, player_type)
            uri = '/:/timeline?' + urlencode(timeline)
            url = self._plex.authenticated_url(uri)
            try:
                get = Request(url, headers=self._plex.headers)
                resp = urlopen(get).read()
            except Exception as e:
                self._logger.warn('caught %s while getting to %s' % (str(e), url))

    def notify_subscribers(self):
        state = self._xbmc.get_players_state()
        with self._lock:
            for uuid in self._subs:
                sub = self._subs.get(uuid)
                state['commandID'] = sub.cmd_id
                xml = dict2xml_withheader(state, root_node='MediaContainer')
                url = sub.url('/:/timeline')
                try:
                    post = Request(url, data=xml, headers=self._plex.headers)
                    resp = urlopen(post).read()
                except Exception as e:
                    self._logger.warn('caught %s while posting to %s' % (str(e), url))