__doc__ = """
Implementation of an Event-Driven State Machine.

States inherit from the State class and can implement the methods
'handleMessage', 'handleEvent', 'handleTimer' as needed.  If the
triggered one is not implemented, the state object will be called
itself (__call__) without arguments.

The 'accepts' method must be reimplemented to decide whether a
transition is acceptable by this state.  Specialized subclasses are
available for convenience that only accept their specific type of
transition, i.e. messages, events or timers.

The state methods must return reentrant iterators.  Each step of the
EDMS calls them a number of times and lets them yield a number of
items.  These are forwarded to the respective successor states.
Special return items are State.TERMINATED, State.ADVANCE_ONLY and
State.YIELD.

TERMINATED deletes the state immediately.

ADVANCE_ONLY terminates the execution, but continues waiting for the
first event (timer, message, ...) to advance from this state before
deleting it.  Note that only one event will be waited for and timers
that have not fired yet will be cancelled when advancing.

YIELD postbones the execution of the iterator for later continuation.
This can be used to cut down longer calculations into chunks and to
free the CPU in between.
"""

from itertools import *

from slow.model.edsm_model import EDSMTransition

############################################################
# Run-time transition base classes for the EDSM
# (the construction is done from the edsm model!)
############################################################

class Transition(object):
    TYPE = None
    def __init__(self, name):
        self.name = name
    def type(self):
        return self.TYPE

class Message(Transition):
    TYPE = EDSMTransition.TYPE_MESSAGE

class Event(Transition):
    TYPE = EDSMTransition.TYPE_VIEW_EVENT

class DirectTransition(Transition):
    TYPE = EDSMTransition.TYPE_TRANSITION


############################################################
# Timers
############################################################

class Timer(Transition):
    TYPE = EDSMTransition.TYPE_TIMER
    def __init__(self, name, destinations, delay):
        self.destinations, self.delay = destinations, delay
        self.name = name

    class __Timer(object):
        from time import time as current_time
        def __init__(self, timer):
            self.timer = timer
            delay = timer.delay
            self.destinations = timer.destinations
            self.running  = True
            self.delay    = int(delay)
            self.deadline = self.current_time() + delay / 1000.0
        def remaining(self):
            return self.deadline - self.current_time()
        def has_fired(self):
            return self.current_time() >= self.deadline
        def cancel(self):
            self.running = False

    def new_timer(self):
        return self.__Timer(self)

############################################################
# EDSM implementation
############################################################

from helpers import TimerQueue
from states import State

NEVER = TimerQueue.INFINITY

