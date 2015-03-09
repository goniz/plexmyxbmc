import plexmyxbmc
from plexmyxbmc import millis_to_time
from plexmyxbmc.xbmc_rpc import InvalidRPCConnection
import plexapi.video as video
from plexmyxbmc.log import get_logger


class PlayerType(object):
    def __init__(self, type):
        self._type = type

    @property
    def plex(self):
        if 'audio' == self._type:
            return 'music'
        return self._type

    @property
    def xbmc(self):
        if 'music' == self._type:
            return 'audio'
        return self._type

    def __eq__(self, other):
        if not isinstance(other, PlayerType):
            return False
        return self.plex == other.plex


class XBMC(object):
    def __init__(self, rpc):
        self._logger = get_logger(self.__class__.__name__)
        self._rpc = rpc
        if not self._rpc.verify():
            raise InvalidRPCConnection()

    @property
    def rpc(self):
        return self._rpc

    def get_player_properties(self, playerid):
        args = dict(playerid=int(playerid), properties=["time", "totaltime", "speed", "shuffled"])
        resp = self._rpc.execute("Player.GetProperties", args)
        properties = dict()
        try:
            properties['time'] = plexmyxbmc.time_to_millis(resp['time'])
            properties['duration'] = plexmyxbmc.time_to_millis(resp['totaltime'])
            properties['state'] = 'paused' if resp['speed'] is 0 else 'playing'
            properties['shuffle'] = '0' if resp.get('shuffled', False) is False else '1'
        except Exception:
            properties['time'] = 0
            properties['duration'] = 0
            properties['state'] = "stopped"
            properties['shuffle'] = '0'

        properties['volume'] = self.volume
        return properties

    def get_active_players(self):
        return self._rpc.execute('Player.GetActivePlayers', tuple())

    def play_media(self, url, offset=0):
        params = dict(
            item=dict(
                file=url,
                ),
            options=dict(
                resume=millis_to_time(offset)
            )
        )
        return self._rpc.execute('Player.Open', params)

    def stop(self):
        for player in self.get_active_players():
            playerid = int(player['playerid'])
            self._rpc.execute('Player.Stop', dict(playerid=playerid))

    @property
    def volume(self):
        args = dict(properties=['volume'])
        resp = self._rpc.execute('Application.GetProperties', args)
        return resp.get('volume', 100)

    @volume.setter
    def volume(self, val):
        val = int(val)
        args = dict(volume=val)
        self._rpc.execute('Application.SetVolume', args)

    def play_pause(self, state):
        assert isinstance(state, bool) is True, 'Expected Bool, got %s' % type(state)
        for player in self.get_active_players():
            playerid = int(player['playerid'])
            self._rpc.execute('Player.PlayPause', dict(playerid=playerid, play=state))

    def seek(self, seek_value=0):
        for player in self.get_active_players():
            playerid = int(player['playerid'])
            if isinstance(seek_value, int):
                seek_to = millis_to_time(seek_value)
            elif isinstance(seek_value, str):
                seek_to = seek_value
            else:
                raise ValueError('expected (int, str), found %s' % type(seek_value))
            params = dict(playerid=playerid, value=seek_to)
            self._logger.debug('Seek params %s', str(params))
            self._rpc.execute("Player.Seek", params)

    def notify(self, title, msg, duration=5000):
        args = dict(title=title, message=msg, displaytime=duration)
        self._rpc.execute('GUI.ShowNotification', args)

    def __str__(self):
        return '{0} at {1}:{2}'.format(
            self.__class__.__name__,
            self._rpc.host,
            self._rpc.port
        )


class XBMCPlexPlayer(XBMC):
    def __init__(self, rpc, plex):
        super(XBMCPlexPlayer, self).__init__(rpc)
        self._plex = plex
        self._metadata = dict()

    @property
    def metadata(self):
        return self._metadata

    def step(self, plex_value):
        steps = dict(
            stepForward='smallforward',
            stepBack='smallbackward',
            skipNext='bigforward',
            skipPrevious='bigbackward'
        )
        value = steps[plex_value]
        self.seek(value)

    def navigate(self, plex_value):
        steps = dict(
            moveUp='Input.Up',
            moveDown='Input.Down',
            moveLeft='Input.Left',
            moveRight='Input.Right',
            select='Input.Select',
            home='Input.Home',
            back='Input.Back'
        )
        value = steps[plex_value]
        self._rpc.execute(value, dict())

    def get_timeline(self, playerid, playertype):
        timeline = dict(type=playertype.plex)
        vid = self.metadata.get('video', None)
        container_key = self.metadata.get('containerKey', None)
        
        if playerid > 0:
            prop = self.get_player_properties(playerid)
            timeline.update(prop)
            timeline['controllable'] = "playPause,play,stop,skipPrevious,skipNext,volume,stepBack,stepForward,seekTo"
            timeline['seekRange'] = '0-%d' % prop['duration']
            timeline['guid'] = ''
            timeline['machineIdentifier'] = self.metadata.get('machineIdentifier', '')

            if vid is not None:
                timeline['address'] = vid.server.address
                timeline['port'] = str(vid.server.port)
                timeline['protocol'] = 'http'
                timeline['key'] = vid.key
                timeline['ratingKey'] = vid.ratingKey
                timeline['subtitleStreamID'] = '-1'

            if container_key is not None:
                timeline['containerKey'] = container_key
                timeline['playQueueID'] = container_key.strip().split('/')[-1]
        else:
            if vid is not None:
                timeline['key'] = vid.key
            timeline['state'] = 'stopped'
            timeline['time'] = 0
        return timeline

    def get_players_state(self):
        state = dict()
        players = self.get_active_players()

        state['location'] = "navigation"
        index = 0
        for mediatype in ('audio', 'photo', 'video'):
            mediatype = PlayerType(mediatype)
            player = filter(lambda x: PlayerType(x['type']) == mediatype, players)
            if player:
                playerid = int(player[0]['playerid'])
                state['location'] = 'fullScreen' + mediatype.plex.capitalize()
            else:
                playerid = -1

            # hack to generate 'Timeline_', 'Timeline__' or 'Timeline___' to cheat dict2xml
            key = 'Timeline' + ('_' * index)
            state[key] = self.get_timeline(playerid, mediatype)
            state[key]['location'] = state['location']
            index += 1

        return state

    def play_video(self, video, offset=0):
        # gets a plexapi.video.Video object
        media_parts = [x for x in video.iter_parts()]
        if not media_parts:
            raise Exception(video)

        media_part = media_parts[0]
        cached_item = self._plex.storage_mgr.get_cached_item(video, media_part)
        if cached_item:
            self._logger.info('found cached media part %s', str(cached_item))
        else:
            self._logger.info('did not find media part in local cache, playing from remote server')

        if cached_item and cached_item.done is True:
            # assumes XBMC is running on the same host as this PMX
            # will implement this via the embedded HTTP server to allow
            # this feature to work with remote XBMC
            #url = 'file://{0}'.format(cached_item.filename)
            url = cached_item.filename
            self._logger.debug('cached media part is fully downloaded! using local file')
        else:
            url = self._plex.authenticated_url(media_part.key)
            self._logger.debug('Using remote file')
            
        self._logger.debug('playing url %s', url)
        self.play_media(url, offset)
        self._metadata['video'] = video
        self._metadata['part'] = media_part

    def play_key(self, key, offset=0):
        server = self._plex.server
        item = video.list_items(server, key, video.Episode.TYPE)
        if not item:
            raise Exception()

        item = item[0]
        self.play_video(item, offset)
