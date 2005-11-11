try:
    from psyco.classes import *
except:
    pass

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO  import StringIO

import copy
from collections import deque

from observable import TypedObservable

class StupidNodeIO(TypedObservable):
    def __init__(self, global_io):
        TypedObservable.__init__(self)
        self.id = id(self)
        self.global_io = global_io

    def __hash__(self):
        return self.id

    def send(self, msg_type, to_node, message):
        self.global_io.send(msg_type, self, to_node, message)

    def receive(self, msg_type, from_node, message):
        self._notify(msg_type, from_node, message)


class StupidIO(object):
    def __init__(self):
        self.node_ios = {}
        self.messages = deque()
        self.message_data = StringIO()
        self.serializer   = XMLMessageSerializer(self.message_data)
        self.deserializer = XMLMessageDeserializer()

    def create_node(self):
        node_io = StupidNodeIO(self)
        self.node_ios[node_io.id] = node_io
        return node_io

    def send(self, msg_type, from_node, to_node, message):
        if not hasattr(to_node, 'receive'):
            to_node = self.node_ios[to_node]

        self.message_data.seek(0)
        self.message_data.truncate()
        self.serializer.serialize( message )
        message_data = self.message_data.getvalue()
        self.message_data.seek(0)
        self.message_data.truncate()

        self.messages.append( (from_node, to_node, msg_type, message_data) )
        self.deliver_next_message()

    def deliver_next_message(self):
        if self.messages:
            (from_node, to_node, msg_type, message_data) = self.messages.popleft()
            to_node.receive(msg_type, from_node, message)
        return len(self.messages)


class StupidScheduler(object):
    def __init__(self, node_action, s_io):
        self.node_action, self.s_io = node_action, s_io

    def run(self, nodes):
        messages = self.s_io.messages
        deliver  = self.s_io.deliver_next_message

        node_action = self.node_action
        for node in nodes:
            node_action(node)
        while deliver():
            pass


from networking.message import (
    XMLSerializer, XMLDeserializer, SAXCache,
    XMLViewSerializer, XMLViewDeserializer,
    XMLSpecSerializer, XMLSpecDeserializer )

class MessageTypes(object):
    MSG_SPECS = 1
    MSG_NODES = 2
    MSG_BOTH  = 3


class XMLMessageSerializer(XMLSerializer):
    def __init__(self, xml_out):
        XMLSerializer.__init__(self, xml_out)
        self.view_serializer = XMLViewSerializer(xml_out)
        self.spec_serializer = XMLSpecSerializer(xml_out)

    def serialize(self, msg_type, objects):
        saxout = self.saxout
        serialize_spec = self.spec_serializer.serialize_spec
        serialize_node = self.view_serializer.serialize_node
        serialize_view = self.view_serializer.serialize_view

        object_iterator = iter(objects)
        deferred        = defer.succeed(None)
        def handle_next_object(_, obj):
            try:
                while not hasattr(obj, 'iterNodes'):
                    if isinstance(obj, ViewSpecification):
                        serialize_spec(obj)
                    elif isinstance(obj, AbstractNode):
                        serialize_node(obj)
                    else:
                        print "FAILED:", type(obj)
                    obj = object_iterator.next()

                new_deferred = serialize_view(obj)
                obj = object_iterator.next()

            except StopIteration:
                new_deferred.addCallback(self._terminate_message)
                return new_deferred

            new_deferred.addCallback(handle_next_object, obj)
            return new_deferred

        saxout.startElement('message', {'type':msg_type})
        try:
            obj = object_iterator.next()
            deferred.addCallback(handle_next_object, obj)
        except StopIteration:
            deferred.addCallback(self._terminate_message)
        return deferred

    def _terminate_message(self, _):
        self.saxout.endElement('message')


class XMLMessageDeserializer(XMLDeserializer):
    def __init__(self, reader):
        self.view_deserializer = XMLViewDeserializer()
        self.spec_deserializer = XMLSpecDeserializer()
        XMLSerializer.__init__(self, reader)

    def deserialize(self, msg_type, objects):
        saxout = self.saxout
        saxout.startElement('message', {'type':msg_type})
        for obj in objects:
            if isinstance(obj, NodeView):
                self.view_serializer.serialize_view(obj)
            elif isinstance(obj, DBNode) or isinstance(obj, ViewNode):
                self.view_serializer.serialize_node(obj)
            elif isinstance(obj, ViewSpecification):
                self.spec_serializer.serialize_spec(obj)
            else:
                print "FAILED:", type(obj)
        saxout.endElement('message')
