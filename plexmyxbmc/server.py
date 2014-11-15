#!/usr/bin/python2

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound


class MyPlexServer(object):
    def __init__(self, myplex_server):
        self._server = myplex_server

    def connect_local(self):
        server = self._server
        addresses = sorted(server.localAddresses)
        for address in addresses:
            try:
                # port mapping may not tell the truth, trying this before the mapped port
                return PlexServer(address, port=32400, token=server.accessToken)
            except NotFound:
                pass

            try:
                return PlexServer(address, server.port, token=server.accessToken)
            except NotFound:
                continue
        return None

    def connect_external(self):
        server = self._server
        try:
            return PlexServer(server.address, server.port, server.accessToken)
        except NotFound:
            return None

    def connect(self):
        local = self.connect_local()
        if local:
            return local

        external = self.connect_external()
        if external:
            return external

        raise NotFound()

    def connect_nothrow(self):
        try:
            return self.connect()
        except NotFound:
            return None

    def __str__(self):
        return str(self._server)