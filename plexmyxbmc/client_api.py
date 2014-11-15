#!/usr/bin/python2
import re
import time
from urlparse import urlparse, parse_qs
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import plexapi.video as video

import plexmyxbmc
from plexmyxbmc.xml import dict2xml_withheader
from plexmyxbmc.config import Configuration, default_system_config_path

# contains the ThreadedAPIServer uri to handler routes
__ROUTES__ = dict()

# contains the routes NOT to verbose about
__ROUTES_SHUTUP__ = list()


class AuthenticatedUrl(object):
    def __init__(self, url, user):
        self._url = url
        self._user = user

    @property
    def url(self):
        return self._url + '?X-Plex-Token=' + self._user.authenticationToken

    def __str__(self):
        return self.url


def route(uri, quite=False):
    def route_wrapper(func):
        global __ROUTES_SHUTUP__
        __ROUTES__[uri] = func
        if quite is True:
            __ROUTES_SHUTUP__ += [uri]

        return func
    return route_wrapper


class ThreadedAPIServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler_class, bind_and_activate=True):
        HTTPServer.__init__(self, addr, handler_class, bind_and_activate)
        self.config = Configuration(default_system_config_path())
        self.plex = None
        self._plex_headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Access-Control-Allow-Origin": "*",
            "X-Plex-Version": plexmyxbmc.__version__,
            "X-Plex-Client-Identifier": self.config['uuid'],
            "X-Plex-Provides": "player",
            "X-Plex-Product": "PlexCast",
            "X-Plex-Device-Name": self.config['name'],
            "X-Plex-Platform": "Linux",
            "X-Plex-Model": "PlexCast",
            "X-Plex-Device": "PC",
        }

        if not self.config.get('plex_username') is None:
            self._plex_headers["X-Plex-Username"] = self.config['plex_username']

    @route('resources')
    def handle_resources(self, request, path, params):
        resp = {
            "Player": {
                "title": self.config['name'],
                "protocol": "plex",
                "protocolVersion": "1",
                "protocolCapabilities": "navigation,playback,timeline",
                "machineIdentifier": self.config['uuid'],
                "product": "PlexMyXBMC",
                "platform": "Linux",
                "platformVersion": plexmyxbmc.__version__,
                "deviceClass": "pc"
            }
        }
        self.plex.xbmc.notify('Plex', 'Detected Remote Control')
        resp = dict2xml_withheader(resp, root_node='MediaContainer')
        return dict(data=resp, headers=self._plex_headers, code=200)

    @route('player/timeline/subscribe')
    def handle_timeline_subscribe(self, request, path, params):
        assert 'http' == params.get('protocol'), 'http is the only protocol supported'
        host = request.client_address[0]
        port = params.get('port', 32400)
        uuid = request.headers.get('X-Plex-Client-Identifier', "")
        command_id = params.get('commandID', 0)
        self.plex.sub_mgr.add(uuid, host, port, command_id)
        return dict(data='', headers=dict(), code=200)

    @route('player/timeline/unsubscribe')
    def handle_timeline_unsubscribe(self, request, path, params):
        uuid = request.headers.get('X-Plex-Client-Identifier', "")
        self.plex.sub_mgr.remove(uuid)
        return dict(data='', headers=dict(), code=200)

    @route('player/timeline/poll', quite=False)
    def handle_timeline_poll(self, request, path, params):
        # defaults to '0' if 'wait' doesnt exist
        if params.get('wait', '0') == '1':
            time.sleep(1)
        commandID = params.get('commandID', 0)
        state = self.plex.xbmc.get_players_state()
        state['commandID'] = commandID
        xml = dict2xml_withheader(state, root_node='MediaContainer')
        headers = {
            'X-Plex-Client-Identifier': self.config['uuid'],
            'Access-Control-Expose-Headers': 'X-Plex-Client-Identifier',
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'text/xml'
        }
        return dict(data=xml, headers=headers, code=200)

    @route('player/playback/playMedia')
    def handle_play_media(self, request, path, params):
        assert 'key' in params, 'a media key is a must'
        key = params.get('key')
        offset = int(params.get('offset', 0))

        server = self.plex.server
        item = video.list_items(server, key, video.Episode.TYPE)
        if not item:
            raise Exception()

        item = item[0]
        media_parts = [x for x in item.iter_parts()]
        if not media_parts:
            raise Exception()

        media_part = media_parts[0]
        url = AuthenticatedUrl(server.url(media_part.key), self.plex.user).url
        self.plex.xbmc.play_media(url, offset)
        self.plex.sub_mgr.last_key = key
        return dict(data='', headers=dict(), code=200)

    @route('player/playback/stop')
    def handle_player_stop(self, request, path, params):
        self.plex.xbmc.stop()
        return dict(data='', headers=dict(), code=200)

    @route('player/playback/setParameters')
    def handle_playback_set_parameters(self, request, path, params):
        if 'volume' in params:
            self.plex.xbmc.volume = int(params['volume'])
        return dict(data='', headers=dict(), code=200)

    @route('player/playback/pause')
    @route('player/playback/play')
    def handle_playback_pause(self, request, path, params):
        state = True if path.endswith('play') else False
        self.plex.xbmc.play_pause(state)
        return dict(data='', headers=dict(), code=200)

    @route('player/playback/seekTo')
    def handle_playback_seekto(self, request, path, params):
        offset = int(params.get('offset', 0))
        self.plex.xbmc.seek(offset)
        return dict(data='', headers=dict(), code=200)

    @route('player/playback/stepForward')
    @route('player/playback/stepBack')
    @route('player/playback/skipNext')
    @route('player/playback/skipPrevious')
    def handle_playback_step(self, request, path, params):
        value = path.split('/')[-1]
        self.plex.xbmc.step(value)
        return dict(data='', headers=dict(), code=200)

    @route("player/navigation/moveUp")
    @route("player/navigation/moveDown")
    @route("player/navigation/moveLeft")
    @route("player/navigation/moveRight")
    @route("player/navigation/select")
    @route("player/navigation/home")
    @route("player/navigation/back")
    def handle_navigation(self, request, path, params):
        value = path.split('/')[-1]
        self.plex.xbmc.navigate(value)
        return dict(data='', headers=dict(), code=200)


class PlexClientHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

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
            print str(e)

    def answer_request(self, sendData):
        request_path = self.path[1:]
        request_path = re.sub(r'\?.*', '', request_path)

        url = urlparse(self.path)
        paramarrays = parse_qs(url.query)
        params = {}
        for key in paramarrays:
            params[key] = paramarrays[key][0]

        if not request_path in __ROUTES_SHUTUP__:
            print "request /%s args %s" % (request_path, params)
        handler = __ROUTES__.get(request_path)
        if handler is None:
            print 'Unknown route, 404.. sry.'
            self.response('', code=404)
        else:
            try:
                resp = handler(self.server, self, request_path, params)
            except Exception as e:
                resp = dict(data=str(e), headers=dict(), code=500)

            if not request_path in __ROUTES_SHUTUP__:
                print 'Responded with', resp
            self.response(resp['data'], headers=resp['headers'], code=resp['code'])
