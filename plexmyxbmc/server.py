#!/usr/bin/python2


class PlexMedia(object):
    pass


class PlexServer(object):
    def __init__(self, address, port):
        self._address = address
        self._port = port

    def get_media(self, key):
        return None