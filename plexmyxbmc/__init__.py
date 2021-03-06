#!/usr/bin/python2
__version__ = "1.0.0"
import plexapi
from plexmyxbmc.config import get_config
from plexmyxbmc.log import get_logger

plexapi.X_PLEX_PROVIDES = 'player,controller,sync-target'
plexapi.X_PLEX_PRODUCT = "PlexMyXBMC"
plexapi.X_PLEX_VERSION = __version__
plexapi.X_PLEX_IDENTIFIER = get_config().get('uuid', 'randomuuid')
plexapi.X_PLEX_PLATFORM_VERSION = plexapi.X_PLEX_PLATFORM + plexapi.X_PLEX_PLATFORM_VERSION
plexapi.X_PLEX_PLATFORM = 'Generic'
BASE_HEADERS = {
    'X-Plex-Provides': plexapi.X_PLEX_PROVIDES,
    'X-Plex-Product': plexapi.X_PLEX_PRODUCT,
    'X-Plex-Version': plexapi.X_PLEX_VERSION,
    'X-Plex-Client-Identifier': plexapi.X_PLEX_IDENTIFIER,
    'X-Plex-Device-Name': get_config().get('name', 'randomname'),
    'X-Plex-Platform': plexapi.X_PLEX_PLATFORM,
    'X-Plex-Platform-Version': plexapi.X_PLEX_PLATFORM_VERSION,
}

plexapi.BASE_HEADERS.update(BASE_HEADERS)
logger = get_logger('plexapi', _force=True)
plexapi.log = logger


def time_to_millis(time):
    return (time['hours']*3600 + time['minutes']*60 + time['seconds'])*1000 + time['milliseconds']


def millis_to_time(t):
    millis = int(t)
    seconds = millis / 1000
    minutes = seconds / 60
    hours = minutes / 60
    seconds %= 60
    minutes %= 60
    millis %= 1000
    return dict(hours=hours, minutes=minutes, seconds=seconds, milliseconds=millis)
