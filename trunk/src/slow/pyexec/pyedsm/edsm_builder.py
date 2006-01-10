from itertools import *

from lxml.etree import parse

from edsm import StateMachine, Timer
from helpers import DefaultDict
from slow.model.edsm_model import EDSMTransition, EDSM_NAMESPACE_URI
#from serialization.edsm_serializer import EDSMDefinitionParser


############################################################
# Global context object
############################################################

class Context(dict):
    def __new__(cls, name, parent_name=''):
        return dict.__new__(cls)

    def __init__(self, name, parent_name=''):
        super(Context, self).__init__()
        if parent_name:
            name = '%s.%s' % (parent_name, name)
        self.__name = name
        self.__SUBCONTEXTS = {}

    def SUBCONTEXT(self, name):
        names = name.split('.', 1)
        child_name = names[0]
        try:
            context = self.__SUBCONTEXTS[child_name]
        except KeyError:
            context = self.__SUBCONTEXTS[child_name] = Context(child_name, self.__name)
        if len(names) == 1:
            return context
        else:
            return context.SUBCONTEXT(names[1])

    @property
    def LOGGER(self):
        import logging
        logger = logging.getLogger(self.__name)
        if logger:
            self.LOGGER = logger
        return logger

############################################################
# Construct EDSM from model
############################################################

class StateMachineConstructor(object):
    STATE_MACHINE_CLASS = StateMachine

    __BUILTINS = globals()['__builtins__']
    __GLOBAL_DICT = { '__builtins__' : __BUILTINS }
    exec 'from states import *' in __GLOBAL_DICT

    def __init__(self, env=None, edsm_class=STATE_MACHINE_CLASS,
                 global_env=__GLOBAL_DICT):
        self.edsm_class = edsm_class

        global_env = global_env.copy()
        if env:
            global_env.update(env)
        if '__builtins__' not in global_env:
            global_env['__builtins__'] = self.__BUILTINS
        self._env = global_env

    def from_file(self, file_or_filename):
        root = parse(file_or_filename)
        edsm_tags = root.xpath(u'//edsm:edsm', {u'edsm':EDSM_NAMESPACE_URI})
        if not edsm_tags:
            return None
        elif len(edsm_tags) == 1:
            return self.from_model(edsm_tags[0])
        else:
            return map(self.from_model, edsm_tags)

    def from_model(self, edsm_model):
        """Constructs a new EDSM from the EDSM graph model.
        """
        triggered = []
        by_type = dict( izip(EDSMTransition.VALID_TYPES, repeat(triggered)) )
        for t in (EDSMTransition.TYPE_TIMER, EDSMTransition.TYPE_TRANSITION):
            by_type[t] = []

        for transition in edsm_model.transitions:
            by_type[transition.type].append(transition)

        direct = by_type[EDSMTransition.TYPE_TRANSITION]
        if direct:
            equiv_states = self._resolve_direct_transitions(direct)
        else:
            equiv_states = {}

        # for messages and view events:
        triggered = by_type[EDSMTransition.TYPE_MESSAGE]
        state_table = self._init_states(equiv_states, triggered)

        start_states = self._find_start_states(edsm_model.states, equiv_states)

        # translate to executable objects:
        state_objects, global_context = self._build_state_objects(edsm_model.states)
        state_object_table, start_state_objects = self._translate_to_state_objects(
            state_objects, state_table, start_states )

        timers = by_type[EDSMTransition.TYPE_TIMER]
        self._init_timers(timers, state_objects, equiv_states)

        # build and return state machine
        return self.edsm_class(state_object_table, start_state_objects,
                               global_context)

    def _build_state_objects(self, states):
        state_objects = {}

        global_env = self._env.copy()
        global_context = global_env['GLOBAL_CONTEXT'] = Context('edsm')

        copy_env = global_env.copy
        for state in states:
            state_name = state.name
            init_code  = state.code.compiled_code
            class_name = state.code.class_name

            class_env = copy_env()
            state_context = class_env['STATE_CONTEXT'] = Context(state_name, 'edsm')

            if init_code:
                exec init_code in class_env
            if not class_name:
                class_name = 'State'
            state_class = eval(class_name, class_env)

            state_class.GLOBAL_CONTEXT = global_context
            state_class.STATE_CONTEXT  = state_context

            if state.inherit_context:
                state_class.PROCESS_CONTEXT = None
            else:
                state_class.PROCESS_CONTEXT = state_context

            state_objects[state_name] = state_class(state_name)
        return (state_objects, global_context)

    @staticmethod
    def _translate_to_state_objects(state_objects, state_table, start_states):
        state_object_table = {}
        for state_model, transitions in state_table.iteritems():
            state_object = state_objects[state_model.name]
            target_state_objects = state_object_table[state_object] = {}
            for transition_type, target_states in transitions.iteritems():
                target_state_objects[transition_type] = set(
                    state_objects[s.name] for s in target_states )

        start_state_objects = [ state_objects[s.name] for s in start_states ]

        return (state_object_table, start_state_objects)

    @staticmethod
    def _find_start_states(states, equiv_states):
        start_states = set()
        for state in states:
            if state.name == 'start':
                start_states.add(state)
                for equiv in equiv_states.get(state, ()):
                    start_states.add(equiv)

        return start_states

    @staticmethod
    def _resolve_direct_transitions(direct_transitions):
        equiv_states = DefaultDict(set)
        for transition in direct_transitions:
            source = transition.from_state
            dest   = transition.to_state

            equiv_states[source].add(dest) # set()

        if not equiv_states:
            return equiv_states

        # this is not fast, but it should work
        _len = len
        added = True
        while added:
            added = False
            for state, equivs in equiv_states.iteritems():
                old_len = _len(equivs)
                for equiv in tuple(equivs):
                    equivs.update( equiv_states.get(equiv, ()) )
                added |= _len(equivs) > old_len

        return equiv_states

    @staticmethod
    def _init_states(equiv_states, transitions):
        # build dict of target state sets
        state_table = DefaultDict( lambda : DefaultDict(set) )
        for transition in transitions:
            source = transition.from_state
            dest   = transition.to_state
            ttype  = transition.type

            state_transitions = state_table[source] # dict()
            dests = state_transitions[ttype] # set()
            dests.add(dest)

        if not equiv_states:
            return state_table

        # merge with equivalent states
        for state, state_transitions in state_table.iteritems():
            for equiv_state in equiv_states[state]:
                if equiv_state not in state_table:
                    continue
                for ttype, dests in state_table[equiv_state].iteritems():
                    try:
                        state_transitions[ttype].update(dests)
                    except KeyError:
                        state_transitions[ttype] = dests

        return state_table

    @staticmethod
    def _init_timers(timers, state_objects, equiv_states):
        for timer_description in timers:
            source = state_objects[ timer_description.from_state.name ]

            to_state = timer_description.to_state
            to_states = set()
            to_states.add(to_state)
            to_states.update( equiv_states.get(to_state, ()) )

            destinations = [ state_objects[dest.name] for dest in to_states ]

            timer = Timer(timer_description.name,
                          destinations, timer_description.timer_delay)
            source.attach_timer(timer)
