"""
.. module:: controller
   :synopsis: Basic controller classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>

Modified to fit GridCal's purposes when using PySOT
"""

try:
    import Queue
except ImportError:
    import queue as Queue

import sys
import heapq
import threading
import logging
import time
from GridCal.Engine.Replacements.strategy import EvalRecord


# Get module-level logger
logger = logging.getLogger(__name__)


class Controller(object):
    """Base class for controller.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        fevals: Database of function evaluations.
        feval_callbacks: List of callbacks to execute on new eval record
        term_callbacks: List of callbacks to execute on termination
    """

    def __init__(self):
        "Initialize the controller."
        logger.debug("Initialize controller")
        self.strategy = None
        self.fevals = []
        self.feval_callbacks = []
        self.term_callbacks = []

    def add_timer(self, timeout, callback):
        """Add a task to be executed after a timeout (e.g. for monitoring).

        Args:
            timeout: Time to wait before execution
            callback: Function to call when timeout elapses
        """
        thread = threading.Timer(timeout, callback)
        thread.daemon = True
        thread.start()

    def ping(self):
        "Tell controller to consult strategies when possible (if asynchronous)"
        pass

    def can_work(self):
        "Return whether we can currently perform work."
        return True

    def best_point(self, merit=None, filter=None):
        """Return the best point in the database satisfying some criterion.

        Args:
            merit: Function to minimize (default is r.value)
            filter: Predicate to use for filtering candidates

        Returns:
            Record minimizing merit() and satisfying filter();
            or None if nothing satisfies the filter
        """
        if filter is None:
            fcomplete = [f for f in self.fevals if f.is_completed]
        else:
            fcomplete = [f for f in self.fevals
                         if f.is_completed and filter(f)]
        if merit is None:
            def merit(r):
                return r.value
        if fcomplete:
            return min(fcomplete, key=merit)

    def new_feval(self, params, extra_args=None):
        """Add a function evaluation record to the database.

        In addition to adding the record with status 'pending',
        we run the feval_callbacks on the new record.

        Args:
            params: Parameters to the objective function

        Returns:
            New EvalRecord object
        """
        record = EvalRecord(params, extra_args=extra_args, status='pending')
        self.fevals.append(record)
        logger.debug("Call new feval callbacks")
        for callback in self.feval_callbacks:
            callback(record)
        return record

    def call_term_callbacks(self):
        "Call termination callbacks."
        logger.debug("Call termination callbacks")
        for callback in self.term_callbacks:
            callback()

    def add_term_callback(self, callback):
        "Add a callback for cleanup on termination."
        self.term_callbacks.append(callback)

    def add_feval_callback(self, callback):
        "Add a callback for notification on new fevals."
        self.feval_callbacks.append(callback)

    def remove_term_callback(self, callback):
        "Remove a callback from the term callback list."
        self.term_callbacks = [
            c for c in self.term_callbacks if c != callback
        ]

    def remove_feval_callback(self, callback):
        "Remove a callback from the feval callback list."
        self.feval_callbacks = [
            c for c in self.feval_callbacks if c != callback
        ]


class SerialController(Controller):
    """Serial optimization controller.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        objective: Objective function
        fevals: Database of function evaluations
        skip: if True, skip over "None" proposals
    """

    def __init__(self, objective, skip=False):
        """Initialize the controller.

        Args:
            objective: Objective function
            skip: if True, skip over "None" proposals
        """
        Controller.__init__(self)
        self.objective = objective
        self.skip = skip

    def _run(self, merit=None, filter=None, reraise=True, stop_at=False, stop_value=0):
        "Run the optimization and return the best value."
        while True:
            proposal = self.strategy.propose_action()
            if not proposal:
                if not self.skip:
                    raise NameError('No proposed action')
            elif proposal.action == 'terminate':
                logger.debug("Accept termination proposal")
                proposal.accept()
                return self.best_point(merit=merit, filter=filter)
            elif proposal.action == 'eval':
                logger.debug("Accept eval proposal")
                proposal.record = self.new_feval(proposal.args)
                proposal.accept()
                try:
                    value = self.objective(*proposal.record.params)
                    proposal.record.complete(value)

                    # brute exit
                    if stop_at:
                        if value == stop_value:
                            return self.best_point(merit=merit, filter=filter)

                except Exception:
                    logger.exception("Error calling objective", exc_info=sys.exc_info())
                    proposal.record.cancel()
                    if reraise:
                        raise
            else:
                logger.debug("Reject proposal")
                proposal.reject()

    def run(self, merit=None, filter=None, reraise=True, stop_at=False, stop_value=0):
        """Run the optimization and return the best value.

        Args:
            merit: Function to minimize (default is r.value)
            filter: Predicate to use for filtering candidates
            reraise: Flag indicating whether exceptions in the
              objective function evaluations should be re-raised,
              terminating the optimization.

        Returns:
            Record minimizing merit() and satisfying filter();
            or None if nothing satisfies the filter
        """
        try:
            return self._run(merit=merit, filter=filter, reraise=reraise, stop_at=stop_at, stop_value=stop_value)
        finally:
            self.call_term_callbacks()


