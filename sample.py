__author__ = 'gz'

from plexmyxbmc.client import PlexClient

client = PlexClient()
client.serve()

client.stop()
client.join()