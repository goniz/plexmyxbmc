#!/usr/bin/python2
from threading import Thread, Event, Timer, Lock
from Queue import Queue
import os
import json
import urllib2
import shutil
import hashlib
from plexmyxbmc.log import get_logger
from plexmyxbmc.config import get_config
from plexmyxbmc.exceptions import DownloadInterruptedError
from plexapi.exceptions import NotFound
import plexapi


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
        lname = '{0}-{1}'.format(self.__class__.__name__, self._part.id)
        self._logger = get_logger(lname)
        self._metadata = self._load_meta()
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
    
    @property
    def done(self):
        """
        :return: bool
        """
        return self.metadata.get('done', False)
    
    @done.setter
    def done(self, d):
        self.metadata['done'] = d

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
        if 'season' not in meta:
            meta['season'] = int(self._video.parentIndex)
        if 'episode' not in meta:
            meta['episode'] = int(self._video.index)
        if 'total_size' not in meta:
            meta['total_size'] = self.remote_size
        if 'video.key' not in meta:
            meta['video.key'] = int(str(self._video.key).split('/')[-1])
        if 'part.id' not in meta:
            meta['part.id'] = self._part.id
        if 'part.syncId' not in meta:
            if not hasattr(self._part, 'syncId') or int(self._part.syncId) <= 0:
                raise ValueError('{0}:{1} - Expected valid syncId for media part. found {2}'.format(self._video.key, self._part.id, self._part.syncId))
            meta['part.syncId'] = self._part.syncId

        if not hasattr(self._part, 'syncId') or int(self._part.syncId) <= 0:
            setattr(self._part, 'syncId', self.metadata['part.syncId'])

        return meta
    
    def __str__(self):
        desc = ''
        if 'title' in self.metadata:
            desc = self.metadata['title']
        if 'season' in self.metadata and 'episode' in self.metadata:
            desc = 'S%02dE%02d' % (self.metadata['season'], self.metadata['episode'])
            
        return '<{0}:{1}:{2}:{3}MB>'.format(self.__class__.__name__,
                                          self.metadata['show'],
                                          desc,
                                          int(int(self.metadata['total_size'])/1024.0/1024.0))

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
        if os.path.exists(self.filename):
            os.unlink(self.filename)
        self.done = False
        self.save()

    def delete(self):
        self.reset()
        shutil.rmtree(self._base_dir)

    def download_part(self, url, _interrupt_event=None):
        """
        :param url: str
        :param _interrupt_event: Event
        :return: None
        """
        _interrupt_event = Event() if _interrupt_event is None else _interrupt_event
        if self.done is True:
            return

        file_offset = self.current_filesize()
        if file_offset > self.remote_size:
            self.reset()
            file_offset = 0
            self._logger.info('found inconsistency in file sizes, resetting local file')

        if file_offset == self.remote_size:
            self.done = True
            return

        file_stream = self.writable_stream()
        remote_stream = self.url_to_stream(url, LocalSyncItem.READ_TIMEOUT)
        current = self.current_filesize()
        self._logger.info('Downloading item, total size: %d MB, remaining size %d MB',
                          self.remote_size/1024/1024.0,
                          self.download_size_left(current)/1024/1024.0)

        last_progress = self.download_progress(current, int)
        try:
            while _interrupt_event.is_set() is True:
                chunk = remote_stream.read(4 * 1024 * 1024)
                if not chunk:
                    self.done = True
                    self._logger.info('finished downloading part')
                    break

                file_stream.write(chunk)

                current = file_stream.tell()
                progress = self.download_progress(current, int)
                if last_progress != progress:
                    last_progress = progress
                    self._logger.debug('Download progress %3d%%, left %d MB',
                                       progress,
                                       self.download_size_left(current)/1024/1024.0)
        except Exception as e:
            self._logger.warn(str(e))

        remote_stream.close()
        file_stream.flush()
        file_stream.close()
        self.save()

        if _interrupt_event.is_set() is False:
            raise DownloadInterruptedError('Download interrupted by user event.')

    def download_progress(self, current_size=None, cast=float):
        current_size = self.current_filesize() if current_size is None else current_size
        current = float(current_size)
        total = float(self.remote_size)
        progress = (current / total) * 100.0
        return cast(progress)

    def download_size_left(self, current_size=None):
        current_size = self.current_filesize() if current_size is None else current_size
        return self.remote_size - current_size


