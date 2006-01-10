from tests import run_testsuites

from pyedsm.edsm import *
from pyedsm.states import TimerHandlerState

import unittest, time


class Counter(object):
    def __init__(self):
        self.counter = 0
    def reset(self):
        self.counter = 0
    def __eq__(self, value):
        return self.counter == value
    def __repr__(self):
        return str(self.counter)
    def inc(self, value=1):
        self.counter += value


class EDSMTestCase(unittest.TestCase):
    def setUp(self):
        self.counter = Counter()

    def build_generator(self, retval):
        def incrCounter():
            while True:
                self.counter.inc()
                yield retval
        return incrCounter

    class incrCounterRunRepeat(object):
        def __init__(self, count, counter):
            self.count = count
            self.counter = counter
        def __call__(self):
            for i in range(self.count):
                self.counter.inc()
                yield State.RUNNING

    def testAdvanceOnly(self):
        incr_counter = self.build_generator(State.ADVANCE_ONLY)
        state_table = {
            incr_counter : {EDSMTransition.TYPE_MESSAGE : [incr_counter, incr_counter]}
            }
        self.counter.reset()
        sm = StateMachine(state_table, [incr_counter, incr_counter])
        self.assertEqual(self.counter, 0)
        sm.start()
        self.assertEqual(self.counter, 0)

        sm.run_iterations()
        self.assertEqual(self.counter, 2)
        sm.run_iterations()
        self.assertEqual(self.counter, 2)

        self.counter.reset()
        self.assertEqual(self.counter, 0)
        self.assertEqual(sm.state_count(), 2)
        sm.run_iterations()
        self.assertEqual(self.counter, 0)

        self.counter.reset()
        self.assertEqual(sm.state_count(), 2)
        sm.advance(Message('test', None, None, None))
        self.assertEqual(sm.state_count(), 4)
        self.assertEqual(self.counter, 0)
        sm.run_iterations()
        self.assertEqual(self.counter, 4)
        sm.run_iterations()
        self.assertEqual(self.counter, 4)

        self.counter.reset()
        self.assertEqual(self.counter, 0)
        sm.run_iterations()
        self.assertEqual(self.counter, 0)

    def testYield(self):
        incr_counter = self.build_generator(State.YIELD)
        state_table = {
            incr_counter : {EDSMTransition.TYPE_MESSAGE : [incr_counter, incr_counter]}
            }
        self.counter.reset()
        sm = StateMachine(state_table, [incr_counter, incr_counter])
        self.assertEqual(self.counter, 0)
        sm.start()
        self.assertEqual(self.counter, 0)

        sm.run_iterations(5)
        self.assertEqual(self.counter, 2)
        sm.run_iterations(2)
        self.assertEqual(self.counter, 2+2)

        self.counter.reset()
        self.assertEqual(self.counter, 0)
        self.assertEqual(sm.state_count(), 2)
        sm.run_iterations(5)
        self.assertEqual(self.counter, 2)

        self.counter.reset()
        sm.advance(Message('test', None, None, None))
        self.assertEqual(sm.state_count(), 6)
        self.assertEqual(self.counter, 0)
        sm.run_iterations(2)
        self.assertEqual(self.counter, 6)
        sm.run_iterations(5)
        self.assertEqual(self.counter, 6+6)

        self.counter.reset()
        self.assertEqual(self.counter, 0)
        sm.run_iterations(2)
        self.assertEqual(self.counter, 6)

    def testRunning(self):
        incr_counter4 = self.incrCounterRunRepeat(4, self.counter)
        incr_counter6 = self.incrCounterRunRepeat(6, self.counter)
        state_table = {
            incr_counter4 : {EDSMTransition.TYPE_MESSAGE : [incr_counter6, incr_counter6]}
            }
        self.counter.reset()
        sm = StateMachine(state_table, [incr_counter4, incr_counter4])
        self.assertEqual(self.counter, 0)
        sm.start()
        self.assertEqual(self.counter, 0)

        sm.run_iterations(1)
        self.assertEqual(self.counter, 2)
        sm.run_iterations(1)
        self.assertEqual(self.counter, 2+2)

        self.counter.reset()
        self.assertEqual(self.counter, 0)
        self.assertEqual(sm.state_count(), 2)
        sm.run_iterations(2)
        self.assertEqual(self.counter, 2*2)

        self.counter.reset()
        sm.advance(Message('test', None, None, None))
        self.assertEqual(sm.state_count(), 6)
        self.assertEqual(self.counter, 0)
        sm.run_iterations(2)
        self.assertEqual(sm.state_count(), 4)
        self.assertEqual(self.counter, 2*4)
        sm.run_iterations(2)
        self.assertEqual(self.counter, 2*4+2*4)

        self.counter.reset()
        self.assertEqual(sm.state_count(), 4)
        self.assertEqual(self.counter, 0)
        sm.run_iterations(2)
        self.assertEqual(sm.state_count(), 4)
        self.assertEqual(self.counter, 2*4)
        sm.run_iterations(1)
        self.assertEqual(sm.state_count(), 0)
        self.assertEqual(self.counter, 2*4)

    def testTermination(self):
        incr_counter1 = self.build_generator(State.ADVANCE_ONLY)
        incr_counter2 = self.build_generator(State.ADVANCE_ONLY)
        state_table = {
            incr_counter1 : {EDSMTransition.TYPE_MESSAGE : [incr_counter2]}
            }
        self.counter.reset()
        sm = StateMachine(state_table, [incr_counter1, incr_counter2])

        self.assertEqual(self.counter, 0)
        sm.start()
        self.assertEqual(sm.state_count(), 2)
        self.assertEqual(self.counter, 0)
        sm.run_iterations(1)
        self.assertEqual(sm.state_count(), 1)
        self.assertEqual(self.counter, 2)
        sm.run_iterations(1)
        self.assertEqual(sm.state_count(), 1)
        self.assertEqual(self.counter, 2)

        self.counter.reset()
        self.assertEqual(sm.state_count(), 1)
        self.assertEqual(self.counter, 0)
        sm.advance(Message('test', None, None, None))
        self.assertEqual(sm.state_count(), 1)
        self.assertEqual(self.counter, 0)
        sm.run_iterations(1)
        self.assertEqual(sm.state_count(), 0)
        self.assertEqual(self.counter, 1)


