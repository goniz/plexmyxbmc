#!/usr/bin/python2
from threading import Thread, Event, Timer
from Queue import Queue
import os
import json
import urllib2
import shutil
from plexapi.video import Video
from plexapi.media import MediaPart
from plexmyxbmc.log import get_logger
from plexmyxbmc.config import get_config


class ThreadStopRequest(object):
    pass


class SyncRequest(object):
    pass


class LocalSyncItem(object):
    READ_TIMEOUT = 10

    def __init__(self, video, part, dirname):
        """
        :type video: Video
        :type part: MediaPart
        :type dirname: str
        """
        self._base_dir = dirname
        self._part = part
        self._video = video
        self._metadata = self._load_meta()
        lname = '{0}-{1}'.format(self.__class__.__name__, self._part.sync_id)
        self._logger = get_logger(lname)
        self.save()

    @property
    def metadata_filename(self):
        """
        :return: str
        """
        return os.path.join(self._base_dir, 'metadata.json')

    @property
    def filename(self):
        """
        :return: str
        """
        return os.path.join(self._base_dir, 'file.mp4')

    @property
    def metadata(self):
        """
        :return: dict
        """
        return self._metadata

    @property
    def remote_size(self):
        """
        :return: int
        """
        return self._part.size

    def save(self):
        with open(self.metadata_filename, 'wb') as f:
            j = json.dumps(self._metadata)
            f.write(j)

    def _load_meta(self):
        """
        :return: dict
        """
        fname = self.metadata_filename
        if os.path.exists(fname):
            meta = json.load(open(fname, 'rb'))
        else:
            meta = dict()

        if 'done' not in meta:
            meta['done'] = False
        if 'reported' not in meta:
            meta['reported'] = False

        if 'show' not in meta:
            meta['show'] = self._video.grandparentTitle
        if 'title' not in meta:
            meta['title'] = self._video.title

        return meta

    def current_filesize(self):
        """
        :return: int
        """
        if os.path.exists(self.filename) is False:
            return 0

        return os.path.getsize(self.filename)

    def writable_stream(self):
        """
        :return: file
        """
        if not os.path.exists(self.filename):
            return open(self.filename, 'wb')
        return open(self.filename, 'a+b')

    def url_to_stream(self, url, timeout=None):
        """
        :param url: str
        :return: file
        """
        request = urllib2.Request(url)
        request.headers['Range'] = 'bytes={0}-{1}'.format(self.current_filesize(), self.remote_size)
        return urllib2.urlopen(request, timeout=timeout)

    def reset(self):
        os.unlink(self.filename)
        self.metadata['done'] = False
        self.save()

    def delete(self):
        self.reset()
        shutil.rmtree(self._base_dir)

    def download_part(self, url):
        """
        :param url: str
        :return: None
        """
        if self.metadata['done'] is True:
            return

        file_offset = self.current_filesize()
        if file_offset > self.remote_size:
            self.reset()
            file_offset = 0
            self._logger.info('found inconsistency in file sizes, resetting local file')

        if file_offset == self.remote_size:
            self.metadata['done'] = True
            return

        file_stream = self.writable_stream()
        remote_stream = self.url_to_stream(url, LocalSyncItem.READ_TIMEOUT)
        while True:
            chunk = remote_stream.read(4096)
            if not chunk:
                self.metadata['done'] = True
                self._logger.info('finished downloading part')
                break

            file_stream.write(chunk)
            file_stream.flush()

        remote_stream.close()
        file_stream.flush()
        file_stream.close()
        self.save()


class PlexStorageManager(object):
    def __init__(self, base_dir):
        """
        :type base_dir: str
        """
        self._base = os.path.join(base_dir, 'sync')
        self.mkdir_p(self._base)

    @property
    def base_dir(self):
        return self._base

    def mkdir_p(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    def local_sync_item(self, video, part):
        """
        :type part: MediaPart
        :type video: Video
        """
        server = video.server
        dirname = '{0}/library/parts/{1}/{2}'.format(server.machineIdentifier, part.sync_id, part.id)
        dirname = os.path.join(self._base, dirname)
        self.mkdir_p(dirname)
        return LocalSyncItem(video, part, dirname)

    def cleanup(self):
        #os.removedirs(self._base)
        pass

    def get_size_left(self):
        st = os.statvfs(self._base)
        if st.f_frsize:
            return st.f_frsize * st.f_bavail
        else:
            return st.f_bsize * st.f_bavail


class PlexSyncManager(Thread):
    # initial delay set to 60 seconds
    INITIAL_DELAY = 10
    # interval between syncs iterations set to 30 minutes
    SYNC_INTERVAL = 60 * 1

    def __init__(self, plex_client, storage_mgr):
        """
        :type plex_client: PlexClient
        :type storage_mgr: PlexStorageManager
        """
        self._plex = plex_client
        self._storage = storage_mgr
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
                self._storage.cleanup()
                recents = self._handle_sync_operation()
                self._remove_unused(recents)
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
        recents = list()
        uuid = self._config['uuid']
        device = self._plex.user.getDevice(uuid)
        items = device.sync_items()
        for item in items:
            media = item.get_media()
            for m in media:
                for part in m.iter_parts():
                    self._logger.debug('Found part %s - %s', m.grandparentTitle, part.id)
                    recents.append((m.server.machineIdentifier, part.sync_id, part.id))

                    url = self._plex.authenticated_url(m.server.url(part.key))
                    local_item = self._storage.local_sync_item(m, part)
                    local_item.download_part(url)

                    if local_item.metadata['done'] is True and local_item.metadata['reported'] is False:
                        item.mark_as_done(part.sync_id)
                        local_item.metadata['reported'] = True
                        local_item.save()
                        self._logger.debug('set %d as DONE', part.sync_id)
        return recents

    def _schedule_sync_request(self, seconds):
        """
        :param seconds: int
        :return: Timer
        """
        def __trigger_sync_request():
            self._queue.put(SyncRequest())

        self._last_timer = Timer(seconds, __trigger_sync_request)
        self._last_timer.start()
        return self._last_timer

    def _remove_unused(self, recents):
        paths = ['{0}/library/parts/{1}/{2}'.format(uuid, sync_id, part_id) for uuid, sync_id, part_id in recents]

        count = 0
        for server in os.listdir(self._storage.base_dir):
            server = os.path.join(self._storage.base_dir, server)
            sync_ids = os.path.join(server, 'library/parts')
            for sync_id in os.listdir(sync_ids):
                sync_id = os.path.join(sync_ids, sync_id)
                for part_id in os.listdir(sync_id):
                    part_id = os.path.join(sync_id, part_id)

                    path = part_id.replace(self._storage.base_dir, '').lstrip('/')
                    if path not in paths:
                        self._logger.warn('Removing unused sync items: %s', path)
                        try:
                            shutil.rmtree(part_id)
                        except OSError as e:
                            self._logger.warn('_remove_unused: %s', str(e))
                        count += 1
        self._logger.debug('removed %d unused items', count)
        return count
