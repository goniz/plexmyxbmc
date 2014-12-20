#!/usr/bin/python2
from threading import Thread
from Queue import Queue
from plexmyxbmc.log import get_logger
from plexmyxbmc.exceptions import ThreadStopError


class PlexEvent(object):
    def __init__(self, func, args, notify):
        self.func = func
        self.args = args
        self.notify = notify

    def __str__(self):
        return '{0} {1}{2}, notify={3}'.format(
            self.__class__.__name__,
            str(self.func.__name__),
            str(self.args),
            str(self.notify)
        )


class ThreadStopEvent(PlexEvent):
    def __init__(self):
        super(ThreadStopEvent, self).__init__(self.func, tuple(), False)

    def func(self):
        raise ThreadStopError()


class PlexEventsManager(Thread):
    def __init__(self, plex_client):
        self._queue = Queue()
        self._plex = plex_client
        self._xbmc = self._plex.xbmc
        self._handlers = dict()
        self._logger = get_logger(self.__class__.__name__)
        super(PlexEventsManager, self).__init__(name=self.__class__.__name__)

    def schedule(self, func, args, notify=True):
        event = PlexEvent(func, args, notify)
        self._queue.put(event)

    def schedule_event(self, event):
        assert isinstance(event, PlexEvent)
        self._queue.put(event)

    def run(self):
        while True:
            try:
                event = self._queue.get()
                self._logger.info('Processing Plex Event %s', event)
                event.func(*event.args)
                if event.notify is True:
                    self._plex.sub_mgr.notify_all()
            except ThreadStopError:
                self._logger.critical('Stopping event thread')
                break
            except Exception as e:
                self._logger.warn(str(e))
                pass

    def stop(self):
        self.schedule_event(ThreadStopEvent())