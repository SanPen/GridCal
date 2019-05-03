"""
.. module:: tcpserve
   :synopsis: TCP-based controller server and workers for POAP.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

import time
import socket
import threading
import pickle
import logging

try:
    import socketserver
except ImportError:
    import SocketServer as socketserver

from poap.controller import ThreadController


logger = logging.getLogger(__name__)


class SocketWorkerHandler(socketserver.BaseRequestHandler):
    """Manage a remote worker for a thread controller.

    The SocketWorkerHandler is a request handler for incoming workers.
    It implements the socketserver request handler interface, and also
    the worker interface expected by the ThreadController.
    """

    def eval(self, record):
        "Send an evaluation request to remote worker"
        logger.debug("Send eval to worker")
        self.records[id(record)] = record
        try:
            if record.extra_args is None:
                m = ('eval', id(record), record.params)
            else:
                m = ('eval', id(record), record.params, record.extra_args)
            self.request.send(self.server.marshall(*m))
        except Exception as e:
            logger.warning("In eval: {0}".format(e))
            self._cleanup(record)

    def kill(self, record):
        "Send a kill request to a remote worker"
        logger.debug("Send kill to worker")
        try:
            self.request.send(
                self.server.marshall('kill', id(record)))
        except socket.error as e:
            logger.warning("In kill: {0}".format(e))
            self._cleanup(record)

    def terminate(self):
        "Send a termination request to a remote worker"
        if not self.running:
            return
        logger.debug("Send terminate to worker")
        try:
            self.running = False
            self.request.send(self.server.marshall('terminate'))
            self.request.close()
        except socket.error as e:
            logger.warning("In terminate: {0}".format(e))

    def _handle_message(self, args):
        "Receive a record status message"
        mname = args[0]
        record = self.records[args[1]]
        controller = self.server.controller
        if mname in self.server.message_handlers:
            handler = self.server.message_handlers[mname]
            controller.add_message(lambda: handler(record, *args[2:]))
        else:
            method = getattr(record, mname)
            controller.add_message(lambda: method(*args[2:]))
        if mname == 'complete' or mname == 'cancel' or mname == 'kill':
            logger.debug("Re-queueing worker")
            controller.add_worker(self)

    def _cleanup(self, record):
        "Clean up an incomplete record assigned to this worker."
        def killrec():
            if not record.is_done:
                logger.debug("Kill {0}".format(record.params))
                record.kill()
        self.server.controller.add_message(killrec)

    def handle(self):
        "Main event loop called from SocketServer"
        self.records = {}
        self.running = True
        self.server.controller.add_term_callback(self.terminate)
        try:
            self.server.controller.add_worker(self)
            while self.running:
                logger.debug("Waiting for worker input")
                data = self.request.recv(4096)
                if not data:
                    return
                args = self.server.unmarshall(data)
                self._handle_message(args)
        except socket.error as e:
            logger.debug("Exiting worker: {0}".format(e))
        finally:
            for rec_id, record in self.records.items():
                self._cleanup(record)
            logger.debug("Leaving worker thread")


class ThreadedTCPServer(socketserver.ThreadingMixIn,
                        socketserver.TCPServer, object):
    """SocketServer interface for workers to connect to controller.

    The socket server interface lets workers connect to a given
    TCP/IP port and exchange updates with the controller.

    The server sends messages of the form

        ('eval', record_id, args, extra_args)
        ('eval', record_id, args)
        ('kill', record_id)
        ('terminate')

    The default messages received are

        ('running', record_id)
        ('kill', record_id)
        ('cancel', record_id)
        ('complete', record_id, value)

    The set of handlers can also be extended with a dictionary of
    named callbacks to be invoked whenever a record update comes in.
    For example, to set a lower bound field, we might use the handler

        def set_lb(rec, value):
            rec.lb = value
        handlers = {'lb' : set_lb }

    This is useful for adding new types of updates without mucking
    around in the EvalRecord implementation.

    Attributes:
        controller: ThreadController that manages the optimization
        handlers: dictionary of specialized message handlers
        strategy: redirects to the controller strategy
    """

    def __init__(self, sockname=("localhost", 0), strategy=None, handlers={}):
        """Initialize the controller on the given (host,port) address

        Args:
            sockname: Socket on which to serve workers
            strategy: Strategy object to connect to controllers
            handlers: Dictionary of specialized message handlers
        """
        super(ThreadedTCPServer, self).__init__(sockname, SocketWorkerHandler)
        self.message_handlers = handlers
        self.controller = ThreadController()
        self.controller.strategy = strategy
        self.controller.add_term_callback(self.shutdown)

    def marshall(self, *args):
        "Convert an argument list to wire format."
        return pickle.dumps(args)

    def unmarshall(self, data):
        "Convert wire format back to Python arg list."
        return pickle.loads(data)

    @property
    def strategy(self):
        return self.controller.strategy

    @strategy.setter
    def strategy(self, strategy):
        self.controller.strategy = strategy

    @property
    def sockname(self):
        return self.socket.getsockname()

    def run(self, merit=lambda r: r.value, filter=None):
        thread = threading.Thread(target=self.controller.run)
        thread.start()
        self.serve_forever()
        thread.join()
        return self.controller.best_point(merit=merit, filter=filter)


class SocketWorker(object):
    """Base class for workers that connect to SocketServer interface

    The socket server interface is a server to which workers can
    connect.  The socket worker is the client to that interface.  It
    connects to a given TCP/IP port, then attempts to do work on the
    controller's behalf.

    Attributes:
        running: True if the socket is active
        sock: Worker TCP socket
    """

    def __init__(self, sockname, retries=0):
        """Initialize the SocketWorker.

        The constructor tries to open the socket; on failure, it keeps
        trying up to retries times, once per second.

        Args:
            sockname: (host, port) tuple where server lives
            retries: number of times to retry the connection
        """
        self.running = False
        while not self.running and retries >= 0:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(sockname)
                self.running = True
            except socket.error as e:
                logger.warning("Worker could not connect: {0}".format(e))
                retries -= 1
                time.sleep(1)

    def marshall(self, *args):
        "Marshall data to wire format"
        return pickle.dumps(args)

    def unmarshall(self, data):
        "Convert data from wire format back to Python tuple"
        return pickle.loads(data)

    def send(self, *args):
        "Send a message to the controller"
        self.sock.send(self.marshall(*args))

    def _run(self):
        "Run a message from the controller"
        if not self.running:
            return
        data = self.unmarshall(self.sock.recv(4096))
        method = getattr(self, data[0])
        method(*data[1:])

    def eval(self, record_id, params):
        "Compute a function value"
        pass

    def kill(self, record_id):
        "Kill a function evaluation"
        pass

    def terminate(self):
        "Terminate the worker"
        self.running = False

    def run(self, loop=True):
        "Main loop"
        try:
            self._run()
            while loop and self.running:
                self._run()
        except socket.error as e:
            logger.warning("Exit loop: {0}".format(e))
        finally:
            self.sock.close()


class SimpleSocketWorker(SocketWorker):
    """Simple socket worker that runs a local objective function

    The SimpleSocketWorker is a socket worker that runs a local Python
    function and returns the result.  It is probably mostly useful for
    testing -- the ProcessSocketWorker is a better option for external
    simulations.
    """

    def __init__(self, objective, sockname, retries=0):
        """Initialize the SimpleSocketWorker.

        The constructor tries to open the socket; on failure, it keeps
        trying up to retries times, once per second.

        Args:
            objective: Python objective function
            sockname: (host, port) tuple where server lives
            retries: number of times to retry the connection
        """
        SocketWorker.__init__(self, sockname, retries)
        self.objective = objective

    def eval(self, record_id, params):
        """Evaluate the function and send back a result.

        If the function evaluation crashes, we send back a 'cancel'
        request for the record.  If, on the other hand, there is a
        problem with calling send, we probably want to let the worker
        error out.

        Args:
            record_id: Feval record identifier used by server/controller
            params: Parameters sent to the function to be evaluated
        """
        try:
            msg = ('complete', record_id, self.objective(*params))
        except:
            msg = ('cancel', record_id)
        self.send(*msg)


class ProcessSocketWorker(SocketWorker):
    """Socket worker that runs an evaluation in a subprocess

    The ProcessSocketWorker is a base class for simulations that run a
    simulation in an external subprocess.  This class provides functionality
    just to allow graceful termination of the external simulations.

    Attributes:
        process: Handle for external subprocess
    """

    def __init__(self, sockname, retries=0):
        """Initialize the ProcessSocketWorker.

        The constructor tries to open the socket; on failure, it keeps
        trying up to retries times, once per second.

        Args:
            sockname: (host, port) tuple where server lives
            retries: number of times to retry the connection
        """
        SocketWorker.__init__(self, sockname, retries)
        self.process = None

    def kill_process(self):
        "Kill the child process"
        if self.process is not None and self.process.poll() is None:
            logger.debug("ProcessSocketWorker is killing subprocess")
            self.process.terminate()

    def kill(self, record_id):
        self.kill_process()

    def terminate(self):
        self.kill_process()
        SocketWorker.terminate(self)
