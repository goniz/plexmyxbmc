__author__ = 'gz'

import sys
from plexmyxbmc.client import PlexClient


def main():
    client = PlexClient()
    client.serve()
    client.stop()
    client.join()
    return 0

if '__main__' == __name__:
    sys.exit(main())
