from lxml import etree
from lxml.etree import Element, SubElement, XML
from copy import deepcopy
from StringIO import StringIO
from itertools import imap

from xpathmodel import XPathModel, autoconstruct, get_first, disconnect_element
from code_model import CodeContainer
from model import NamedObject

import random

EDSM_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/edsl"

def uniqueID(node, state_id):
    node_by_id = node.getObjectById
    randint = random.randint
    while node_by_id(state_id) is not None:
        state_id = str(randint(100000000, 999999999))
    return state_id

def buildTransition(parent, transition_type):
    if isinstance(parent, EDSMRootModel):
        parent = parent.transitions
    return SubElement(parent,
                      u"{%s}transition" % EDSM_NAMESPACE_URI,
                      type=transition_type)

def buildState(parent, name, readable_name=None,
               inputs=('input',), outputs=('output',)):
    if isinstance(parent, EDSMRootModel):
        parent = parent.states
    state = SubElement(parent,
                       u"{%s}state" % EDSM_NAMESPACE_URI,
                       name=name)
    if readable_name:
        state.readable_name = readable_name
    state.id = uniqueID(parent, str(id(state)))
    if inputs:
        for queue in inputs:
            state.add_input(queue)
    if outputs:
        for queue in outputs:
            state.add_output(queue)
    return state

def buildSubgraph(parent, name, readable_name=None):
    if isinstance(parent, EDSMRootModel):
        parent = parent.states
    subgraph = SubElement(parent,
                          u"{%s}subgraph" % EDSM_NAMESPACE_URI,
                          name=name)
    if readable_name:
        subgraph.readable_name = readable_name
    subgraph.id = uniqueID(parent, str(id(subgraph)))
    states = subgraph.states
    subgraph.entry_state = buildState(states, 'entry')
    subgraph.exit_state  = buildState(states, 'exit')
    return subgraph

EMPTY_MODEL = u'''\
<edsm xmlns="%s">
  <states>
    <state name="start" id="start">
      <readablename>start</readablename>
    </state>
  </states>
  <transitions/>
</edsm>
''' % EDSM_NAMESPACE_URI

def buildEmptyModel():
    return XML(EMPTY_MODEL)

class EDSMClass(XPathModel):
    DEFAULT_NAMESPACE = EDSM_NAMESPACE_URI
    @property
    def type_name(self):
        return self.tag.split('}', 1)[-1]
    @get_first
    def _get_states(self):
        u"ancestor-or-self::{%(DEFAULT_NAMESPACE)s}edsm/{%(DEFAULT_NAMESPACE)s}states"
    @get_first
    def _get_transitions(self):
        u"ancestor-or-self::{%(DEFAULT_NAMESPACE)s}edsm/{%(DEFAULT_NAMESPACE)s}transitions"
    @get_first
    def _get_objectById(self, id):
        u"ancestor-or-self::{%(DEFAULT_NAMESPACE)s}edsm/{%(DEFAULT_NAMESPACE)s}states//{%(DEFAULT_NAMESPACE)s}*[ @id = $id ]"
    def _get_stateTransitions(self, ref_id):
        u"ancestor-or-self::{%(DEFAULT_NAMESPACE)s}edsm//{%(DEFAULT_NAMESPACE)s}transition[ {%(DEFAULT_NAMESPACE)s}*/@ref = $ref_id ]"

class EDSMCodeContainer(CodeContainer):
    DEFAULT_NAMESPACE = EDSM_NAMESPACE_URI


class EDSMRootModel(EDSMClass):
    @get_first
    @autoconstruct
    def _get_states(self):
        u"./{%(DEFAULT_NAMESPACE)s}states"
    @get_first
    @autoconstruct
    def _get_transitions(self):
        u"./{%(DEFAULT_NAMESPACE)s}transitions"

    def _get_used_names(self, _xpath_result):
        u".//{%(DEFAULT_NAMESPACE)s}*/@name"
        return frozenset(imap(unicode, _xpath_result))

    def _get_used_ids(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}states//{%(DEFAULT_NAMESPACE)s}*/@id"
        return frozenset(imap(unicode, _xpath_result))

    _get_statelist      = u"./{%(DEFAULT_NAMESPACE)s}states/{%(DEFAULT_NAMESPACE)s}state"
    _get_subgraphlist   = u"./{%(DEFAULT_NAMESPACE)s}states/{%(DEFAULT_NAMESPACE)s}subgraph"
    _get_transitionlist = u"./{%(DEFAULT_NAMESPACE)s}transitions/{%(DEFAULT_NAMESPACE)s}transition"

    def add_state(self, state):
        state.discard()
        self.states.append(state)
    @get_first
    def _get_stateByName(self, name):
        u"./{%(DEFAULT_NAMESPACE)s}states/{%(DEFAULT_NAMESPACE)s}state[ @name = $name ]"
    @get_first
    def _get_state(self, id):
        u"./{%(DEFAULT_NAMESPACE)s}states/{%(DEFAULT_NAMESPACE)s}state[ @id = $id ]"