class ThreadController(Controller):
    """Thread-based optimization controller.

    The optimizer dispatches work to a queue of workers.
    Each worker has methods of the form

       worker.eval(record)
       worker.kill(record)

    These methods are asynchronous: they start a function evaluation
    or termination, but do not necessarily complete it.  The worker
    must respond to eval requests, but may ignore kill requests.  On
    eval requests, the worker should either attempt the evaluation or
    mark the record as killed.  The worker sends status updates back
    to the controller in terms of lambdas (executed at the controller)
    that update the relevant record.  When the worker becomes
    available again, it should use add_worker to add itself back to
    the queue.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        fevals: Database of function evaluations
        workers: Queue of available worker threads
        messages: Queue of messages from workers

    """

    def __init__(self):
        "Initialize the controller."
        Controller.__init__(self)
        self.workers = Queue.Queue()
        self.messages = Queue.Queue()

    def ping(self):
        "Tell controller to consult strategies when possible"
        logger.debug("Wake thread controller")
        self.add_message()

    def add_timer(self, timeout, callback):
        """Add a task to be executed after a timeout (e.g. for monitoring).

        Args:
            timeout: Time to wait before execution
            callback: Function to call when timeout elapses
        """
        thread = threading.Timer(timeout, lambda: self.add_message(callback))
        thread.start()

    def add_message(self, message=None):
        """Queue up a message.

        Args:
            message: callback function with no arguments or None (default)
                     if None, a dummy message is queued to ping the controller
        """
        if message is None:
            self.messages.put(lambda: None)
        else:
            self.messages.put(message)

    def add_worker(self, worker):
        """Add a worker and queue a 'wake-up' message.

        Args:
            worker: a worker thread object
        """
        logger.debug("Add worker to thread controller")
        self.workers.put(worker)
        self.ping()

    def launch_worker(self, worker, daemon=False):
        """Launch and take ownership of a new worker thread.

        Args:
            worker: a worker thread object
            daemon: if True, the worker is launched in a daemon thread
                    (default is False)
        """
        logger.debug("Launch worker in thread controller")
        self.add_worker(worker)
        self.add_term_callback(worker.terminate)
        worker.daemon = worker.daemon or daemon
        worker.start()

    def can_work(self):
        "Claim we can work if a worker is available."
        return not self.workers.empty()

    def _submit_work(self, proposal):
        "Submit proposed work."
        try:
            worker = self.workers.get_nowait()
            logger.debug("Accept eval proposal")
            proposal.record = self.new_feval(proposal.args)
            proposal.record.worker = worker
            proposal.accept()
            worker.eval(proposal.record)
        except Queue.Empty:
            logger.debug("Reject eval proposal -- no worker")
            proposal.reject()

    def _run_message(self):
        "Process a message, blocking for one if none is available."
        message = self.messages.get()
        message()

    def _run_queued_messages(self):
        "Process any queued messages."
        while not self.messages.empty():
            self._run_message()

    def _run(self, merit=None, filter=filter):
        "Run the optimization and return the best value."
        while True:
            self._run_queued_messages()
            time.sleep(0)  # Yields to other threads
            proposal = self.strategy.propose_action()
            if not proposal:
                self._run_message()
            elif proposal.action == 'terminate':
                logger.debug("Accept terminate proposal")
                proposal.accept()
                return self.best_point(merit=merit, filter=filter)
            elif proposal.action == 'eval' and self.can_work():
                self._submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.args[0].is_done:
                logger.debug("Accept kill proposal")
                record = proposal.args[0]
                proposal.accept()
                record.worker.kill(record)
            else:
                logger.debug("Reject proposal")
                proposal.reject()

    def run(self, merit=None, filter=None):
        """Run the optimization and return the best value.

        Args:
            merit: Function to minimize (default is r.value)
            filter: Predicate to use for filtering candidates

        Returns:
            Record minimizing merit() and satisfying filter();
            or None if nothing satisfies the filter
        """
        try:
            return self._run(merit=merit, filter=filter)
        finally:
            self.call_term_callbacks()


