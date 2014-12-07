#!/usr/bin/python2
import re
import time
from urlparse import urlparse, parse_qs
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

import plexmyxbmc
from plexmyxbmc.xml import dict2xml_withheader
from plexmyxbmc.config import get_config
from plexmyxbmc.log import get_logger

# contains the ThreadedAPIServer uri to handler routes
__ROUTES__ = dict()

# contains the routes NOT to verbose about
__ROUTES_SHUTUP__ = list()


def route(uri, quite=False):
    """
    :type quite: bool
    :type uri: str
    """

    def route_wrapper(func):
        """
        :type func: object
        """
        global __ROUTES_SHUTUP__
        __ROUTES__[uri] = func
        if quite is True:
            __ROUTES_SHUTUP__ += [uri]

        return func
    return route_wrapper


class ThreadedAPIServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, plex_client, addr, handler_class, bind_and_activate=True):
        """
        :type bind_and_activate: bool
        :type handler_class: PlexClientHandler
        :type addr: tuple
        :type plex_client: PlexClient
        """
        self.config = get_config()
        self._ok_msg = dict2xml_withheader(dict(code='200', status='OK'), root_node='Response')
        self.plex = plex_client
        HTTPServer.__init__(self, addr, handler_class, bind_and_activate)

    def update_command_id(self, req, params):
        """
        :type params: dict
        :type req: PlexClientHandler
        """
        uuid = req.headers.get('X-Plex-Client-Identifier', "")
        command_id = params.get('commandID', 0)
        sub = self.plex.sub_mgr.get(uuid, None)
        if sub:
            sub.update(cmd_id=command_id)

    @route('resources')
    def handle_resources(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        resp = {
            "Player": {
                "title": self.config['name'],
                "protocol": "plex",
                "protocolVersion": "1",
                "protocolCapabilities": "navigation,playback,timeline,sync-target",
                "machineIdentifier": self.config['uuid'],
                "product": "PlexMyXBMC",
                "platform": "Linux",
                "platformVersion": plexmyxbmc.__version__,
                "deviceClass": "pc"
            }
        }

        self.update_command_id(request, params)
        self.plex.xbmc.notify('Plex', 'Detected Remote Control')
        resp = dict2xml_withheader(resp, root_node='MediaContainer')
        return dict(data=resp, headers=self.plex.headers, code=200)

    @route('player/timeline/subscribe')
    def handle_timeline_subscribe(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        assert 'http' == params.get('protocol'), 'http is the only protocol supported'
        host = request.client_address[0]
        port = int(params.get('port', 32400))
        uuid = request.headers.get('X-Plex-Client-Identifier', "")
        command_id = params.get('commandID', 0)
        self.plex.sub_mgr.add(uuid, host, port, command_id, headers=request.headers)

        self.plex.sub_mgr.notify_all_delayed()
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/timeline/unsubscribe')
    def handle_timeline_unsubscribe(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        uuid = request.headers.get('X-Plex-Client-Identifier', "")
        self.update_command_id(request, params)
        self.plex.sub_mgr.remove(uuid)
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/timeline/poll', quite=True)
    def handle_timeline_poll(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        # defaults to '0' if 'wait' doesnt exist
        if params.get('wait', '0') == '1':
            time.sleep(1)

        self.update_command_id(request, params)
        command_id = params.get('commandID', 0)
        state = self.plex.xbmc.get_players_state()
        state['commandID'] = command_id
        xml = dict2xml_withheader(state, root_node='MediaContainer')
        return dict(data=xml, headers=self.plex.headers, code=200)

    @route('player/playback/playMedia')
    def handle_play_media(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        assert 'key' in params, 'a media key is a must'
        key = params.get('key')
        offset = int(params.get('offset', 0))

        self.update_command_id(request, params)
        self.plex.xbmc.metadata['containerKey'] = params.get('containerKey').split('?')[0]
        self.plex.xbmc.metadata['machineIdentifier'] = params.get('machineIdentifier')

        self.plex.event_mgr.schedule(self.plex.xbmc.play_key, (key, offset))
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/playback/stop')
    def handle_player_stop(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        self.update_command_id(request, params)

        self.plex.event_mgr.schedule(self.plex.xbmc.stop, tuple())
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/playback/setParameters')
    def handle_playback_set_parameters(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        self.update_command_id(request, params)
        if 'volume' in params:
            self.plex.xbmc.volume = int(params['volume'])
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/playback/pause')
    @route('player/playback/play')
    def handle_playback_pause(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        self.update_command_id(request, params)
        state = True if path.endswith('play') else False

        self.plex.event_mgr.schedule(self.plex.xbmc.play_pause, (state, ))
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/playback/seekTo')
    def handle_playback_seekto(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        self.update_command_id(request, params)
        offset = int(params.get('offset', 0))

        self.plex.event_mgr.schedule(self.plex.xbmc.seek, (offset, ))
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)

    @route('player/playback/stepForward')
    @route('player/playback/stepBack')
    @route('player/playback/skipNext')
    @route('player/playback/skipPrevious')
    def handle_playback_step(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        self.update_command_id(request, params)
        value = path.split('/')[-1]

        self.plex.event_mgr.schedule(self.plex.xbmc.step, (value, ))
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)


    @route("player/navigation/moveUp")
    @route("player/navigation/moveDown")
    @route("player/navigation/moveLeft")
    @route("player/navigation/moveRight")
    @route("player/navigation/select")
    @route("player/navigation/home")
    @route("player/navigation/back")
    def handle_navigation(self, request, path, params):
        """
        :type params: dict
        :type path: str
        :type request: PlexClientHandler
        """
        value = path.split('/')[-1]

        self.plex.event_mgr.schedule(self.plex.xbmc.navigate, (value, ))
        return dict(data=self._ok_msg, headers=self.plex.headers, code=200)


class PlexClientHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    _logger = get_logger('PlexClientHandler')

    def __init__(self, *args, **kwargs):
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def finish(self):
        try:
            return BaseHTTPRequestHandler.finish(self)
        except:
            pass

    def log_message(self, format, *args):
        # suppressing BaseHTTPRequestHandler's
        return True

    def do_HEAD(self):
        self.answer_request(0)

    def do_GET(self):
        self.answer_request(1)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.send_header('X-Plex-Client-Identifier', self.server.config['uuid'])
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Max-Age', '1209600')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', ', '.join((
            'POST',
            'GET',
            'OPTIONS',
            'DELETE',
            'PUT',
            'HEAD'
        )))

        self.send_header('Access-Control-Allow-Headers', ', '.join((
            "x-plex-version",
            "x-plex-platform-version",
            "x-plex-username",
            "x-plex-client-identifier",
            "x-plex-target-client-identifier",
            "x-plex-device-name",
            "x-plex-platform",
            "x-plex-product",
            "accept",
            "x-plex-device"
        )))
        self.end_headers()
        self.wfile.close()

    def response(self, body, headers={}, code=200):
        try:
            self.send_response(code)
            for key in headers:
                self.send_header(key, headers[key])
            self.send_header('Content-Length', len(body))
            self.send_header('Connection', "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.close()
        except Exception as e:
            self._logger.warn(str(e))

    def answer_request(self, sendData):
        request_path = self.path[1:]
        request_path = re.sub(r'\?.*', '', request_path)

        url = urlparse(self.path)
        paramarrays = parse_qs(url.query)
        params = {}
        for key in paramarrays:
            params[key] = paramarrays[key][0]

        if request_path not in __ROUTES_SHUTUP__:
            PlexClientHandler._logger.info('{0}:{1} request /{2} args {3}'.format(
                self.client_address[0],
                self.client_address[1],
                request_path,
                params
            ))

        handler = __ROUTES__.get(request_path)
        if handler is None:
            PlexClientHandler._logger.info('Unknown route, 404.. sry.')
            self.response('', code=404)
        else:
            try:
                resp = handler(self.server, self, request_path, params)
            except Exception as e:
                resp = dict(data=str(e), headers=dict(), code=500)

            resp['headers']['Content-Type'] = 'text/xml'
            resp['headers']['X-Plex-Client-Identifier'] = get_config().get('uuid')
            if request_path not in __ROUTES_SHUTUP__:
                PlexClientHandler._logger.debug('Responded with code: %d', int(resp['code']))
            self.response(resp['data'], headers=resp['headers'], code=resp['code'])
