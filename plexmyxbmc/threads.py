#!/usr/bin/python2
import time
import threading
from plexmyxbmc.log import get_logger


class ThreadMonitor(threading.Thread):
    def __init__(self):
        super(ThreadMonitor, self).__init__(name=self.__class__.__name__)
        self._keep_running = threading.Event()
        self._keep_running.set()
        self._logger = get_logger(self.__class__.__name__)

    def __del__(self):
        self.stop()

    def stop(self):
        self._logger.debug('signalling monitor to stop')
        self._keep_running.clear()
        self.join()

    def run(self):
        while self._keep_running.is_set() is True:
            self._logger.debug('Current Thread Status:')
            for thread in threading.enumerate():
                self._logger.debug(thread)
            time.sleep(30)
        self._logger.debug('monitor thread quiting..')