##     def _get_state(self, _xpath_result, id):
##         u"./{%(DEFAULT_NAMESPACE)s}states/{%(DEFAULT_NAMESPACE)s}state[ @id = $id ]"
##         if _xpath_result:
##             return _xpath_result[0]
##         else:
##             return SubElement(self.states, u"{%s}state" % EDSM_NAMESPACE_URI, id=id)

    @get_first
    def _get_subgraph(self, id):
        u"./{%(DEFAULT_NAMESPACE)s}states//{%(DEFAULT_NAMESPACE)s}subgraph[ @id = $id ]"


class EDSMSubgraphModel(EDSMRootModel, NamedObject):
    _attr_id = u"./@id"
    def discard(self):
        for state in self.states[:]:
            state.discard()
        disconnect_element(self)
    def __setIOState(self, io_type, state):
        state_id = state.id
        child_state = self.getState(state_id)
        if child_state is None:
            self.addState(state)
        self.set(io_type, state_id)
    def _get_entry_state(self):
        return self.getState(self.get('entry_state'))
    def _set_entry_state(self, state):
        self.__setIOState('entry_state', state)
    def _get_exit_state(self):
        return self.getState(self.get('exit_state'))
    def _set_exit_state(self, state):
        self.__setIOState('exit_state', state)


class EDSMState(object):
    pass

class EDSMStateModel(EDSMClass, EDSMState, NamedObject):
    _attr_id = u"./@id"
    def discard(self):
        for transition in self.getStateTransitions(self.id):
            transition.discard()
        disconnect_element(self)

    def _get_code(self, _xpath_result, language):
        u"./{%(DEFAULT_NAMESPACE)s}code[@language = $language]"
        if _xpath_result:
            return _xpath_result[0]
        else:
            return SubElement(self, "{%s}code" % EDSM_NAMESPACE_URI, language=language)

    def _set_code(self, _xpath_result, language, code, *class_name):
        u"./{%(DEFAULT_NAMESPACE)s}code[@language = $language]"
        if _xpath_result:
            code_tag = _xpath_result[0]
        else:
            code_tag = SubElement(self, "{%s}code" % EDSM_NAMESPACE_URI, language=language)
        code_tag.code = code
        if class_name and class_name[0]:
            code_tag.class_name = class_name[0]

    def _del_code(self, language):
        u"./{%(DEFAULT_NAMESPACE)s}code[@language = $language]"

    _get_codes = u"./{%s}code" % EDSM_NAMESPACE_URI
    _del_codes = u"./{%s}code" % EDSM_NAMESPACE_URI

    _attr_inherit_context = u"bool#./@inherit_context"
    _attr_long_running    = u"bool#./@long_running"

    def _get_input_queues(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}input/text()"
        return set(imap(str, _xpath_result))
    def _get_output_queues(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}output/text()"
        return set(imap(str, _xpath_result))

    def _set_input_queues(self, _xpath_result, queues):
        u"./{%(DEFAULT_NAMESPACE)s}input"
        for queue in _xpath_result:
            queue.discard()
        for queue in queues:
            self.add_input(queue)
    def _set_output_queues(self, _xpath_result, queues):
        u"./{%(DEFAULT_NAMESPACE)s}output"
        for queue in _xpath_result:
            queue.discard()
        for queue in queues:
            self.add_output(queue)

    def add_input(self, name):
        if name not in self.input_queues:
            SubElement(self, "{%s}input" % EDSM_NAMESPACE_URI).text = name
    def add_output(self, name):
        if name not in self.output_queues:
            SubElement(self, "{%s}output" % EDSM_NAMESPACE_URI).text = name

    def del_input(self, name):
        self._discard_child_with_text("{%s}input" % EDSM_NAMESPACE_URI, name)
    def del_input(self, name):
        self._discard_child_with_text("{%s}output" % EDSM_NAMESPACE_URI, name)

    def _discard_child_with_text(self, tag, text):
        for child in self:
            if child.tag == tag and child.text == name:
                child.discard()

