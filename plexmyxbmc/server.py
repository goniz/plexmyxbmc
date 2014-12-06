#!/usr/bin/python2

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
from plexmyxbmc.log import get_logger


class MyPlexServer(object):
    def __init__(self, myplex_server):
        self._server = myplex_server
        self.friendlyName = self._server.name
        self.name = self._server.name
        lname = '%s-%s' % (self.__class__.__name__, self._server.name)
        self._logger = get_logger(lname)

    def connect_local(self):
        server = self._server
        addresses = sorted(server.localAddresses)
        for address in addresses:
            try:
                # port mapping may not tell the truth, trying this before the mapped port
                s = PlexServer(address, port=32400, token=server.accessToken)
                self._logger.info('connected to %s:%d', address, 32400)
                return s
            except NotFound:
                self._logger.debug('failed to connect to %s:%d', address, 32400)

            try:
                s = PlexServer(address, server.port, token=server.accessToken)
                self._logger.info('connected to %s:%d', address, server.port)
                return s
            except NotFound:
                self._logger.debug('failed to connect to %s:%d', address, server.port)

        return None

    def connect_external(self):
        server = self._server
        try:
            s = PlexServer(server.address, server.port, server.accessToken)
            self._logger.info('connected to %s:%d', server.address, server.port)
            return s
        except NotFound:
            self._logger.debug('failed to connect to %s:%d', server.address, server.port)
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