class BaseWorkerThread(threading.Thread):
    """Worker base class for use with the thread controller.

    The BaseWorkerThread class has a run routine that actually handles
    the worker event loop, and a set of helper routines for
    dispatching messages into the worker event loop (usually from the
    controller) and dispatching messages to the controller (usually
    from the worker).
    """

    def __init__(self, controller):
        "Initialize the worker."
        logger.debug("Initialize worker thread")
        super(BaseWorkerThread, self).__init__()
        self.controller = controller
        self.queue = Queue.Queue()

    def eval(self, record):
        """Start evaluation.

        Args:
            record: Function evaluation record
        """
        logger.debug("Queue eval at worker")
        self.queue.put(('eval', record))

    def kill(self, record):
        """Send kill message to worker.

        Args:
            record: Function evaluation record
        """
        logger.debug("Queue kill at worker")
        self.queue.put(('kill', record))

    def terminate(self):
        """Send termination message to worker.

        NB: if the worker is not running in a daemon thread,
        a call to the terminate method only returns after the
        the thread has terminated.
        """
        logger.debug("Queue terminate at worker")
        self.queue.put(('terminate',))
        if self.daemon:
            logger.debug("Do not wait on thread join (daemon)")
        else:
            logger.debug("Wait on worker thread join")
            self.join()

    def add_message(self, message):
        "Send message to be executed at the controller."
        self.controller.add_message(message)

    def add_worker(self):
        "Add worker back to the work queue."
        logger.debug("Worker thread is ready")
        self.controller.add_worker(self)

    def finish_success(self, record, value):
        "Finish successful work on a record and add ourselves back."
        logger.debug("Finished feval successfully")
        self.add_message(lambda: record.complete(value))
        self.add_worker()

    def finish_killed(self, record):
        "Finish recording killed on a record and add ourselves back."
        logger.debug("Feval killed")
        self.add_message(record.kill)
        self.add_worker()

    def finish_cancelled(self, record):
        "Finish recording cancelled on a record and add ourselves back."
        logger.debug("Feval cancelled")
        self.add_message(record.cancel)
        self.add_worker()

    def handle_eval(self, record):
        "Process an eval request."
        pass

    def handle_kill(self, record):
        "Process a kill request"
        pass

    def handle_terminate(self):
        "Handle any cleanup on a terminate request"
        pass

    def run(self):
        "Run requests as long as we get them."
        while True:
            request = self.queue.get()
            if request[0] == 'eval':
                logger.debug("Worker thread received eval request")
                record = request[1]
                self.add_message(record.running)
                self.handle_eval(record)
            elif request[0] == 'kill':
                logger.debug("Worker thread received kill request")
                self.handle_kill(request[1])
            elif request[0] == 'terminate':
                logger.debug("Worker thread received terminate request")
                self.handle_terminate()
                logger.debug("Exit worker thread run()")
                return


class BasicWorkerThread(BaseWorkerThread):
    """Basic worker for use with the thread controller.

    The BasicWorkerThread calls a Python objective function
    when asked to do an evaluation.  This is concurrent, but only
    results in parallelism if the objective function implementation
    itself allows parallelism (e.g. because it communicates with
    an external entity via a pipe, socket, or whatever).
    """

    def __init__(self, controller, objective):
        "Initialize the worker."
        super(BasicWorkerThread, self).__init__(controller)
        self.objective = objective

    def handle_eval(self, record):
        try:
            value = self.objective(*record.params)
            self.finish_success(record, value)
            logger.debug("Worker finished feval successfully")
        except Exception:
            self.finish_cancelled(record)
            logger.debug("Worker feval exited with exception")


class ProcessWorkerThread(BaseWorkerThread):
    """Subprocess worker for use with the thread controller.

    The ProcessWorkerThread is meant for use as a base class.
    Implementations that inherit from ProcessWorkerThread should
    define a handle_eval method that sets the process field so that it
    can be interrupted if needed.  This allows use of blocking
    communication primitives while at the same time allowing
    interruption.
    """

    def __init__(self, controller):
        "Initialize the worker."
        super(ProcessWorkerThread, self).__init__(controller)
        self.process = None

    def _kill_process(self):
        if self.process is not None and self.process.poll() is None:
            logger.debug("ProcessWorker is killing subprocess")
            self.process.terminate()

    def kill(self, record):
        "Send kill message."
        self._kill_process()
        super(ProcessWorkerThread, self).kill(record)

    def terminate(self):
        "Send termination message."
        self._kill_process()
        super(ProcessWorkerThread, self).terminate()


