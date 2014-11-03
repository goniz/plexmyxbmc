#!/usr/bin/python2

import json
import os
import uuid
from plexcast.lock import Lock


class ConfigurationError(Exception):
    pass


class Configuration(dict):
    LOCK_PATH = '/tmp/.plexcast.lock'

    def __init__(self, path):
        self.path = path
        self.lock = Lock(Configuration.LOCK_PATH)
        if os.path.isfile(path):
            try:
                self.lock.acquire()
                fp = open(self.path, 'rb')
                config = json.load(fp)
            except:
                print('config file %s could not be read, using defaults')
                config = dict()
            finally:
                self.lock.release()
        else:
            config = dict()

        if config.get('uuid') is None:
            config['uuid'] = str(uuid.uuid4())
        if config.get('port') is None:
            config['port'] = 9999
        if config.get('name') is None:
            config['name'] = 'PlexCast for XBMC'
        if config.get('xbmc_host') is None:
            config['xbmc_host'] = 'localhost'
        if config.get('xbmc_port') is None:
            config['xbmc_port'] = 8080
        if not 'plex_username' in config or not 'plex_password' in config:
            raise ConfigurationError('missing plex_username or plex_password')

        super(Configuration, self).__init__(config)
        self.commit()

    def commit(self):
        self.lock.acquire()
        fp = open(self.path, 'wb')
        json.dump(self, fp)
        fp.close()
        self.lock.release()
        print('config commited to disk')


def default_system_config_path():
    return os.path.join(os.environ['HOME'], '.plexcast.json')
