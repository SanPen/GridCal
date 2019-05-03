"""
.. module:: mpiserve
   :synopsis: MPI-based controller server and workers for POAP.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

# NB: Must do mpirun with a working mpi4py install.
#     See https://groups.google.com/forum/#!topic/mpi4py/ULMq-bC1oQA

try:
    import Queue
except ImportError:
    import queue as Queue

import logging

from threading import Thread
from mpi4py import MPI
from poap.controller import Controller

# Get module-level logger
logger = logging.getLogger(__name__)

# Get MPI communicator and rank
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
nproc = comm.Get_size()


class MPIController(Controller):
    """MPI controller.

    The MPI controller *must* run at rank 0.

    The server sends messages of the form
        ('eval', record_id, args, extra_args)
        ('eval', record_id, args)
        ('kill', record_id)
        ('terminate')
    The default messages received are
        ('update_dict', record_id, dict)
        ('running', record_id)
        ('kill', record_id)
        ('cancel', record_id)
        ('complete', record_id, value)
    """

    def __init__(self, strategy=None):
        "Initialize the controller."
        Controller.__init__(self)
        self._workers = [w for w in range(1, nproc)]
        self._recids = {}
        self._needs_ping = False
        self.strategy = strategy
        self.add_term_callback(self._send_shutdown)

    def ping(self):
        "Ping controller to check in with strategies"
        logger.debug("Ping MPIController to check strategies")
        self._needs_ping = False

    def can_work(self):
        "Return whether we can currently perform work."
        return len(self._workers) > 0

    def _handle_message(self):
        """Handle received messages.

        Receive record update messages of the form
            ('action', record_id, params)
        where 'action' is the name of an EvalRecord method and params is
        the list of parameters.  The record_id should be recorded in the
        hub's records table (which happens whenever it is referenced in
        a message sent to a worker).

        On a message indicating that the worker is done with the record,
        we add the worker that sent the message back to the free pool.
        """
        logger.debug("Handle incoming message")
        s = MPI.Status()
        data = comm.recv(status=s, source=MPI.ANY_SOURCE, tag=0)
        logger.debug("Received message: %s", data)
        mname = data[0]
        record = self._recids[data[1]]
        method = getattr(record, mname)
        method(*data[2:])
        if mname == 'complete' or mname == 'cancel' or mname == 'kill':
            logger.debug("Re-queueing worker")
            self._workers.append(s.source)
        self.ping()

    def _submit_work(self, proposal):
        "Create new record and send to worker"
        worker = self._workers.pop()
        record = self.new_feval(proposal.args)
        record.worker = worker
        proposal.record = record
        self._recids[id(record)] = record
        proposal.accept()
        logger.debug("Dispatch eval request to %d", worker)
        if record.extra_args is None:
            m = ('eval', id(record), record.params)
        else:
            m = ('eval', id(record), record.params, record.extra_args)
        comm.send(m, dest=worker, tag=0)

    def _kill_work(self, record):
        "Send a kill request to a worker"
        worker = record.worker
        logger.debug("Dispatch kill request to %d", worker)
        comm.send(('kill', id(record)), dest=worker, tag=0)

    def _send_shutdown(self):
        "Send shutdown requests to all workers"
        for worker in range(1, nproc):
            comm.send(('terminate',), dest=worker, tag=0)

    def _run(self, merit=None, filterp=None):
        "Run the optimization and return the best value."
        while True:
            if comm.Iprobe():
                self._handle_message()
            proposal = None
            if not self._needs_ping:
                proposal = self.strategy.propose_action()
            if not proposal:
                self._handle_message()
            elif proposal.action == 'terminate':
                logger.debug("Accept terminate proposal")
                proposal.accept()
                return self.best_point(merit=merit, filter=filterp)
            elif proposal.action == 'eval' and self.can_work():
                logger.debug("Accept eval proposal")
                self._submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.args[0].is_done:
                logger.debug("Accept kill proposal")
                record = proposal.args[0]
                proposal.accept()
                self._kill_work(record)
            else:
                logger.debug("Reject proposal")
                proposal.reject()
                self._needs_ping = True

    def run(self, merit=None, filterp=None):
        """Run the optimization and return the best value.

        Args:
            merit: Function to minimize (default is r.value)
            filterp: Predicate to use for filtering candidates

        Returns:
            Record minimizing merit() and satisfying filterp();
            or None if nothing satisfies the filter
        """
        try:
            return self._run(merit=merit, filterp=filterp)
        finally:
            self.call_term_callbacks()


class MPIWorker(object):
    """MPI worker process.

    An MPI worker mostly monitors messages from the master.
    It also monitors a local queue in case there is a separate
    computational process or thread generating results.  The
    main routine for the evaluator is eval.
    """

    def __init__(self):
        self._running = False
        self._outbox = Queue.Queue()
        self._eval_thread = None
        self._eval_killed = False
        self.daemonize = False

    def eval(self, record_id, args, extra_args=None):
        "Actually do the function evaluation (separate thread)"
        logger.error("Call to base MPIWorker.eval(%d, %s, %s)",
                     record_id, args, extra_args)

    def _eval_wrap(self, record_id, args, extra_args=None):
        "Wrapper for eval request (handle evaluation crash)"
        try:
            if extra_args is None:
                self.eval(record_id, args)
            else:
                self.eval(record_id, args, extra_args)
        except Exception:
            logger.error("Function evaluation failed")
            self.finish_cancel(record_id)

    def on_eval(self, record_id, args, extra_args=None):
        "Handle eval request."
        logger.debug("In MPIWorker.on_eval")
        self._eval_thread = Thread(target=self._eval_wrap,
                                   args=(record_id, args, extra_args))
        self._eval_thread.daemon = self.daemonize
        self._eval_killed = False
        self._eval_thread.start()
        logger.debug("Returning after worker thread start")

    def on_kill(self, record_id):
        "Handle kill request."
        logger.debug("In MPIWorker.on_kill(%d)", record_id)
        self._eval_killed = True

    def on_terminate(self):
        "Handle termination request."
        logger.debug("In MPIWorker.on_terminate")
        self._running = False

    def send(self, *args):
        "Queue message to process 0 (where the controller lives)."
        logger.debug("Queue outgoing message %s", args)
        self._outbox.put(args)

    def update(self, record_id, **kwargs):
        """Update a function evaluation status with a call to update_dict.

        Args:
            record_id: Identifier for the function evaluation
            kwargs: Named argument values
        """
        self.send('update_dict', record_id, kwargs)

    def running(self, record_id):
        """Indicate that a function evaluation is running.

        Args:
            record_id: Identifier for the function evaluation
        """
        self.send('running', record_id)

    def finish_success(self, record_id, value):
        """Indicate that a function evaluation completed successfully.

        Args:
            record_id: Identifier for the function evaluation
            value: Value returned by the feval
        """
        self.send('complete', record_id, value)

    def finish_cancel(self, record_id):
        """Indicate that a function evaluation was cancelled (at worker).

        Args:
            record_id: Identifier for the function evaluation
        """
        self.send('cancel', record_id)

    def finish_killed(self, record_id):
        """Indicate that a function evaluation was killed (controller request).

        Args:
            record_id: Identifier for the function evaluation
        """
        self.send('kill', record_id)

    def _handle_message(self):
        "Handle an incoming message and dispatch to handler."
        logger.debug("Handle incoming message")
        try:
            s = MPI.Status()
            data = comm.recv(status=s, source=0, tag=0)
            logger.debug("Incoming message received")
            mname = "on_{0}".format(data[0])
            logger.debug("Call to %s%s", mname, data[1:])
            method = getattr(self, mname)
            method(*data[1:])
        except Exception:
            logger.debug("Exception in message handler")

    def run(self):
        "Run the main loop."
        self._running = True
        while self._running:
            if comm.Iprobe():
                self._handle_message()
            elif self._eval_thread and not self._eval_thread.is_alive():
                logger.debug("Join worker eval thread")
                self._eval_thread.join()
                self._eval_thread = None
                logger.debug("Joined eval thread")
            else:
                try:
                    timeout = 0.005
                    msg = self._outbox.get(True, timeout)
                    logger.debug("MPI send to 0: %s", msg)
                    comm.send(msg, dest=0, tag=0)
                    logger.debug("MPI send completed")
                except Queue.Empty:
                    pass


class MPISimpleWorker(MPIWorker):
    """Worker that calls a Python function.

    The MPISimpleWorker does ordinary Python function evaluations.
    Requests to kill a running evaluation are simply ignored.
    """

    def __init__(self, f):
        super(MPISimpleWorker, self).__init__()
        self.f = f

    def eval(self, record_id, params):
        """Evaluate a function at a point.

        Args:
            record_id: Identifier for the function evaluation
            params: Set of parameters
        """
        logger.debug("Eval %d at %s", record_id, params)
        value = self.f(*params)
        self.finish_success(record_id, value)


class MPIProcessWorker(MPIWorker):
    """MPI worker that runs an evaluation in a subprocess

    The MPIProcessWorker is a base class for simulations that run a
    simulation in an external subprocess.  This class provides functionality
    just to allow graceful termination of the external simulations.

    Attributes:
        process: Handle for external subprocess
    """

    def __init__(self):
        super(MPIProcessWorker, self).__init__()
        self.process = None

    def kill_process(self):
        "Kill the child process"
        if self.process is not None and self.process.poll() is None:
            logger.debug("MPIProcessWorker is killing subprocess")
            self.process.terminate()

    def on_kill(self, record_id):
        self._eval_killed = True
        self.kill_process()

    def on_terminate(self):
        self.kill_process()
        super(MPIProcessWorker, self).on_terminate()