class PlexStorageManager(object):
    def __init__(self, plex_client, base_dir):
        """
        :type plex_client: PlexClient
        :type base_dir: str
        """
        self._plex = plex_client
        self._base = os.path.join(base_dir, 'sync')
        self._items_cache = dict()
        self._lock = Lock()
        self._logger = get_logger(self.__class__.__name__)
        self.mkdir_p(self._base)
        self._load_cached_items()

    @property
    def base_dir(self):
        return self._base

    def mkdir_p(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    def _local_sync_item_from_metadata(self, meta):
        if isinstance(meta, file):
            meta = json.load(file)
        elif isinstance(meta, (str, unicode)):
            meta = json.load(open(meta, 'rb'))
        elif isinstance(meta, dict):
            pass
        else:
            raise TypeError('Expected file, (str, unicode) filename, or a dict. found {0}'.format(type(meta)))
        
        assert 'video.key' in meta
        assert 'part.id' in meta
        assert 'part.syncId' in meta
        
        server = self._plex.server
        key = '/library/metadata/{0}'.format(meta['video.key'])
        part_id = meta['part.id']
        video = plexapi.video.list_items(server, key, plexapi.video.Episode.TYPE)
        if not video:
            raise NotFound('Could not find video in library: {0}'.format(key))

        video = video[0]
        for part in video.iter_parts():
            if str(part.id) == str(part_id):
                part.syncId = meta['part.syncId']
                return self.local_sync_item(video, part)
        raise NotFound('Could not find video+part combo in library: {0}:{1}'.format(key, part_id))
                
    def _load_cached_items(self):
        for server in os.listdir(self.base_dir):
            server = os.path.join(self.base_dir, server)
            sync_ids = os.path.join(server, 'library/parts')
            if not os.path.isdir(sync_ids):
                continue

            for sync_id in os.listdir(sync_ids):
                sync_id = os.path.join(sync_ids, sync_id)
                if not os.path.isdir(sync_id):
                    continue

                parts = os.listdir(sync_id)
                if len(parts) == 0:
                    try:
                        self._logger.debug('removing empty dir %s', sync_id.replace(self.base_dir, '').lstrip('/'))
                        os.rmdir(sync_id)
                    except OSError as e:
                        self._logger.warn(str(e))
                    continue
                    
                for part_id in parts:
                    part_id = os.path.join(sync_id, part_id)
                    meta = os.path.join(part_id, 'metadata.json')
                    
                    if not os.path.exists(meta):
                        try:
                            self._logger.debug('removing empty dir %s', part_id.replace(self.base_dir, '').lstrip('/'))
                            os.rmdir(part_id)
                        except OSError as e:
                            self._logger.warn(str(e))
                        continue

                    try:
                        self._local_sync_item_from_metadata(meta)
                    except NotFound as e:
                        self._logger.warn(str(e))
        self._logger.info('loaded %d cache entries', len(self._items_cache))
    
    def _gen_cache_hash(self, video_key, part_id):
        try:
            video_key = int(str(video_key).split('/')[-1])
        except Exception as e:
            self._logger.warn('failed to understand video_key when generating hash: %s', str(e))
            raise
        
        item_hash = hashlib.sha1()
        item_hash.update(str(video_key))
        item_hash.update(str(part_id))
        return item_hash.digest()
    
    def _gen_cache_hash_by_item(self, item):
        return self._gen_cache_hash(item._video.key, item._part.id)
            
    def get_cached_item(self, video, part):
        item_hash = self._gen_cache_hash(video.key, part.id)
        with self._lock:
            item = self._items_cache.get(item_hash, None)
        return item
        
    def set_cached_item(self, item):
        item_hash = self._gen_cache_hash_by_item(item)
        with self._lock:
            self._items_cache[item_hash] = item
        return item_hash
    
    def del_cached_item(self, item):
        item_hash = self._gen_cache_hash_by_item(item)
        with self._lock:
            del self._items_cache[item_hash]
        return item_hash

    def local_sync_item(self, video, part):
        """
        :type part: MediaPart
        :type video: Video
        """
        cached_item = self.get_cached_item(video, part)
        if cached_item:
            return cached_item
        
        server = video.server
        dirname = '{0}/library/parts/{1}/{2}'.format(server.machineIdentifier, part.syncId, part.id)
        dirname = os.path.join(self._base, dirname)
        self.mkdir_p(dirname)
        item = LocalSyncItem(video, part, dirname)
        self.set_cached_item(item)
        return item

    def cleanup(self, recents):
        used = recents
        total = self._items_cache.values()
        unused = [x for x in total if x not in used]
        
        self._logger.info('Found %d unused items', len(unused))
        for item in unused:
            self._logger.debug('Removing unused item: %s - %s (%d MB)',
                               item.metadata['show'],
                               item.metadata['title'],
                               item.current_filesize()/1024.0/1024.0)
            item.delete()
            self.del_cached_item(item)
            del item
        self._logger.info('Removed %d unused items', len(unused))

    def get_size_left(self):
        st = os.statvfs(self._base)
        if st.f_frsize:
            return st.f_frsize * st.f_bavail
        else:
            return st.f_bsize * st.f_bavail


class PlexSyncManager(Thread):
    # initial delay set to 5 seconds
    INITIAL_DELAY = 5
    # interval between syncs iterations set to 15 minutes
    SYNC_INTERVAL = 60 * 15
    # a lower interval to set when an error occurred
    ERROR_SYNC_INTERVAL = 60

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

                self._logger.info('SyncRequest() --> Running PlexSync job')
                self._clear_timer()
                recents = self._handle_sync_operation()
                self._storage.cleanup(recents)
                self._logger.info('Finished PlexSync job')

                # if necessary, set a
                if self._keep_running.is_set() is True:
                    self._schedule_sync_request(PlexSyncManager.SYNC_INTERVAL)
            except Exception as e:
                self._logger.warn(str(e))
                self._schedule_sync_request(PlexSyncManager.ERROR_SYNC_INTERVAL)
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
        items = device.syncItems()
        for item in items:
            media = item.getMedia()
            for m in media:
                for part in m.iter_parts():
                    url = self._plex.authenticated_url(m.server.url(part.key))
                    local_item = self._storage.local_sync_item(m, part)
                    recents.append(local_item)

                    self._logger.info('Found part %s', str(local_item))
                    local_item.download_part(url, _interrupt_event=self._keep_running)

                    if local_item.done is True and local_item.metadata['reported'] is False:
                        item.markAsDone(part.syncId)
                        local_item.metadata['reported'] = True
                        local_item.save()
                        self._logger.debug('set %d as DONE', part.syncId)
        return recents

    def _schedule_sync_request(self, seconds):
        """
        :param seconds: int
        :return: Timer
        """
        def __trigger_sync_request():
            self._queue.put(SyncRequest())

        if self._keep_running.is_set() is True:
            self._last_timer = Timer(seconds, __trigger_sync_request)
            self._last_timer.start()
            self._logger.debug('Rescheduled another job that will launch in %d min', seconds/60.0)

        return self._last_timer