class SimTeamController(Controller):
    """Simulated parallel optimization controller.

    Run events in simulated time.  If two events are scheduled at the
    same time, we prioritize by when the event was added to the queue.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        objective: Objective function
        delay: Time delay function
        workers: Number of workers available
        fevals: Database of function evaluations
        time: Current simulated time
        time_events: Time-stamped event heap
    """

    def __init__(self, objective, delay, workers):
        """Initialize the controller.

        Args:
            objective: Objective function
            delay: Time delay function (takes no arguments)
            workers: Number of workers available in simulation
        """
        Controller.__init__(self)
        self.objective = objective
        self.delay = delay
        self.workers = workers
        self.time = 0
        self.time_events = []
        self.event_id = 0

    def can_work(self):
        "Check if there are workers available."
        return self.workers > 0

    def submit_work(self, proposal):
        "Submit a work event."
        logger.debug("Accept eval proposal")
        self.workers -= 1
        record = self.new_feval(proposal.args)
        proposal.record = record
        proposal.accept()

        def event():
            "Closure for marking record done at some later point."
            if not record.is_done:
                try:
                    record.complete(self.objective(*record.params))
                    logger.debug("Finished evaluation successfully")
                except Exception:
                    record.cancel()
                    logger.debug("Finished evaluation with exception")
                self.workers += 1

        self.add_timer(self.delay(record), event)

    def kill_work(self, proposal):
        "Submit a kill event."
        logger.debug("Accept kill proposal")
        record = proposal.args[0]
        proposal.accept()

        def event():
            """Closure for canceling a function evaluation
            NB: This is a separate event because it will eventually have delay!
            """
            if not record.is_done:
                logger.debug("Finished killing evaluation")
                record.kill()
                self.workers += 1

        self.add_timer(0, event)

    def advance_time(self):
        "Advance time to the next event."
        assert self.time_events, "Deadlock detected!"
        event_time, event_id, event = heapq.heappop(self.time_events)
        self.time = event_time
        event()

    def add_timer(self, timeout, event):
        """Add a task to be executed after a timeout (e.g. for monitoring).

        Args:
            timeout: Time to wait before execution
            callback: Function to call when timeout elapses
        """
        heapq.heappush(self.time_events,
                       (self.time + timeout, self.event_id, event))
        self.event_id += 1

    def _run(self, merit=None, filter=None):
        "Run the optimization and return the best value."
        while True:
            proposal = self.strategy.propose_action()
            if not proposal:
                logger.debug("Advance")
                self.advance_time()
            elif proposal.action == 'terminate':
                logger.debug("Accepted terminate proposal")
                proposal.accept()
                return self.best_point(merit=merit, filter=filter)
            elif proposal.action == 'eval' and self.can_work():
                self.submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.args[0].is_done:
                self.kill_work(proposal)
            else:
                logger.debug("Reject proposal")
                proposal.reject()
                self.advance_time()

    def run(self, merit=None, filter=None):
        """Run the optimization and return the best value.

        Args:
            merit: Function to minimize (default is r.value)
            filter: Predicate to use for filtering candidates

        Returns:
            Record minimizing merit() and satisfying filter();
            or None if nothing satisfies the filter
        """
        try:
            return self._run(merit=merit, filter=filter)
        finally:
            self.call_term_callbacks()


