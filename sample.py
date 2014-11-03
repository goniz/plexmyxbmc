__author__ = 'gz'

from plexcast.client import PlexClient

client = PlexClient()
client.serve()

client.stop()
client.join()