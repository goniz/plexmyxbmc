#!/usr/bin/python2
from threading import Lock
from urllib import urlencode
from urllib2 import Request, urlopen
from plexmyxbmc.xml import dict2xml_withheader
from plexmyxbmc.config import Configuration, default_system_config_path


class PlexSubscriber(object):
    def __init__(self, uuid, host, port=32400, command_id=0):
        self.uuid = uuid
        self.host = host
        self.port = port
        self.cmd_id = command_id

    def update(self, host=None, port=None, cmd_id=None):
        self.host = self.host if host is None else host
        self.port = self.port if port is None else port
        self.cmd_id = self.cmd_id if cmd_id is None else cmd_id
        return self

    def url(self, relative=''):
        base = 'http://%s:%d/' % (self.host, self.port)
        if relative:
            return base + relative + '/'
        return base


class PlexSubManager(object):
    def __init__(self, xbmc):
        self._xbmc = xbmc
        self._lock = Lock()
        self._subs = dict()
        self.last_key = ''
        self.config = Configuration(default_system_config_path())
        self._register_xbmc_callbacks()

    def __del__(self):
        self._xbmc.rpc.unregister('Application.OnVolumeChanged', self.notify)
        self._xbmc.rpc.unregister('Player.OnPause', self.notify)
        self._xbmc.rpc.unregister('Player.OnPlay', self.notify)

    def _register_xbmc_callbacks(self):
        self._xbmc.rpc.register('Application.OnVolumeChanged', self.notify)
        self._xbmc.rpc.register('Player.OnPause', self.notify)
        self._xbmc.rpc.register('Player.OnPlay', self.notify)

    def add(self, uuid, host, port, command_id):
        with self._lock:
            sub = self._subs.get(uuid, None)
            if sub:
                return sub.update(host, port, command_id)

            sub = PlexSubscriber(uuid, host, port, command_id)
            self._subs[uuid] = sub

    def remove(self, uuid):
        with self._lock:
            sub = self._subs[uuid]
            del self._subs[uuid]
            del sub

    def get(self, uuid, default=None):
        with self._lock:
            return self._subs.get(uuid, default)

    def notify(self):
        state = self._xbmc.get_players_state()
        headers = {
            'X-Plex-Client-Identifier': self.config['uuid'],
            'Access-Control-Expose-Headers': 'X-Plex-Client-Identifier',
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'text/xml'
        }
        with self._lock:
            for uuid in self._subs:
                sub = self._subs.get(uuid)
                state['commandID'] = sub.cmd_id
                xml = dict2xml_withheader(state, root_node='MediaContainer')
                url = sub.url('/:/timeline')
                post = Request(url, data=xml, headers=headers)
                resp = urlopen(post).read()
            #TODO: update the server too