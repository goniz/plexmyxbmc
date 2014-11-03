#!/usr/bin/python2
import socket
import httplib
import StringIO
from plexapi.server import PlexServer


class _FakeSocket(StringIO.StringIO):
    def makefile(self, *args, **kw):
        return self


class SSDPResponse(object):
    def __init__(self, addr, response):
        self.addr = addr
        r = httplib.HTTPResponse(_FakeSocket(response))
        r.begin()
        self.headers = dict(r.getheaders())
        self.msg = r.msg
        self.status = r.status

    def __repr__(self):
        return "<SSDPResponse(%s, %s) from %s>" % (
            self.status,
            self.headers,
            self.addr
        )


class SSDPDiscovery(object):
    def __init__(self, timeout=2):
        self.timeout = timeout
        self.group = ("239.255.255.250", 1900)
        self.msg = [
            'M-SEARCH * HTTP/1.1',
            'HOST: {0}:{1}',
            'MAN: "ssdp:discover"',
            'ST: {st}',
            'MX: 3',
            '',
            ''
        ]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(self.timeout)

    def discover(self, service, retries=1):
        responses = list()
        for _ in range(retries):
            msg = '\r\n'.join(self.msg).format(*self.group, st=service)
            self.sock.sendto(msg, self.group)
            while True:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    response = SSDPResponse(addr, data)
                    responses.append(response)
                except socket.timeout:
                    break
        return responses


class PlexGDM(SSDPDiscovery):
    def __init__(self, plex_user, timeout=2):
        super(PlexGDM, self).__init__(timeout)
        self._user = plex_user
        self.group = ("255.255.255.255", 32414)

    def discover(self, service='Plex Media Server', retries=1):
        resp = super(PlexGDM, self).discover(service, retries)
        token = self._user.authenticationToken
        servers = []
        for server in resp:
            addr, port = server.addr
            port = int(server.headers['port'])
            try:
                servers.append(PlexServer(addr, port, token))
            except:
                pass
        servers.sort(key=lambda x: x.friendlyName)
        return servers