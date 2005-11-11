from itertools import imap
from collections import deque

class DefaultDict(dict):
    def __init__(self, default_container=list, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__default_container = default_container

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            container = self.__default_container()
            dict.__setitem__(self, key, container)
            return container


class TimerQueue(object):
    INFINITY = float('inf')
    from time import time as current_time
    def __init__(self):
        self._timers = DefaultDict(deque)
        self._min_deadline = self.INFINITY

    def start_new(self, timer_type):
        timer = timer_type.new_timer()
        self._min_deadline = min(self._min_deadline, timer.deadline)

        self._timers[timer.delay].append(timer) # deque()

    def __len__(self):
        return sum(imap(len, self._timers.itervalues()))

    def cancel_all(self):
        self._timers.clear()

    def min_deadline(self):
        return self._min_deadline

    def get_fired(self):
        current_time = self.current_time()
        fired = []

        min_deadline = self._min_deadline
        if min_deadline > current_time and min_deadline != self.INFINITY:
            return fired

        append = fired.append
        min_deadline = self.INFINITY
        for queue in self._timers.itervalues():
            poptimer = queue.popleft
            while queue:
                timer = queue[0]
                if not timer.running:
                    poptimer()
                elif current_time >= timer.deadline:
                    append( poptimer().timer )
                else:
                    min_deadline = min(min_deadline, timer.deadline)
                    break
        self._min_deadline = min_deadline
        return fired