class StateMachine(object):
    def __init__(self, state_table, start_states, global_context):
        self.state_table  = state_table
        self.start_states = start_states
        self.running_states = []
        self.waiting_states = []
        self._setup_state_controller(global_context)

    def _setup_state_controller(self, global_context):
        state_controller = self.StateController(self)
        self.state_controller = state_controller
        global_context['state_controller'] = state_controller

    class StateStatus(object):
        def __init__(self, state):
            self.state  = state
            self.status = None
            self._queue_timers = getattr(state, 'queue_timers', None)
            self.timers = ()
            self.generator = None

        def has_timers(self):
            try:
                return self.state.has_timers()
            except AttributeError:
                return False

        def start(self, method_name=None, handler_getter=None, item=None):
            self.status = State.RUNNING
            queue_timers = self._queue_timers
            if queue_timers:
                self.timers = queue_timers()

            method = state = self.state
            try:
                if method_name:
                    method = getattr(state, method_name)
                elif handler_getter:
                    method = handler_getter(state)
            except AttributeError:
                pass

            if item is None or method is state:
                self.generator = method()
            else:
                self.generator = method(item)

    class StateController(object):
        def __init__(self, state_machine):
            TERMINATED = State.TERMINATED
            iterstates = state_machine.iterstates
            discard_terminated = state_machine.discard_terminated

            def kill_state(state):
                for state_status in iterstates():
                    if state_status.state == state:
                        state_status.status = TERMINATED
                discard_terminated()

            def kill_all(state_class=State):
                for state_status in iterstates():
                    if isinstance(state_status.state, state_class):
                        state_status.status = TERMINATED
                discard_terminated()
        
            self.state_count = state_machine.state_count
            self.kill_state  = kill_state
            self.kill_all    = kill_all

    import operator
    get_message_handler = operator.attrgetter('handleMessage')
    get_event_handler   = operator.attrgetter('handleEvent')
    get_timer_handler   = operator.attrgetter('handleTimer')
    get_object_handler  = operator.attrgetter('handleObject')

    GET_HANDLER = {
        EDSMTransition.TYPE_MESSAGE    : get_message_handler,
        EDSMTransition.TYPE_VIEW_EVENT : get_event_handler,
        EDSMTransition.TYPE_TIMER      : get_timer_handler
        }

    def start(self):
        states = self.running_states = map(self.StateStatus, self.start_states)
        for state in states:
            state.start()

    def iterstates(self):
        return chain(self.running_states, self.waiting_states)

    def state_count(self):
        return len(self.running_states) + len(self.waiting_states)

    def advance(self, value):
        waiting_states = self.waiting_states
        self.waiting_states = []

        advance_state = self.advance_state
        for state_status in tuple(self.running_states):
            advance_state(state_status.state, value)

        ADVANCE_ALWAYS = State.ADVANCE_ALWAYS

        append = self.waiting_states.append
        for state_status in waiting_states:
            has_advanced = advance_state(state_status.state, value)
            if not has_advanced or state_status.status == ADVANCE_ALWAYS:
                append(state_status)

    def advance_timers(self):
        running_states = [ s for s in self.running_states
                           if s.timers is not None ]
        waiting_states = [ s for s in self.waiting_states
                           if s.timers is not None ]

        if not (running_states or waiting_states):
            return None

        self.waiting_states = [ s for s in self.waiting_states
                                if s.timers is None ]

        new_min_deadline = NEVER
        advance_state = self.advance_state
        for state_status in running_states:
            timers = state_status.timers
            state  = state_status.state
            for timer in timers.get_fired():
                advance_state(state, timer, timer.destinations)
            new_min_deadline = min(new_min_deadline, timers.min_deadline())

        ADVANCE_ALWAYS = State.ADVANCE_ALWAYS

        append = self.waiting_states.append
        for state_status in waiting_states:
            timers = state_status.timers
            state  = state_status.state
            has_advanced = False
            for timer in timers.get_fired():
                has_advanced |= advance_state(state, timer, timer.destinations)
            if not has_advanced or state_status.status == ADVANCE_ALWAYS:
                append(state_status)
                new_min_deadline = min(new_min_deadline, timers.min_deadline())

        if new_min_deadline == NEVER:
            return None
        else:
            return new_min_deadline

    def advance_state(self, state, value, successors=()):
        if not successors:
            try:
                ttype = value.type()
            except (AttributeError, TypeError):
                # FIXME: what are the successors for arbitrary objects?
                return False

            successors_by_type = self.state_table.get(state)
            if not successors_by_type:
                return False

            successors = successors_by_type.get(ttype)
            if not successors:
                return False

        if isinstance(value, Message):
            get_handler = self.get_message_handler
        elif isinstance(value, Event):
            get_handler = self.get_event_handler
        elif isinstance(value, Timer):
            get_handler = self.get_timer_handler
        else:
            get_handler = self.get_object_handler

        process_context = state.PROCESS_CONTEXT

        successor_found = False
        append_state = self.running_states.append
        for successor in successors:
            accepts = getattr(successor, 'accepts', None)
            if accepts and not accepts(value):
                continue

            # FIXME: this assumes a single predecessor state!
            if successor.PROCESS_CONTEXT is None:
                successor.PROCESS_CONTEXT = process_context

            state_status = self.StateStatus(successor)
            state_status.start(handler_getter=get_handler, item=value)
            append_state(state_status)
            successor_found = True
        return successor_found

    def run_state(self, state_status, count=1):
        advance_state = self.advance_state
        action_count = 0

        RUNNING        = State.RUNNING
        YIELD          = State.YIELD
        TERMINATED     = State.TERMINATED
        ADVANCE_ONLY   = State.ADVANCE_ONLY
        ADVANCE_ALWAYS = State.ADVANCE_ALWAYS

        for item in islice(state_status.generator, count):
            action_count += 1
            if item is None or item == RUNNING:
                continue
            elif item == YIELD:
                #state_status.status = RUNNING
                return
            elif item in (ADVANCE_ONLY, TERMINATED, ADVANCE_ALWAYS):
                state_status.status = item
                return
            else:
                advance_state(state_status.state, item)

        if action_count < count:
            state_status.status = TERMINATED

    def run_iterations(self, count=1):
        running_states = self.running_states
        self.running_states = []

        RUNNING        = State.RUNNING
        ADVANCE_ONLY   = State.ADVANCE_ONLY
        ADVANCE_ALWAYS = State.ADVANCE_ALWAYS

        append_running = self.running_states.append
        append_waiting = self.waiting_states.append

        run_state = self.run_state
        for state_status in running_states:
            run_state(state_status, count)

            status = state_status.status
            if status == RUNNING:
                append_running(state_status)
            elif status in (ADVANCE_ONLY, ADVANCE_ALWAYS):
                if state_status.has_timers() or state_status.state in self.state_table:
                    append_waiting(state_status)
            # otherwise: TERMINATED!

    def discard_terminated(self):
        TERMINATED = State.TERMINATED
        self.running_states = [ s for s in self.running_states
                                if s.status != TERMINATED ]
        self.waiting_states = [ s for s in self.waiting_states
                                if s.status != TERMINATED ]
