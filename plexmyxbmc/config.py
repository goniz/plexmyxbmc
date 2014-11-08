#!/usr/bin/python2

import json
import os
import uuid
from plexmyxbmc.lock import Lock


class ConfigurationError(Exception):
    pass


class Configuration(dict):
    LOCK_PATH = '/tmp/.plexmyxbmc.lock'

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

        super(Configuration, self).__init__(config)
        self.commit()

    def commit(self):
        self.lock.acquire()
        fp = open(self.path, 'wb')
        json.dump(self, fp)
        fp.close()
        self.lock.release()

    def verify(self):
        if self.get('uuid') is None:
            self['uuid'] = str(uuid.uuid4())
        if self.get('port') is None:
            self['port'] = 9999
        if self.get('name') is None:
            self['name'] = 'PlexMyXBMC'
        if self.get('xbmc_host') is None:
            self['xbmc_host'] = 'localhost'
        if self.get('xbmc_port') is None:
            self['xbmc_port'] = 8080
        if self.get('xbmc_username') is None:
            self['xbmc_username'] = 'xbmc'
        if self.get('xbmc_password') is None:
            self['xbmc_password'] = 'xbmc'
        if not 'plex_username' in self or not 'plex_password' in self:
            self.commit()
            raise ConfigurationError('missing plex_username or plex_password')
        self.commit()


def default_system_config_path():
    return os.path.join(os.environ['HOME'], '.plexmyxbmc.json')
