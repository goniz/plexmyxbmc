#!/usr/bin/python2
import time
import threading


class ThreadMonitor(threading.Thread):
    def __init__(self):
        super(ThreadMonitor, self).__init__(name=self.__class__.__name__)
        self._keep_running = threading.Event()
        self._keep_running.set()

    def __del__(self):
        self.stop()

    def stop(self):
        print 'signalling monitor to stop'
        self._keep_running.clear()
        self.join()

    def run(self):
        while self._keep_running.is_set() is True:
            print '\nCurrent Thread Status:'
            for thread in threading.enumerate():
                print thread
            time.sleep(30)
        print 'monitor thread quiting..'