class EDSMTimerTestCase(unittest.TestCase):
    def setUp(self):
        self.counter = Counter()

    class incrCounterTimer(TimerHandlerState):
        def __init__(self, count, counter):
            TimerHandlerState.__init__(self, 'test')
            self.count = count
            self.counter = counter
        def __call__(self):
            yield State.ADVANCE_ONLY
        def handleTimer(self, timer):
            for i in range(self.count):
                self.counter.inc()
                yield State.RUNNING
            yield State.ADVANCE_ONLY

    def testTimer(self):
        class TimerModel(object):
            timer_delay = 0.1

        incr_counter = self.incrCounterTimer(1, self.counter)

        timer = Timer('timer', incr_counter, incr_counter, TimerModel())
        incr_counter.attach_timer(timer)

        state_table = {}
        self.counter.reset()
        sm = StateMachine(state_table, [incr_counter, incr_counter])
        self.assertEqual(self.counter, 0)
        sm.start()
        self.assertEqual(sm.state_count(), 2)
        self.assertEqual(self.counter, 0)

        sm.run_iterations()
        self.assertEqual(sm.state_count(), 2)
        self.assertEqual(self.counter, 0)
        sm.advance_timers()
        self.assertEqual(sm.state_count(), 2)
        self.assertEqual(self.counter, 0)
        sm.run_iterations()
        self.assertEqual(sm.state_count(), 2)
        self.assertEqual(self.counter, 0)

        time.sleep(0.2)

        incr_counter.attach_timer(timer)

        self.counter.reset()
        sm.advance_timers()
        self.assertEqual(sm.state_count(), 2)
        self.assertEqual(self.counter, 0)
        sm.run_iterations()
        self.assertEqual(self.counter, 2)
        sm.run_iterations()
        self.assertEqual(self.counter, 2)

        time.sleep(0.2)

        self.counter.reset()
        sm.advance_timers()
        self.assertEqual(sm.state_count(), 4)
        self.assertEqual(self.counter, 0)
        sm.run_iterations()
        self.assertEqual(self.counter, 4)


class EDSMBuilderTestCase(unittest.TestCase):
    def setUp(self):
        import random
        from model.edsm_model import EDSMState, EDSMTransition

        states = self.states = [
            EDSMState('s%02d' % i, 'test %02d' % i,
                      'class MyState(MessageHandlerState): pass', 'MyState')
            for i in range(10) ]

        states.append(
            EDSMState('start', 'start',
                      'class StartState(MessageHandlerState): pass', 'StartState')
            )

        self.message_transitions = [
            EDSMTransition('m%02d' % i,
                           random.choice(states),
                           random.choice(states),
                           EDSMTransition.TYPE_MESSAGE)
            for i in range(10) ]

        transitions = self.direct_transitions = []
        for i in range(5):
            start_state = random.choice(states)
            end_state = start_state
            while end_state == start_state:
                end_state = random.choice(states)

            transitions.append(
                EDSMTransition('d%02d' % i, start_state, end_state,
                               EDSMTransition.TYPE_TRANSITION)
                )

    def testAll(self):
        all_transitions = self.message_transitions + self.direct_transitions
        builder = StateMachineConstructor()
        edsm = builder.from_model(self.states, all_transitions)
        edsm.start()
        #print edsm.state_count()
        edsm.advance(Message('test', None, None, None))
        #print edsm.state_count()


if __name__ == "__main__":
    run_testsuites( globals().values() )
