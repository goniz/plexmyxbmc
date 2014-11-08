#!/usr/bin/python2

import argparse
import sys

from plexmyxbmc.config import Configuration, default_system_config_path


def init_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xbmc-host', type=str)
    parser.add_argument('--xbmc-port', type=int)
    parser.add_argument('--xbmc-username', type=str)
    parser.add_argument('--xbmc-password', type=str)
    parser.add_argument('--plex-username', type=str)
    parser.add_argument('--plex-password', type=str)
    parser.add_argument('--name', type=str)
    parser.add_argument('--port', type=int)

    parser.add_argument('--config-path', type=str, default=default_system_config_path())
    parser.add_argument('--display', action='store_true', default=False)
    return parser


def pprint(config):
    print '\nCurrent config values:'
    keys = sorted(config.keys())
    for key in keys:
        value = config[key]
        line = '\t%-15s: %s' % (key, value)
        print(line)


def main():
    parser = init_argparse()
    options = parser.parse_args()

    config = Configuration(options.config_path)
    if options.xbmc_host:
        config['xbmc_host'] = options.xbmc_host
    if options.xbmc_port:
        config['xbmc_port'] = options.xbmc_port
    if options.xbmc_username:
        config['xbmc_username'] = options.xbmc_username
    if options.xbmc_password:
        config['xbmc_password'] = options.xbmc_password
    if options.plex_username:
        config['plex_username'] = options.plex_username
    if options.plex_password:
        config['plex_password'] = options.plex_password
    if options.name:
        config['name'] = options.name
    if options.port:
        config['port'] = options.port
    config.commit()

    if options.display is True:
        pprint(config)
    return 0

if '__main__' == __name__:
    sys.exit(main())