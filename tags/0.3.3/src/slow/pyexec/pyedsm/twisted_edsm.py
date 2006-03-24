from twisted.internet import reactor
import edsm

class TwistedStateMachine(edsm.StateMachine):
    from time import time as current_time
    def start(self):
        self._callLater = reactor.callLater
        self.timer_deadline = None
        self.running = False

        super(TwistedStateMachine, self).start()
        self.scheduled_advance()

    def schedule_run(self):
        if self.running_states and not self.running:
            self.running = True
            self._callLater(0, self.run)

    def run(self):
        if self.running_states:
            self.run_iterations(3)

        self.running = False
        self.schedule_run()

        if self.timer_deadline is None:
            self.scheduled_advance()

    def scheduled_advance(self):
        self.timer_deadline = advance_deadline = self.advance_timers()
        if advance_deadline is not None:
            advance_delay = advance_deadline - self.current_time()
            self._callLater(advance_delay, self.scheduled_advance)
        self.schedule_run()

    def message_received(self, message):
        self.advance(message)
        self.schedule_run()

    def event_received(self, event):
        self.advance(event)
        self.schedule_run()


if __name__ == '__main__':
    import sys, edsm_builder

    if len(sys.argv) < 2:
        print "Need filename to run."
        sys.exit(0)

    builder = edsm_builder.StateMachineConstructor(
        edsm_class=TwistedStateMachine )
    tw_edsm = builder.from_file(sys.argv[1])

    # set I/O handlers, etc.
    #tw_edsm.

    reactor.callLater(0, tw_edsm.start)
    reactor.run()
