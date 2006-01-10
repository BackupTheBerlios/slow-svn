__doc__ = """
Run-time state base classes for the EDSM implementation
"""

class State(object):
    __slots__ = ('name', '_timers', 'CONTEXT', 'PROCESS_CONTEXT')
    from helpers import TimerQueue as _timer_queue_class

    @classmethod
    def set_timer_class(cls, timer_class):
        cls._timer_queue_class = timer_class

    class StateAction(object):
        __slots__ = '_type'
        __ACTIONS = {}
        def __new__(cls, atype):
            if atype < 0 or atype > 4:
                raise ValueError, "invalid action number"
            try:
                return cls.__ACTIONS[atype]
            except KeyError:
                instance = cls.__ACTIONS[atype] = object.__new__(cls)
                instance._type = atype
                return instance

        @property
        def type(self):
            return self._type

        def __eq__(self, other):
            try:
                return self._type == other._type
            except AttributeError:
                return False

        def __repr__(self):
            return str(self._type)

    class StateContext(object):
        __slots__ = '_state'
        def __init__(self, state):
            object.__setattr__(self, '_state', state)

        def __getattr__(self, name):
            state = self._state
            try: return state.STATE_CONTEXT[name]
            except (KeyError, AttributeError, TypeError):
                pass
            try: return state.PROCESS_CONTEXT[name]
            except (KeyError, AttributeError, TypeError):
                pass
            try: return state.GLOBAL_CONTEXT[name]
            except (KeyError, AttributeError, TypeError):
                pass
            raise AttributeError, name

        def __setattr__(self, name, value):
            state = self._state
            try:
                if state.PROCESS_CONTEXT is not None:
                    state.PROCESS_CONTEXT[name] = value
                    return
            except AttributeError:
                pass
            state.STATE_CONTEXT[name] = value


    # state is running => reschedule in next loop
    RUNNING        = StateAction(0)

    # state has terminated => remove
    TERMINATED     = StateAction(1)

    # state has terminated => remove on advance
    ADVANCE_ONLY   = StateAction(2)

    # state has terminated => keep on advance
    ADVANCE_ALWAYS = StateAction(3)

    # state is running => reschedule immediately
    YIELD          = StateAction(4)


    def __init__(self, name):
        self.name = name
        self.CONTEXT = self.StateContext(self)
        self._timers = []
    def __getattr__(self, name):
        return getattr(self.CONTEXT, name)

    def __call__(self):
        "generator"
        yield self.ADVANCE_ONLY
    def accepts(self, value):
        return True

    def has_timers(self):
        return bool(self._timers)
    def attach_timer(self, timer_type):
        self._timers.append(timer_type)
    def queue_timers(self):
        queue = self._timer_queue_class()
        for timer in self._timers:
            queue.start_new(timer)
        return queue


class PermanentState(State):
    __slots__ = ('PROCESS_CONTEXT',)
    def __call__(self):
        "generator"
        yield self.ADVANCE_ALWAYS

class VirtualState(State):
    __slots__ = ('PROCESS_CONTEXT',)
    def __call__(self):
        "generator"
        yield self.ADVANCE_ONLY

class MessageHandlerState(State):
    __slots__ = ('PROCESS_CONTEXT',)
    def handleMessage(self, message):
        "generator"
        yield self.ADVANCE_ONLY

##     def accepts(self, message):
##         return isinstance(message, Message)

class EventHandlerState(State):
    __slots__ = ('PROCESS_CONTEXT',)
    def handleEvent(self, event):
        "generator"
        yield self.ADVANCE_ONLY

##     def accepts(self, event):
##         return isinstance(event, Event)

class TimerHandlerState(State):
    __slots__ = ('PROCESS_CONTEXT',)
    def handleTimer(self, timer):
        "generator"
        yield self.ADVANCE_ONLY

##     def accepts(self, event):
##         return isinstance(event, Timer)

class ObjectHandlerState(State):
    __slots__ = ('PROCESS_CONTEXT',)
    def handleObject(self, obj):
        "generator"
        yield self.ADVANCE_ONLY

##     def accepts(self, obj):
##         return True
