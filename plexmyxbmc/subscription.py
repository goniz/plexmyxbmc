#!/usr/bin/python2
from threading import Lock


class PlexSubscriber(object):
    def __init__(self, uuid, host, port=32400, command_id=0):
        self._uuid = uuid
        self._host = host
        self._port = port
        self._cmd_id = command_id

    def update(self, host=None, port=None, cmd_id=None):
        self._host = self._host if host is None else host
        self._port = self._port if port is None else port
        self._cmd_id = self._cmd_id if cmd_id is None else cmd_id
        return self


class PlexSubManager(object):
    def __init__(self):
        self._lock = Lock()
        self._subs = dict()

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