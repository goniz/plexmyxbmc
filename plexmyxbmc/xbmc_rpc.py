import json
import urllib2
import socket
from Queue import Queue
from threading import Lock, Thread


class InvalidRPCConnection(Exception):
    pass


class XbmcRPC(object):
    def __init__(self):
        self._lock = Lock()
        self._id = 0

    def _execute(self, json_data):
        raise NotImplementedError()

    def execute(self, method, args):
        with self._lock:
            params = dict(jsonrpc='2.0', id=self._id, method=method, params=args)
            self._id += 1

        data = json.dumps(params)
        try:
            resp = self._execute(data)
        except Exception as e:
            print str(e)
            return None

        if len(resp) > 0:
            if isinstance(resp, (str, unicode)):
                resp = json.loads(resp)
            if resp.get('result') is None:
                raise Exception(resp)
            return resp['result']
        return None

    def verify(self):
        res = self.execute('JSONRPC.Ping', tuple())
        if res == u'pong':
            return True
        return False


class XbmcJSONRPC(XbmcRPC):
    def __init__(self, host='localhost', port=9090):
        super(XbmcJSONRPC, self).__init__()
        self._host = host
        self._port = port
        self._events = dict()
        self._socket = None
        self._connect_socket()
        self._response_queue = Queue()
        self._keep_running = False
        self._thread = Thread(target=self._socket_handler_thread)
        self._thread.start()

    def __del__(self):
        self.stop()
        del self._thread

    def _connect_socket(self):
        with self._lock:
            for i in xrange(3):
                try:
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._socket.connect((self._host, self._port))
                    return
                except:
                    continue
            raise InvalidRPCConnection()

    def stop(self):
        self._keep_running = False
        # trigger the thread in order to detect the shutdown request
        self.verify()
        if self._thread.isAlive():
            self._thread.join()

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
        count = 0
        while self._keep_running is True:
            chunk = self._socket.recv(1024)
            if 0 == len(chunk):
                self._socket.close()
                self._connect_socket()
            # this is not a complete implementation
            # there are some loose ends like:
            # if there is an '{' or '}' escaped in a string....
            #TODO: fix this
            depth += chunk.count('{')
            depth -= chunk.count('}')
            buf += chunk
            count += 1

            if (depth == 0) and (count != 0):
                self._process_message(buf)
                buf = str()
                count = 0

    def _process_message(self, msg):
        msg = json.loads(msg)
        if 'method' in msg:
            # this is an event
            event = msg.get('method')
            print 'XBMC Event:', event
            handlers = self._events.get(event, [])
            if handlers:
                print 'Dispatching handlers:', str(handlers)
                #TODO: might be better to have only one thread dedicated for callbacks
                for handler in handlers:
                    Thread(target=handler).start()
        else:
            # this is an response
            self._response_queue.put(msg)

    def _execute(self, json_data):
        self._socket.sendall(json_data)
        return self._response_queue.get()


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

    def _execute(self, json_data):
        req = urllib2.Request(self.url, json_data, self._headers)
        return urllib2.urlopen(req).read().strip()