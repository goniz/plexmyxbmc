import plexmyxbmc
from plexmyxbmc import millis_to_time
from plexmyxbmc.xbmc_rpc import InvalidRPCConnection


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
        self._rpc = rpc
        if not self._rpc.verify():
            raise InvalidRPCConnection()

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
            properties['shuffle'] = False

        properties['seekRange'] = '0-%d' % properties['duration']
        properties['volume'] = self.volume
        properties['protocol'] = 'http'
        properties['guid'] = ''
        return properties

    def get_timeline(self, playerid, playertype, location='navigation'):
        timeline = dict(location=location, type=playertype.plex)
        if playerid > 0:
            prop = self.get_player_properties(playerid)
            timeline.update(prop)
            timeline['controllable'] = "playPause,play,stop,skipPrevious,skipNext,volume,stepBack,stepForward,seekTo"
        else:
            timeline['state'] = 'stopped'
            timeline['time'] = 0
        return timeline

    def get_active_players(self):
        return self._rpc.execute('Player.GetActivePlayers', tuple())

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
            state[key] = self.get_timeline(playerid, mediatype, location=state['location'])
            index += 1

        return state

    def play_media(self, url, offset=0):
        params = dict(
            item=dict(
                file=url,
                ),
            options=dict(
                resume=millis_to_time(offset)
            )
        )
        self._rpc.execute('Player.Open', params)

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
            print 'Seek params', str(params)
            self._rpc.execute("Player.Seek", params)

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

    def notify(self, title, msg, duration=5000):
        args = dict(title=title, message=msg, displaytime=duration)
        self._rpc.execute('GUI.ShowNotification', args)
