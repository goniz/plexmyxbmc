#!/usr/bin/python2
import threading
import socket
import time
import plexmyxbmc
from plexmyxbmc.log import get_logger


class ClientInfo(object):
    def __init__(self, c_id, c_name, c_port, c_product, c_version):
        self.id = c_id
        self.name = c_name
        self.port = c_port
        self.product = c_product
        self.version = c_version

    @staticmethod
    def from_config(conf):
        return ClientInfo(
            conf['uuid'],
            conf['name'],
            conf['port'],
            'PlexMyXBMC',
            plexmyxbmc.__version__
        )


class ClientRegistration(threading.Thread):
    def __init__(self, client_info):
        super(ClientRegistration, self).__init__(name=self.__class__.__name__)
        self.c_info = client_info
        self.multicast_addr = '239.0.0.250'
        self.update_port = 32412
        self.register_port = 32413
        self.client_register_group = (self.multicast_addr, self.register_port)
        self._setup_socket()
        self._keep_running = False
        self._logger = get_logger(self.__class__.__name__)
        self.hello_headers = [
            "HELLO * HTTP/1.0"
        ]
        self.bye_headers = [
            "BYE * HTTP/1.0"
        ]
        self.response_headers = [
            "HTTP/1.0 200 OK"
        ]
        self.c_headers = [
            "Content-Type: plex/media-player",
            "Resource-Identifier: %s" % self.c_info.id,
            "Name: %s" % self.c_info.name,
            "Port: %s" % self.c_info.port,
            "Product: %s" % self.c_info.product,
            "Version: %s" % self.c_info.version,
            "Protocol: plex",
            "Protocol-Version: 1",
            "Protocol-Capabilities: navigation,playback,timeline,sync-target",
            "Device-Class: HTPC"
        ]

    def _setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                             socket.inet_aton(self.multicast_addr) + socket.inet_aton('0.0.0.0'))
        self.sock.settimeout(5)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except:
            pass

    @staticmethod
    def _pack_headers(headers):
        headers.append("Updated-At: %d" % (int(time.time()), ))
        return '\r\n'.join(headers) + ('\r\n' * 2)

    def _send_hello(self):
        msg = ClientRegistration._pack_headers(self.hello_headers + self.c_headers)
        self.sock.sendto(msg, self.client_register_group)

    def _send_bye(self):
        msg = ClientRegistration._pack_headers(self.bye_headers + self.c_headers)
        self.sock.sendto(msg, self.client_register_group)

    def _send_response(self, addr):
        msg = ClientRegistration._pack_headers(self.response_headers + self.c_headers)
        self.sock.sendto(msg, addr)

    def stop(self):
        self._keep_running = False
        self._logger.debug('trying to stop')

    def run(self):
        try:
            self.sock.bind(('0.0.0.0', self.update_port))
        except socket.error as e:
            self.warn('Client Registration: Failed to bind to port %d (%s)', self.update_port, str(e))
            return

        self._keep_running = True
        self._send_hello()
        while self._keep_running is True:
            data, addr = '', tuple()
            try:
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                self.stop()
                break

            if not data.startswith("M-SEARCH * HTTP/1."):
                self._logger.info('Invalid request, ignoring')
                continue

            self._send_response(addr)

        self._logger.debug('Stopping!')
        self._send_bye()
