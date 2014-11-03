#!/usr/bin/python2
__version__ = "1.0.0"


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