class EDSMQueueEntry(EDSMClass):
    discard = disconnect_element


class EDSMTransition(object):
    TYPE_TRANSITION   = 0
    TYPE_MESSAGE      = 1
    TYPE_VIEW_EVENT   = 2
    TYPE_OUTPUT_CHAIN = 3
    TYPE_TIMER        = 4

    TYPENAMES = {
        TYPE_TRANSITION   : 'transition',
        TYPE_MESSAGE      : 'message',
        TYPE_VIEW_EVENT   : 'event',
        TYPE_OUTPUT_CHAIN : 'outputchain',
        TYPE_TIMER        : 'timer'
        }

    VALID_TYPES = frozenset(TYPENAMES.iterkeys())
    TYPES_BY_NAME = dict( (v,n) for (n,v) in TYPENAMES.iteritems() )

    _INVALID_STATE = "invalid state"
    _INVALID_TYPE  = "invalid type"

class EDSMTransitionModel(EDSMClass, EDSMTransition, NamedObject):
    @property
    def type_name(self):
        return self.get(u"type")

    def _get_type(self, _xpath_result):
        u"string(./@type)"
        return self.TYPES_BY_NAME.get(_xpath_result, None)
    def _set_type(self, value):
        try:
            self.set(u"type", self.TYPENAMES[value])
        except KeyError:
            raise ValueError, self._INVALID_TYPE

    def _get_from_state(self, _xpath_result):
        u"string(./{%(DEFAULT_NAMESPACE)s}from_state/@ref)"
        return self.getObjectById(_xpath_result)
    @autoconstruct
    def _set_from_state(self, _xpath_result, state):
        u"./{%(DEFAULT_NAMESPACE)s}from_state"
        if state.type_name == 'subgraph':
            state = state.exit_state
        state_id = state.id
        assert self.getObjectById(state_id)
        _xpath_result[0].set(u"ref", state_id)

    def _get_to_state(self, _xpath_result):
        u"string(./{%(DEFAULT_NAMESPACE)s}to_state/@ref)"
        return self.getObjectById(_xpath_result)
    @autoconstruct
    def _set_to_state(self, _xpath_result, state):
        u"./{%(DEFAULT_NAMESPACE)s}to_state"
        if state.type_name == 'subgraph':
            state = state.entry_state
        state_id = state.id
        assert self.getObjectById(state_id)
        _xpath_result[0].set(u"ref", state_id)

    @get_first
    def _get_from_queue(self):
        u"./{%(DEFAULT_NAMESPACE)s}from_state/@queue"
    def _set_from_queue(self, _xpath_result, name):
        u"./{%(DEFAULT_NAMESPACE)s}from_state"
        _xpath_result[0].set(u"queue", name)

    @get_first
    def _get_to_queue(self):
        u"./{%(DEFAULT_NAMESPACE)s}to_state/@queue"
    def _set_to_queue(self, _xpath_result, name):
        u"./{%(DEFAULT_NAMESPACE)s}to_state"
        _xpath_result[0].set(u"queue", name)

    def _get_timer_delay(self, _xpath_result):
        u"string(./{%(DEFAULT_NAMESPACE)s}timerdelay)"
        try:
            return int(_xpath_result)
        except (ValueError, IndexError):
            return 0
    @autoconstruct
    def _set_timer_delay(self, _xpath_result, value):
        u"./{%(DEFAULT_NAMESPACE)s}timerdelay"
        _xpath_result[0].text = str(value)

    @autoconstruct
    def _get_code(self):
        u"./{%(DEFAULT_NAMESPACE)s}code"

    _get_message_type = u"string(./{%(DEFAULT_NAMESPACE)s}messagetype)"
    @autoconstruct
    def _set_message_type(self, _xpath_result, value):
        u"./{%(DEFAULT_NAMESPACE)s}messagetype"
        _xpath_result[0].text = value

    discard = disconnect_element


ns = etree.Namespace(EDSM_NAMESPACE_URI)
ns[None]          = EDSMClass
ns[u'code']       = EDSMCodeContainer
ns[u'edsm']       = EDSMRootModel
ns[u'subgraph']   = EDSMSubgraphModel
ns[u'state']      = EDSMStateModel
ns[u'input']      = EDSMQueueEntry
ns[u'output']     = EDSMQueueEntry
ns[u'transition'] = EDSMTransitionModel