class ScriptedController(Controller):
    """Run a test script of actions from the controller.

    The ScriptedController is meant to test that a strategy adheres
    to an expected sequence of proposed actions in a given scenario.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        fevals: Database of function evaluations
    """

    def __init__(self):
        Controller.__init__(self)
        self._can_work = True

    def add_timer(self, timeout, callback):
        "Add timer."
        assert False, "Timers not available in ScriptedController."

    def can_work(self):
        "Return True if worker available."
        return self._can_work

    def proposal(self, skip=False):
        """Return strategy proposal.

        Args:
            skip: if True, skip over all None proposals
        """
        proposal = self.strategy.propose_action()
        while skip and proposal is None:
            proposal = self.strategy.propose_action()
        return proposal

    def set_worker(self, v):
        "Set worker availability status."
        self._can_work = v

    def check_eval(self, proposal, args=None, pred=None):
        """Check whether a proposal is an expected eval proposal.

        Args:
            proposal: proposal to check
            args: expected evaluation args (if not None)
            pred: test predicate to run on proposal (if not None)
        """
        assert proposal is not None, \
            "Expected eval, got None"
        assert proposal.action == 'eval', \
            "Expected eval, got {0}".format(proposal.action)
        if args is not None:
            assert proposal.args == args, \
                "Expected eval at {0}, got {1}".format(args, proposal.args)
        if pred is not None:
            assert pred(proposal), \
                "Eval at {0} does not fit predicate".format(args)
        return proposal

    def check_kill(self, proposal, r=None):
        """Check whether a proposal is an expected kill proposal.

        Args:
            proposal: proposal to check
            r: record to be killed (or None if no check)
        """
        assert proposal is not None, \
            "Expected eval, got None"
        assert proposal.action == 'kill', \
            "Expected kill, got {0}".format(proposal.action)
        if r is not None:
            assert proposal.args[0] == r, \
                "Expected kill, but not at {0}".format(r.params)
        return proposal

    def check_terminate(self, proposal):
        """Check whether a proposal is an expected terminate proposal.

        Args:
            proposal: proposal to check
        """
        assert proposal is not None, \
            "Expected terminate, got None"
        assert proposal.action == 'terminate', \
            "Expected terminate, got {0}".format(proposal.action)
        return proposal

    def no_proposal(self):
        "Assert that next proposed action is None."
        logger.debug("Script: No proposal")
        assert self.proposal() is None

    def accept_eval(self, args=None, pred=None, skip=False):
        """Assert next proposal is an eval, which we accept.

        Args:
            args: expected evaluation args (if not None)
            pred: test predicate to run on proposal (if not None)
            skip: if True, skip over all None proposals

        Returns:
            proposal record
        """
        logger.debug("Script: accept proposal")
        proposal = self.proposal(skip=skip)
        proposal = self.check_eval(proposal, args=args, pred=pred)
        proposal.record = self.new_feval(proposal.args)
        proposal.accept()
        return proposal.record

    def accept_kill(self, r=None, skip=False):
        """Assert next proposal is a kill, which we accept.

        Args:
            r: record to be killed.
            skip: if True, skip over all None proposals
        """
        logger.debug("Script: accept kill")
        self.check_kill(self.proposal(skip=skip), r).accept()

    def accept_terminate(self, skip=False):
        """Assert next proposal is a kill, which we accept.

        Args:
            skip: if True, skip over all None proposals
        """
        logger.debug("Script: accept terminate")
        self.check_terminate(self.proposal(skip=skip)).accept()

    def reject_eval(self, args=None, pred=None, skip=False):
        """Assert next proposal is an eval, which we reject.

        Args:
            args: expected evaluation args (if not None)
            pred: test predicate to run on proposal (if not None)
            skip: if True, skip over all None proposals
        """
        logger.debug("Script: reject eval")
        proposal = self.proposal(skip=skip)
        self.check_eval(proposal, args=args, pred=pred).reject()

    def reject_kill(self, r=None, skip=False):
        """Assert next proposal is a kill, which we reject.

        Args:
            r: record to be killed.
            skip: if True, skip over all None proposals
        """
        logger.debug("Script: reject kill")
        self.check_kill(self.proposal(skip=skip), r).reject()

    def reject_terminate(self, skip=False):
        """Assert next proposal is a terminate, which we reject.

        Args:
            skip: if True, skip over all None proposals
        """
        logger.debug("Script: reject terminate")
        self.check_terminate(self.proposal(skip=skip)).reject()

    def terminate(self):
        "Terminate the script."
        logger.debug("Script: Terminate")
        self.call_term_callbacks()


class Monitor(object):
    """Monitor events observed by a controller.

    The monitor object provides hooks to monitor the progress of an
    optimization run by a controller.  Users should inherit from Monitor
    and add custom version of the methods

        on_new_feval(self, record)
        on_update(self, record)
        on_complete(self, record)
        on_kill(self, record)
        on_cancel(self, record)
        on_terminate(self)
    """

    def __init__(self, controller):
        """Initialize the monitor.

        Args:
            controller: The controller whose fevals we will monitor
        """
        self.controller = controller
        controller.add_feval_callback(self._add_on_update)
        controller.add_feval_callback(self.on_new_feval)
        controller.add_term_callback(self.on_terminate)

    def _add_on_update(self, record):
        "Internal handler -- add on_update callback to all new fevals."
        record.add_callback(self.on_update)

    def on_new_feval(self, record):
        "Handle new function evaluation request."
        pass

    def on_update(self, record):
        "Handle feval update."
        if record.is_completed:
            self.on_complete(record)
        elif record.is_killed:
            self.on_kill(record)
        elif record.is_cancelled:
            self.on_cancel(record)

    def on_complete(self, record):
        "Handle feval completion"
        pass

    def on_kill(self, record):
        "Handle record killed"
        pass

    def on_cancel(self, record):
        "Handle record cancelled"
        pass

    def on_terminate(self):
        "Handle termination."
        pass
