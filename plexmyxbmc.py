#!/usr/bin/python2

import sys
from plexmyxbmc.config import Configuration, default_system_config_path
from plexmyxbmc.client import PlexClient


def main():
    config = Configuration(default_system_config_path())
    config.verify()

    client = PlexClient()
    client.serve()
    client.stop()
    client.join()
    return 0

if '__main__' == __name__:
    sys.exit(main())
