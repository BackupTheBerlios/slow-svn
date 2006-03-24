try:
    #raise ImportError
    from psyco.classes import *
except:
    pass

import logging


class CachingObserver(object):
    def __init__(self):
        self.__cache = []
        self.__observable = None
        self.__reflective = False

    def observe(self, observable):
        self.__cache = []
        self.__observable = observable
        self.__reflective = isinstance(observable, ReflectiveObservable)
        observable.subscribe(self)

    def stop(self):
        if self.__observable:
            self.__observable.unsubscribe(self)
            self.__observable = None
        for name in dir(self):
            if name.startswith('notify_'):
                delattr(self, name)

    def replay(self, observer):
        if self.__observable:
            self.stop()

        if not self.__reflective:
            for args in self._cache:
                observer(args)
        else:
            observable = ReflectiveObservable()
            observable.subscribe(observer)
            notify = observable._notify
            for name, args in self._cache:
                notify(name, args)

    def __call__(self, *args):
        if self.__observable and not self.__reflective:
            self.__cache.append(args)

    def __getattr__(self, name):
        if not self.__reflective or not name.startswith('notify_'):
            raise AttributeError, name
        cache_append = self.__cache.append
        def _store(*args):
            cache_append( (name, args) )
        setattr(self, name, _store)
        return _store


class Observable(object):
    """Superclass for any class that supports listeners.
    Subclasses inherit the subscribe/unsubscribe methods and only have to call
    self._notify(...) to notify all subscribed listeners.
    If a method _schedule_calls is provided in a subclass, it is called from
    _notify to schedule the provided listener calls. By default, the calls
    are made sequentially.
    """
    __EMPTY_SET = ()

    def __init__(self):
        self.__listeners = self.__EMPTY_SET
        if not hasattr(self, '_schedule_calls'):
            self.set_scheduler(self.__run_calls)

    def set_scheduler(self, scheduler=None):
        if not scheduler:
            scheduler = self.__run_calls
        self._schedule_calls = scheduler

    def __run_calls(self, calls, args):
        for call in calls:
            call(*args)

    def _notify(self, *args):
        if self.__listeners:
            self._schedule_calls(self.__listeners, args)

    def _iter_listeners(self):
        return iter(self.__listeners)

    def subscribe(self, listener):
        if self.__listeners is self.__EMPTY_SET:
            self.__listeners = set( (listener,) )
        else:
            self.__listeners.add(listener)

    def unsubscribe(self, listener):
        self.__listeners.discard(listener)


class ReflectiveObservable(Observable):
    "Select listeners based on explicit method names of the form 'notify_*'."
    def _notify(self, ntype, *args):
        method_name = 'notify_%s' % ntype

        observers = []
        _append = observers.append
        _getattr = getattr
        for listener in self._iter_listeners():
            try: _append(_getattr(listener, method_name))
            except AttributeError: pass

        self._schedule_calls(observers, args)


class TypedObservable(object):
    """Superclass for any class that supports type separated listeners.
    Subclasses inherit the subscribe/unsubscribe methods and only have to call
    self._notify(type, ...) to notify all subscribed listeners.
    """
    def __init__(self, observable_class=Observable):
        self._observable_class = observable_class
        self.__observables = {}

    def _notify(self, event_type, *args):
        try:
            observable = self.__observables[event_type]
        except KeyError:
            return
        observable._notify(event_type, *args)

    def subscribe(self, event_type, listener):
        try:
            observable = self.__observables[event_type]
        except KeyError:
            observable = self._observable_class()
            self.__observables[event_type] = observable
        observable.subscribe(listener)

    def unsubscribe(self, event_type, listener):
        try:
            self.__observables[event_type].unsubscribe(listener)
        except KeyError:
            pass
