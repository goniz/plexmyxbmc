import json
import time
import urllib2
import socket
from Queue import Queue
from threading import Lock, Thread, Event
from plexmyxbmc.log import get_logger


class InvalidRPCConnection(Exception):
    pass


class XbmcRPC(object):
    def __init__(self):
        self._lock = Lock()
        self._id = 0
        self._alive = Event()
        self._alive.clear()
        self._logger = get_logger(self.__class__.__name__)

    def _execute(self, json_data, timeout=None):
        raise NotImplementedError()

    def execute(self, method, args, timeout=None):
        with self._lock:
            params = dict(jsonrpc='2.0', id=self._id, method=method, params=args)
            self._id += 1

        data = json.dumps(params)
        try:
            resp = self._execute(data, timeout=timeout)
        except Exception as e:
            self._logger.warn(str(e))
            return None

        if len(resp) > 0:
            if isinstance(resp, (str, unicode)):
                resp = json.loads(resp)
            if resp.get('result') is None:
                raise Exception(resp)
            return resp['result']
        return None

    def verify(self, timeout=None):
        res = self.execute('JSONRPC.Ping', tuple(), timeout=timeout)
        if res == u'pong':
            return True
        return False

    def wait(self, timeout=None):
        if self._alive.wait(timeout) is True:
            return self

        raise InvalidRPCConnection()


class XbmcJSONRPC(XbmcRPC):
    def __init__(self, host='localhost', port=9090):
        super(XbmcJSONRPC, self).__init__()
        self._host = host
        self._port = port
        self._events = dict()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._response_queue = Queue()
        self._execute_lock = Lock()
        self._keep_running = False
        self._thread = Thread(target=self._socket_handler_thread, name=XbmcJSONRPC.__name__)
        self._thread.start()

    def __del__(self):
        self.stop()

    def _connect_socket(self):
        with self._lock:
            if hasattr(self._socket, 'close'):
                self._socket.close()
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            for i in xrange(3):
                try:
                    self._socket.connect((self._host, self._port))
                    self._alive.set()
                    self._logger.info('Connected to XBMC')
                    return self._socket
                except:
                    time.sleep(1)
                    continue
            self._socket.close()
            self._alive.clear()
            self._logger.inof('XBMC Disconnected')
            raise InvalidRPCConnection()

    def stop(self):
        self._keep_running = False
        # trigger the thread in order to detect the shutdown request
        self.verify()
        if self._thread.isAlive():
            self._thread.join()
        self._socket.close()

    def register(self, event, handler):
        with self._lock:
            if event in self._events:
                self._events[event].append(handler)
            else:
                self._events[event] = [handler]

    def unregister(self, event, handler):
        with self._lock:
            if event in self._events:
                self._events[event].remove(handler)

    def _socket_handler_thread(self):
        self._keep_running = True
        buf = str()
        depth = 0
        while self._keep_running is True:
            try:
                chunk = self._socket.recv(1024)
            except socket.error:
                # simulate connection `closed`
                chunk = ''

            if 0 == len(chunk):
                try:
                    self._connect_socket()
                except InvalidRPCConnection:
                    # if XBMC is down, sleep a bit then try again
                    # we don't want to enforce a plexmyxbmc restart because we lost connection
                    time.sleep(5)
                    continue
            # this is not a complete implementation
            # there are some loose ends like:
            # if there is an '{' or '}' escaped in a string....
            for i in xrange(len(chunk)):
                c = chunk[i]
                # try to keep track of the delimiters of json messages
                if c == '{':
                    depth += 1
                if c == '}':
                    depth -= 1

                buf += c
                # if the stars align (we found both START and END of a single json msg
                # TODO: make sure that we found at least 1 '{' (start) to avoid cases where
                # TODO: we didnt find '{' and depth will be 0
                if depth == 0:
                    self._process_message(buf)
                    buf = str()

    def _process_message(self, msg):
        msg = json.loads(msg)
        if 'method' in msg:
            # this is an event
            event = msg.get('method')
            self._logger.info('XBMC Event: %s', event)
            handlers = self._events.get(event, [])
            if handlers:
                self._logger.debug('Dispatching %d handler(s)' % len(handlers))
                # TODO: might be better to have only one thread dedicated for callbacks
                # TODO: or just a plain thread pool (remember that subs manager uses these threads
                for handler in handlers:
                    tname = '%s-%d' % (event, handlers.index(handler))
                    Thread(target=handler, args=(msg, ), name=tname).start()
        else:
            # this is an response
            self._response_queue.put(msg)

    def _execute(self, json_data, timeout=None):
        with self._execute_lock:
            self._socket.sendall(json_data)
            return self._response_queue.get(timeout=timeout)


class XbmcHTTPRPC(XbmcRPC):
    def __init__(self, host, port, username='xbmc', password='xbmc'):
        super(XbmcHTTPRPC, self).__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.url = 'http://%s:%d/jsonrpc' % (self.host, self.port)
        _auth = '%s:%s' % (self.username, self.password)
        self._headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'PlexMyXBMC',
            'Authorization': _auth.encode('base64').strip()
        }

    def _execute(self, json_data, timeout=None):
        req = urllib2.Request(self.url, json_data, self._headers)
        return urllib2.urlopen(req).read().strip()
