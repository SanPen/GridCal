"""
.. module:: strategy
   :synopsis: Basic strategy classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

try:
    import Queue
except ImportError:
    import queue as Queue

import copy
import threading
import random
import logging
from collections import deque


# Get module-level logger
logger = logging.getLogger(__name__)


class Proposal(object):
    """Represent a proposed action.

    We currently recognize three types of proposals: evaluation requests
    ("eval"), requests to stop an evaluation ("kill"), and requests
    to terminate the optimization ("terminate").  When an evaluation
    proposal is accepted, the controller adds an evaluation record to the
    proposal before notifying subscribers.

    NB: Callbacks that handle proposal accept/reject should be
    insensitive to order: it is important *not* to modify attributes
    that might be used by later callbacks (e.g. the proposal.accepted
    flag).

    Attributes:
        action: String describing the action
        args: Tuple of arguments to pass to the action
        accepted: Flag set on accept/reject decision
        callbacks: Functions to call on accept/reject of action
        record: Evaluation record for accepted evaluation proposals

    """

    def __init__(self, action, *args):
        """Initialize the request.

        Args:
            action: String describing the action
            args:   Tuple of arguments to pass to the action
        """
        self.action = action
        self.args = args
        self.accepted = False
        self.callbacks = []

    def copy(self):
        "Make a copy of the proposal."
        proposal = copy.copy(self)
        proposal.callbacks = copy.copy(self.callbacks)
        return proposal

    def add_callback(self, callback):
        "Add a callback subscriber to the action."
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        "Remove a callback subscriber."
        self.callbacks = [c for c in self.callbacks if c != callback]

    def accept(self):
        "Mark the action as accepted and execute callbacks."
        logger.debug("Running callbacks on proposal accept")
        self.accepted = True
        for callback in self.callbacks:
            callback(self)

    def reject(self):
        "Mark action as rejected and execute callbacks."
        logger.debug("Running callbacks on proposal reject")
        self.accepted = False
        for callback in self.callbacks:
            callback(self)


class EvalRecord(object):
    """Represent progress of a function evaluation.

    An evaluation record includes the evaluation point, status of the
    evaluation, and a list of callbacks.  The status may be pending,
    running, killed (deliberately), cancelled (due to a crash or
    failure) or completed.  Once the function evaluation is completed,
    the value is stored as an attribute in the evaluation record.
    Other information, such as gradients, Hessians, or function values
    used to compute constraints, may also be stored in the record.

    The evaluation record callbacks are triggered on any relevant
    event, including not only status changes but also intermediate
    results.  The nature of these intermediate results (lower bounds,
    initial estimates, etc) is somewhat application-dependent.

    NB: Callbacks that handle record updates should be insensitive to
    order: it is important *not* to modify attributes that might be
    used by later callbacks (e.g. the proposal.accepted flag).

    Attributes:
        params: Evaluation point for the function
        status: Status of the evaluation (pending, running, killed, completed)
        value: Return value (if completed)
        callbacks: Functions to call on status updates

    """

    def __init__(self, params, extra_args=None, status='pending'):
        """Initialize the record.

        Args:
            params: Evaluation point for the function
            extra_args: Extra arguments to be sent to the worker
        Kwargs:
            status: Status of the evaluation (default 'pending')
        """
        self.params = params
        self.extra_args = extra_args
        self._status = status
        self.value = None
        self.callbacks = []

    def add_callback(self, callback):
        "Add a callback for update events."
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        "Remove a callback subscriber."
        self.callbacks = [c for c in self.callbacks if c != callback]

    def update(self, **kwargs):
        "Update fields and execute callbacks."
        logger.debug("Running callbacks on feval update")
        if kwargs is not None:
            for key, value in kwargs.items():
                setattr(self, key, value)
        for callback in self.callbacks:
            callback(self)

    def update_dict(self, dict):
        """Update fields and execute callbacks.

        Args:
            dict: Dictionary of attributes to set on the record
        """
        self.update(**dict)

    def running(self):
        "Change status to 'running' and execute callbacks."
        if self.is_done:
            logger.error("Cannot update record that is done [running]")
        assert not self.is_done, "Cannot change complete to running"
        self.update(_status='running')

    def kill(self):
        "Change status to 'killed' and execute callbacks."
        if self.is_done:
            logger.error("Cannot update record that is done [kill]")
        assert not self.is_done, "Cannot change complete to killed"
        self.update(_status='killed')

    def cancel(self):
        "Change status to 'cancelled' and execute callbacks."
        if self.is_done:
            logger.error("Cannot update record that is done [cancel]")
        assert not self.is_done, "Cannot change complete to cancelled"
        self.update(_status='cancelled')

    def complete(self, value):
        "Change status to 'completed' and execute callbacks."
        if self.is_done:
            logger.error("Cannot update record that is done [complete]")
        assert not self.is_done, "Cannot re-complete"
        self.update(_status='completed', value=value)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, v):
        assert not self.is_done, "Cannot complete already-completed record"

    @property
    def is_pending(self):
        "Check if status is pending."
        return self._status == 'pending'

    @property
    def is_running(self):
        "Check if status is running."
        return self._status == 'running'

    @property
    def is_completed(self):
        "Check for successful completion of evaluation"
        return self._status == 'completed'

    @property
    def is_killed(self):
        "Check whether evaluation is killed"
        return self._status == 'killed'

    @property
    def is_cancelled(self):
        "Check whether evaluation was cancelled"
        return self._status == 'cancelled'

    @property
    def is_done(self):
        "Check whether the status indicates the evaluation is finished."
        return (self._status == 'completed' or
                self._status == 'killed' or
                self._status == 'cancelled')


class BaseStrategy(object):
    """Base strategy class.

    The BaseStrategy class provides some support for the basic callback
    flow common to most strategies: handlers are called when an evaluation
    is accepted or rejected; and if an evaluation proposal is accepted,
    the record is decorated so that an on_update handler is called for
    subsequent updates.

    Note that not all strategies follow this pattern -- the only requirement
    for a strategy is that it implement propose_action.
    """

    def propose_eval(self, *args):
        "Generate an eval proposal with a callback to on_reply."
        proposal = Proposal('eval', *args)
        proposal.add_callback(self.on_reply)
        return proposal

    def propose_kill(self, r):
        "Generate a kill proposal with a callback to on_reply_kill."
        proposal = Proposal('kill', r)
        proposal.add_callback(self.on_kill_reply)
        return proposal

    def propose_terminate(self):
        "Generate a terminate proposal with a callback to on_terminate."
        proposal = Proposal('terminate')
        proposal.add_callback(self.on_terminate_reply)
        return proposal

    def decorate_proposal(self, proposal):
        "Add a callback to an existing proposal (for nested strategies)."
        if proposal is None:
            return proposal
        elif proposal.action == 'eval':
            proposal.add_callback(self.on_reply)
        elif proposal.action == 'kill':
            proposal.add_callback(self.on_kill_reply)
        elif proposal.action == 'terminate':
            proposal.add_callback(self.on_terminate_reply)
        return proposal

    def on_reply(self, proposal):
        "Default handling of eval proposal."
        logger.debug("Receive proposal reply at base strategy")
        if proposal.accepted:
            logger.debug("Add on_update callback to record")
            proposal.record.add_callback(self.on_update)
            self.on_reply_accept(proposal)
        else:
            self.on_reply_reject(proposal)

    def on_reply_accept(self, proposal):
        "Handle proposal acceptance."
        pass

    def on_reply_reject(self, proposal):
        "Handle proposal rejection."
        pass

    def on_kill_reply(self, proposal):
        "Default handling of kill proposal."
        logger.debug("Received kill proposal reply at base strategy")
        if proposal.accepted:
            self.on_kill_reply_accept(proposal)
        else:
            self.on_kill_reply_reject(proposal)

    def on_kill_reply_accept(self, proposal):
        "Handle proposal acceptance."
        pass

    def on_kill_reply_reject(self, proposal):
        "Handle proposal rejection."
        pass

    def on_terminate_reply(self, proposal):
        "Default handling of terminate proposal."
        logger.debug("Received terminate proposal reply at base strategy")
        if proposal.accepted:
            self.on_terminate_reply_accept(proposal)
        else:
            self.on_terminate_reply_reject(proposal)

    def on_terminate_reply_accept(self, proposal):
        "Handle proposal acceptance."
        pass

    def on_terminate_reply_reject(self, proposal):
        "Handle proposal rejection."
        pass

    def on_update(self, record):
        "Process update."
        if record.is_completed:
            logger.debug("Received record completed at base strategy")
            self.on_complete(record)
        elif record.is_done:
            logger.debug("Received record killed at base strategy")
            self.on_kill(record)
        else:
            logger.debug("Intermediate record update at base strategy")

    def on_complete(self, record):
        "Process completed record."
        pass

    def on_kill(self, record):
        "Process killed or cancelled record."
        pass


class RetryStrategy(BaseStrategy):
    """Retry strategy class.

    The RetryStrategy class manages a queue of proposals to be retried,
    either because they were rejected or because they correspond to
    a function evaluation that was killed.

    If a proposal is submitted to a retry strategy and it has already
    been marked with the .retry attribute, we do not attempt to manage
    retries, as another object is assumed to have taken responsibility
    for retrying the proposal on failure.  This prevents us from having
    redundant retries.

    When a proposal is submitted to the retry class, we make a copy
    (the proposal draft) for safe-keeping.  If at any point it is
    necessary to resubmit, we submit the draft copy to the retry
    class.  The draft will have any modifications or callbacks that
    were added before the proposal reached this strategy, and none of
    those that were added afterward (including those added afterward
    by the RetryStrategy itself).  The intent is that retried
    proposals inserted into the strategy hierarchy at the place where
    they were recorded should require no special treatment to avoid
    adding multiple copies of callbacks (for example).

    Attributes:
        proposals: Queue of outstanding proposals
        num_eval_pending: Number of pending evaluations
        num_eval_running: Number of running evaluations
        num_eval_outstanding: Number of outstanding evaluations
    """

    def __init__(self):
        self.proposals = deque([])
        self.num_eval_pending = 0
        self.num_eval_running = 0
        self._in_flight = {}

    @property
    def num_eval_outstanding(self):
        "Number of outstanding function evaluations."
        return self.num_eval_pending + self.num_eval_running

    def put(self, proposal):
        "Put a non-retry proposal in the queue."
        self.proposals.append(proposal)

    def rput(self, proposal):
        "Put a retry proposal in the queue."
        if not hasattr(proposal, 'retry'):
            logger.debug("Setting up retry")
            self._set(proposal, proposal.copy())
            self.retry = True
            if proposal.action == 'eval':
                proposal.add_callback(self.on_reply)
                self.num_eval_pending += 1
            elif proposal.action == 'kill':
                proposal.add_callback(self.on_kill_reply)
            elif proposal.action == 'terminate':
                proposal.add_callback(self.on_terminate_reply)
        else:
            logger.debug("Skip retry setup -- already under management")
        self.put(proposal)

    def get(self):
        "Pop a proposal from the queue."
        if self.proposals:
            return self.proposals.popleft()

    def empty(self):
        "Check if the queue is empty"
        return not self.proposals

    def on_reply_accept(self, proposal):
        "Process accepted eval+retry proposal"
        logger.debug("Recording accepted eval+retry proposal")
        self.num_eval_pending -= 1
        self.num_eval_running += 1
        self._rekey(proposal, proposal.record)

    def on_reply_reject(self, proposal):
        "Resubmit rejected eval+retry proposal"
        self.num_eval_pending -= 1
        self._resubmit(proposal)

    def on_kill_reply_reject(self, proposal):
        "Resubmit rejected kill+retry proposal"
        self._resubmit(proposal)

    def on_terminate_reply_reject(self, proposal):
        "Resubmit rejected termination+retry proposal"
        self._resubmit(proposal)

    def on_complete(self, record):
        "Clean up after completed eval+retry"
        logger.debug("Clean up after complete eval+retry")
        self.num_eval_running -= 1
        self._pop(record)

    def on_kill(self, record):
        "Resubmit proposal for killed or cancelled eval+retry"
        self.num_eval_running -= 1
        self._resubmit(record)

    def _set(self, key, proposal):
        "Record a retry proposal draft associated with a given key."
        self._in_flight[id(key)] = proposal

    def _pop(self, key):
        "Pop a retry proposal draft from the in-flight dictionary"
        return self._in_flight.pop(id(key))

    def _rekey(self, old_key, new_key):
        "Change the key on a retry proposal draft."
        logger.debug("Rekey retry proposal")
        self._set(new_key, self._pop(old_key))

    def _resubmit(self, key):
        "Recycle a previously-submitted retry proposal."
        logger.debug("Resubmitting retry proposal")
        self.rput(self._pop(key))


class FixedSampleStrategy(BaseStrategy):
    """Sample at a fixed set of points.

    The fixed sampling strategy is appropriate for any non-adaptive
    sampling scheme.  Since the strategy is non-adaptive, we can
    employ as many available workers as we have points to process.  We
    keep trying any evaluation that fails, and suggest termination
    only when all evaluations are complete.  The points in the
    experimental design can be provided as any iterable object (e.g. a
    list or a generator function).  One can use a generator for an
    infinite sequence if the fixed sampling strategy is used in
    combination with a strategy that provides a termination criterion.
    """

    def __init__(self, points):
        """Initialize the sampling scheme.

        Args:
            points: Points list or generator function.
        """
        def point_generator():
            "Generator wrapping the points list."
            for point in points:
                yield point
        self.point_generator = point_generator()
        self.retry = RetryStrategy()

    def propose_action(self):
        "Propose an action based on outstanding points."
        try:
            if self.retry.empty():
                logger.debug("Getting new point from fixed schedule")
                point = next(self.point_generator)
                proposal = self.propose_eval(point)
                self.retry.rput(proposal)
            return self.retry.get()
        except StopIteration:
            logger.debug("Done fixed schedule; {0} outstanding evals".format(
                self.retry.num_eval_outstanding))
            if self.retry.num_eval_outstanding == 0:
                return self.propose_terminate()


class CoroutineStrategy(BaseStrategy):
    """Event-driven to serial adapter using coroutines.

    The coroutine strategy runs a standard sequential optimization algorithm
    in a Python coroutine, with which the strategy communicates via send/yield
    directives.  The optimization coroutine yields the parameters at which
    it would like function values; the strategy then requests the function
    evaluation and returns the value with a send command when it becomes
    available.

    Attributes:
        coroutine: Optimizer coroutine
        rvalue:    Function to map records to values
        retry:     Retry manager
    """

    def __init__(self, coroutine, rvalue=lambda r: r.value):
        "Initialize the strategy."
        self.coroutine = coroutine
        self.rvalue = rvalue
        self.retry = RetryStrategy()
        try:
            logger.debug("Get first point proposal from coroutine")
            self.retry.rput(self.propose_eval(next(self.coroutine)))
        except StopIteration:
            logger.debug("Coroutine returned without yield")
            self.retry.rput(self.propose_terminate())

    def propose_action(self):
        "If we have a pending request, propose it."
        if not self.retry.empty():
            return self.retry.get()

    def on_complete(self, record):
        "Return point to coroutine"
        try:
            logger.debug("Return value to coroutine")
            params = self.coroutine.send(self.rvalue(record))
            logger.debug("Set up next point proposal from coroutine")
            self.retry.rput(self.propose_eval(params))
        except StopIteration:
            logger.debug("Coroutine returned without yield")
            self.retry.rput(self.propose_terminate())


class CoroutineBatchStrategy(BaseStrategy):
    """Event-driven to synchronous parallel adapter using coroutines.

    The coroutine strategy runs a synchronous parallel optimization
    algorithm in a Python coroutine, with which the strategy
    communicates via send/yield directives.  The optimization
    coroutine yields batches of parameters (as lists) at which it
    would like function values; the strategy then requests the
    function evaluation and returns the records associated with those
    function evaluations when all have been completed.

    NB: Within a given batch, function evaluations are attempted in
    the reverse of the order in which they are specified.  This should
    make no difference for most things (the batch is not assumed to have
    any specific order), but it is significant for testing.

    Attributes:
        coroutine: Optimizer coroutine
        retry:     Retry strategy for in-flight actions
        results:   Completion records to be returned to the coroutine
    """

    def __init__(self, coroutine, rvalue=lambda r: r.value):
        self.coroutine = coroutine
        self.rvalue = rvalue
        self.retry = RetryStrategy()
        self.results = []
        try:
            logger.debug("Get first proposed batch from coroutine")
            self.start_batch(next(self.coroutine))
        except StopIteration:
            pass

    def start_batch(self, xs):
        "Start evaluation of a batch of points."
        for ii in range(len(xs)):
            proposal = self.propose_eval(xs[ii])
            proposal.batch_id = ii
            self.retry.rput(proposal)
        self.results = [None for x in xs]

    def propose_action(self):
        "If we have a pending request, propose it."
        try:
            if (self.retry.empty() and self.retry.num_eval_outstanding == 0):
                logger.debug("Return batch to coroutine")
                batch = self.coroutine.send(self.results)
                logger.debug("Queue up next batch from coroutine")
                self.start_batch(batch)
            if not self.retry.empty():
                return self.retry.get()
        except StopIteration:
            logger.debug("Coroutine returned without yield")
            return self.propose_terminate()

    def on_reply_accept(self, proposal):
        "If proposal accepted, wait for result."
        proposal.record.batch_id = proposal.batch_id

    def on_complete(self, record):
        "Return or re-request on completion or cancellation."
        logger.debug("Got batch value ({0}/{1})".format(
            record.batch_id, len(self.results)))
        self.results[record.batch_id] = self.rvalue(record)


class RunTerminatedException(Exception):
    pass


class PromiseStrategy(BaseStrategy):
    """Provides a promise-based asynchronous evaluation interface.

    A promise (aka a future) is a common concurrent programming abstraction.
    A caller requests an asynchronous evaluation, and the call returns
    immediately with a promise object.  The caller can check the promise
    object to see if it has a value ready, or wait for the value to become
    ready.  The callee can set the value when it is ready.

    Attributes:
        proposalq: Queue of proposed actions caused by optimizer.
        valueq:    Queue of function values from proposed actions.
        rvalue:    Function to extract return value from a record
        block:     Flag whether to block on proposal pop
    """

    class Promise(object):
        """Evaluation promise.

        Properties:
            value: Promised value.  Block on read if not ready.
        """

        def __init__(self, valueq):
            self._value = None
            self.valueq = valueq

        def ready(self):
            "Check whether the value is ready (at consumer)"
            logger.debug("Checking if promise ready")
            while not self.valueq.empty():
                msg = self.valueq.get()
                msg()
            logger.debug("Promise ready = {0}".format(self._value is not None))
            return self._value is not None

        @property
        def value(self):
            "Wait on the value (at consumer)"
            logger.debug("Waiting on promise")
            while self._value is None:
                msg = self.valueq.get()
                msg()
            logger.debug("Promise ready")
            return self._value

        @value.setter
        def value(self, fx):
            "Set the value (at producer)"
            logger.debug("Sending value to promise object")
            self.valueq.put(lambda: self._set(fx))

        def _set(self, fx):
            "Set the value (at the consumer)"
            self._value = fx

    # Controller-facing routines

    def __init__(self, rvalue=lambda r: r.value, block=True):
        "Initialize the strategy."
        self.proposalq = Queue.Queue()
        self.valueq = Queue.Queue()
        self.rvalue = rvalue
        self.block = block

    def propose_action(self):
        "Provide proposals from the queue."
        if self.block or not self.proposalq.empty():
            return self.proposalq.get()

    def on_reply_accept(self, proposal):
        "Make sure we copy over the promise to the feval record."
        proposal.record.promise = proposal.promise

    def on_reply_reject(self, proposal):
        "Re-submit the proposal with the same promise."
        new_proposal = self.propose_eval(*proposal.args)
        new_proposal.promise = proposal.promise
        self.proposalq.put(new_proposal)

    def on_terminate_reply_reject(self, proposal):
        "Re-submit the termination proposal."
        self.proposalq.put(self.propose_terminate())

    def on_complete(self, record):
        "Send the value to the consumer via the promise."
        record.promise.value = self.rvalue(record)

    def on_kill(self, record):
        "Re-submit the proposal with the same promise."
        proposal = self.propose_eval(*record.params)
        proposal.promise = record.promise
        self.proposalq.put(proposal)

    def on_terminate(self):
        "Throw an exception at the consumer if still running on termination"
        self.valueq.put(self._throw_terminate)

    # Client-facing routines

    def promise_eval(self, *args):
        "Request a function evaluation and return a promise object."
        logger.debug("Returning promise value")
        proposal = self.propose_eval(*args)
        proposal.promise = self.Promise(self.valueq)
        self.proposalq.put(proposal)
        return proposal.promise

    def blocking_eval(self, *args):
        "Request a function evaluation and block until done."
        return self.promise_eval(*args).value

    def blocking_evals(self, xs):
        "Request a list of function evaluations."
        promises = [self.promise_eval(x) for x in xs]
        return [p.value for p in promises]

    def terminate(self):
        "Request termination."
        logger.debug("PromiseStrategy queueing termination request")
        self.proposalq.put(self.propose_terminate())

    def _throw_terminate(self):
        logger.debug("Stop worker with RunTerminatedException")
        raise RunTerminatedException()


class ThreadStrategy(PromiseStrategy):
    """Event-driven to serial adapter using threads.

    The thread strategy runs a standard sequential optimization algorithm
    in a separate thread of control, with which the strategy communicates
    via promises.  The optimizer thread intercepts function evaluation requests
    and completion and turns them into proposals for the strategy, which
    it places in a proposal queue.  The optimizer then waits for the requested
    values (if any) to appear in the reply queue.

    Attributes:
        optimizer: Optimizer function (takes objective as an argument)
        proposalq: Queue of proposed actions caused by optimizer.
        valueq:    Queue of function values from proposed actions.
        thread:    Thread in which the optimizer runs.
        proposal:  Proposal that the strategy is currently requesting.
        rvalue:    Function mapping records to values
    """

    class OptimizerThread(threading.Thread):
        def __init__(self, strategy, optimizer):
            threading.Thread.__init__(self)
            self.strategy = strategy
            self.optimizer = optimizer

        def run(self):
            try:
                self.optimizer(self.strategy)
            except RunTerminatedException:
                logger.debug("Caught RunTerminatedException in opt thread")
            finally:
                self.strategy.terminate()

    def __init__(self, controller, optimizer, rvalue=lambda r: r.value):
        logger.debug("Initialize ThreadStrategy")
        PromiseStrategy.__init__(self, rvalue, block=False)
        self.thread = self.OptimizerThread(self, optimizer)
        self.thread.start()
        controller.add_term_callback(self.on_terminate)

    def on_terminate(self):
        logger.debug("In ThreadStrategy on_terminate")
        PromiseStrategy.on_terminate(self)
        logger.debug("ThreadStrategy waiting on worker thread join")
        self.thread.join()


class CheckWorkerStrategy(object):
    """Preemptively kill eval proposals when there are no workers.

    A strategy like the fixed sampler is simple-minded, and will
    propose a function evaluation even if the controller has no
    workers available to carry it out.  This wrapper strategy
    intercepts proposals from a wrapped strategy like the fixed
    sampler, and only submits evaluation proposals if workers are
    available.
    """

    def __init__(self, controller, strategy):
        "Initialize checker strategy."
        self.controller = controller
        self.strategy = strategy

    def propose_action(self):
        "Generate filtered action proposal."
        proposal = self.strategy.propose_action()
        if (proposal and proposal.action == 'eval' and
                not self.controller.can_work()):
            logger.debug("Reject eval proposal (no worker available)")
            proposal.reject()
            return None
        return proposal


class SimpleMergedStrategy(object):
    """Merge several strategies by taking the first valid proposal from them.

    The simplest combination strategy is to keep a list of several
    possible strategies in some priority order, query them for
    proposals in priority order, and pass on the first plausible
    proposal to the controller.

    Attributes:
        controller: Controller object used to determine whether we can eval
        strategies: Prioritized list of strategies
    """

    def __init__(self, controller, strategies):
        "Initialize merged strategy."
        self.controller = controller
        self.strategies = strategies

    def propose_action(self):
        "Go through strategies in order and choose the first valid action."
        for strategy in self.strategies:
            proposal = strategy.propose_action()
            if proposal is None:
                pass
            elif proposal.action == 'eval' and not self.controller.can_work():
                logger.debug("Reject eval proposal (no worker available)")
                proposal.reject()
            else:
                return proposal


class MultiStartStrategy(object):
    """Merge several strategies by taking the first valid eval proposal.

    This strategy is similar to the SimpleMergedStrategy, except that we
    only terminate once all the worker strategies have voted to terminate.

    Attributes:
        controller: Controller object used to determine whether we can eval
        strategies: Prioritized list of strategies
    """

    def __init__(self, controller, strategies):
        "Initialize merged strategy."
        self.controller = controller
        self.strategies = strategies

    def propose_action(self):
        """Go through strategies in order and choose the first valid action.
        Terminate iff all workers vote to terminate.
        """
        proposals = [strategy.propose_action() for strategy in self.strategies]
        proposals.reverse()
        chosen_proposal = None
        terminate_votes = 0
        for proposal in proposals:
            if not proposal:
                pass
            elif proposal.action == 'eval' and self.controller.can_work():
                chosen_proposal = proposal
            elif proposal.action == 'kill':
                chosen_proposal = proposal
            elif proposal.action == 'terminate':
                terminate_votes += 1
        for proposal in proposals:
            if proposal is not None and proposal != chosen_proposal:
                proposal.reject()
        if terminate_votes == len(proposals):
            return Proposal("terminate")
        return chosen_proposal


class MaxEvalStrategy(object):
    """Recommend termination of the iteration after some number of evals.

    Recommends termination after observing some number of *completed*
    function evaluations.  We allow more than the requisite number
    of evaluations to be started, since there's always the possibility
    that one of our outstanding evaluations won't finish.

    Attributes:
        counter: Number of completed evals
        max_counter: Max number of evals
    """

    def __init__(self, controller, max_counter):
        """Initialize the strategy.

        Args:
            controller: Used for registering the feval callback
            max_counter: Maximum number of evals desired
        """
        self.counter = 0
        self.max_counter = max_counter
        controller.add_feval_callback(self.on_new_feval)

    def on_new_feval(self, record):
        "On every feval, add a callback."
        record.add_callback(self.on_update)

    def on_update(self, record):
        "On every completion, increment the counter."
        if record.is_completed:
            self.counter += 1
        logger.debug("MaxEvalStrategy: completed {0}/{1}".format(
            self.counter, self.max_counter))

    def propose_action(self):
        "Propose termination once the eval counter is high enough."
        if self.counter >= self.max_counter:
            logger.debug("MaxEvalStrategy: request termination")
            return Proposal('terminate')
        else:
            return None


class InputStrategy(BaseStrategy):
    """Insert requests from the outside world (e.g. from a GUI)."""

    def __init__(self, controller, strategy):
        self.controller = controller
        self.strategy = strategy
        self.retry = RetryStrategy()

    def _propose(self, proposal, retry):
        if retry:
            self.retry.rput(proposal)
        else:
            self.retry.put(proposal)
        self.controller.ping()

    def eval(self, params, retry=True):
        "Request a new function evaluation"
        self._propose(self.propose_eval(params), retry)

    def kill(self, record, retry=False):
        "Request a function evaluation be killed"
        self._propose(self.propose_kill(record), retry)

    def terminate(self, retry=True):
        "Request termination of the optimization"
        self._propose(self.propose_terminate(), retry)

    def propose_action(self):
        if not self.retry.empty():
            return self.retry.get()
        return self.decorate_proposal(self.strategy.propose_action())


class AddArgStrategy(BaseStrategy):
    """Add extra arguments to evaluation proposals.

    Decorates evaluation proposals with extra arguments.  These may
    reflect termination criteria, advice to workers about which of
    several methods to use, etc.  The extra arguments can be static
    (via the extra_args attribute), or they may be returned from the
    get_extra_args function, which child classes can override.
    The strategy *overwrites* any existing list of extra arguments,
    so it is probably a mistake to compose strategies in a way that
    involves multiple objects of this type.

    Attributes:
        strategy: Parent strategy
        extra_args: Extra arguments to be added
    """

    def __init__(self, strategy, extra_args=None):
        self.strategy = strategy
        self.extra_args = extra_args

    def add_extra_args(self, record):
        """Add any extra arguments to an eval record.

        Args:
            record: Record to be decorated
        """
        record.extra_args = self.extra_args

    def on_reply_accept(self, proposal):
        self.add_extra_args(proposal.record)

    def propose_action(self):
        return self.decorate_proposal(self.strategy.propose_action())


class ChaosMonkeyStrategy(object):
    """Randomly kill running function evaluations.

    The ChaosMonkeyStrategy kills function evaluations at random from
    among all active function evaluations.  Attacks are associated
    with a Poisson process where the mean time between failures is
    specified at startup.  Useful mostly for testing the resilience of
    strategies to premature termination of their evaluations.  The
    controller may decide to ignore the proposed kill actions, in
    which case the monkey's attacks are ultimately futile.
    """

    def __init__(self, controller, strategy, mtbf=1):
        """Release the chaos monkey!

        Args:
            controller: The controller whose fevals we will kill
            strategy: Parent strategy
            mtbf: Mean time between failure (assume Poisson process)
        """
        self.controller = controller
        self.strategy = strategy
        self.running_fevals = []
        self.lam = 1.0/mtbf
        self.target = None
        controller.add_feval_callback(self.on_new_feval)
        controller.add_timer(random.expovariate(self.lam), self.on_timer)

    def on_new_feval(self, record):
        "On every feval, add a callback."
        record.chaos_target = False
        record.add_callback(self.on_update)

    def on_update(self, record):
        "On every completion, remove from list"
        if record.is_running and not record.chaos_target:
            record.chaos_target = True
            self.running_fevals.append(record)
        elif record.is_done and record.chaos_target:
            record.chaos_target = False
            self.running_fevals.remove(record)

    def on_timer(self):
        if self.running_fevals:
            record = self.running_fevals.pop()
            record.chaos_target = False
            self.target = record
            self.controller.ping()
        self.controller.add_timer(random.expovariate(self.lam), self.on_timer)

    def propose_action(self):
        if self.target:
            logger.info("Monkey attack! {0}".format(self.target.params))
            proposal = Proposal('kill', self.target)
            self.target = None
        else:
            proposal = self.strategy.propose_action()
        return proposal
