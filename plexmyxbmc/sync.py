#!/usr/bin/python2
from threading import Thread, Event, Timer
from Queue import Queue
from plexmyxbmc.log import get_logger
from plexmyxbmc.config import get_config


class ThreadStopRequest(object):
    pass


class SyncRequest(object):
    pass


class PlexSyncManager(Thread):
    # initial delay set to 60 seconds
    INITIAL_DELAY = 15
    # interval between syncs iterations set to 30 minutes
    SYNC_INTERVAL = 60 * 30

    def __init__(self, plex_client):
        self._plex = plex_client
        self._logger = get_logger(self.__class__.__name__)
        self._config = get_config()
        self._keep_running = Event()
        self._keep_running.set()
        self._last_timer = None
        self._queue = Queue()
        super(PlexSyncManager, self).__init__(name=self.__class__.__name__)

    def run(self):
        self._schedule_sync_request(PlexSyncManager.INITIAL_DELAY)
        while self._keep_running.is_set() is True:
            try:
                trigger = self._queue.get()
                if isinstance(trigger, ThreadStopRequest):
                    self._logger.warn('thread is exiting..')
                    break
                if not isinstance(trigger, SyncRequest):
                    self._logger.debug('invalid trigger found {0}'.format(type(trigger)))
                    continue

                self._logger.info('got SyncRequest, activating')
                self._clear_timer()
                self._handle_sync_operation()
            except Exception as e:
                self._logger.warn(str(e))
            finally:
                self._schedule_sync_request(PlexSyncManager.SYNC_INTERVAL)
        self._clear_timer()

    def _clear_timer(self):
        if self._last_timer is not None:
            self._last_timer.cancel()
        self._last_timer = None

    def stop(self):
        self._clear_timer()
        self._keep_running.clear()
        self._queue.put(ThreadStopRequest())

    def _handle_sync_operation(self):
        uuid = self._config['uuid']
        device = self._plex.user.getDevice(uuid)
        items = device.sync_items()
        for item in items:
            server = item.server()

        self._logger.debug(str(items))

    def _schedule_sync_request(self, seconds):
        def __trigger_sync_request():
            self._queue.put(SyncRequest())

        self._last_timer = Timer(seconds, __trigger_sync_request)
        self._last_timer.start()
        return self._last_timer
