#!/usr/bin/python2

import sys
from plexmyxbmc.config import get_config
from plexmyxbmc.client import PlexClient


def main():
    config = get_config()
    config.verify()

    client = PlexClient()
    client.serve()
    client.stop()
    client.join()
    return 0

if '__main__' == __name__:
    sys.exit(main())
