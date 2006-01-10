from itertools import *

from slow.model.message_hierarchy_model import *


class MessageClassBuilder(object):
    def __init__(self, global_containers={}, view_descriptions={}):
        self.global_containers = global_containers
        self.view_descriptions = view_descriptions

    def from_model(self, model):
        if isinstance(model, MessageModel):
            return [ self.build_message_class(model, ()) ]
        elif not isinstance(model, HeaderModel):
            raise ValueError, "Invalid model, only messages and headers allowed."

        return self.build_messages(model, [])

    def build_messages(self, model, headers):
        if isinstance(model, MessageModel):
            return [ self.build_message_class(model, headers) ]
        elif not isinstance(model, HeaderModel):
            return []

        headers  = list(headers)
        children = self.collect_children(model)

        if model.access_name:
            headers.append( (model.access_name, children) )
        elif headers:
            old_name, header = headers[-1]
            header = header.copy()
            header.update(children)
            headers[-1] = (old_name, header)

        messages = []
        for child in model.iterchildren():
            messages.extend( self.build_messages(child, headers) )
        return messages

    def collect_children(self, model):
        children = {}
        for child in model.iterchildren():
            if isinstance(child, (MessageModel, HeaderModel)):
                continue

            child_property = None
            if isinstance(child, MessageFieldHierarchy):
                child_dict = self.collect_children(child)
                if child.access_name:
                    child_property = self.build_container(
                        child.access_name, child_dict)
                else:
                    children.update(child_dict)
            elif isinstance(child, ViewDataModel):
                child_property = self.build_view_container(child)

            if child_property:
                children[child.access_name] = child_property
        return children

    def build_init(self, attributes):
        iter_attributes = attributes.iteritems
        def init_attributes(obj, **init_args):
            get_init_value = init_args.get
            for name, value in iter_attributes():
                if isinstance(value, type):
                    value = value()
                else:
                    value = get_init_value(name, value)
                setattr(obj, name, value)
        return init_attributes

    def build_container(self, name, children):
        return type(name, (object,),
                    {'__init__'  : self.build_init(children),
                     '__slots__' : children.keys()})

    def build_message_class(self, model, headers):
        build_container = self.build_container
        children = self.collect_children(model)
        class MessageClass(object):
            __slots__ = children.keys() + [ item[0] for item in headers ]
            def __init__(self, **kwargs):
                self.__init_headers(**kwargs)
                self.__init_children(**kwargs)

            __init_children = self.build_init(children)
            __init_headers  = self.build_init( dict(
                (name, build_container(header))
                for (name, header) in headers) )

        return MessageClass

    class NodeContainer(object):
        __EMPTY_ITER = iter(())
        def __init__(self):
            self.nodes = None

        def _set_nodes(self, nodes):
            self.nodes = self._STORE(nodes)

        def _iterator(self, iterable, callback):
            iterator = iter(iterable)
            if callback:
                callback(iterator)
                return self.__EMPTY_ITER
            else:
                return iterator

    class StructuredViewContainer(NodeContainer):
        _STORE = dict
        def data_from_view(self, view):
            view.iterBuckets(self._set_nodes)

        def data_from_node_dict(self, node_dict):
            self._set_nodes(node_dict)

        def data_from_attribute_tuple_dict(self, attribute_tuple_dict):
            self._set_nodes(
                (variables, tuple(starmap(self.NODE_CLASS, attribute_tuples)))
                for variables, attribute_tuples in attribute_tuple_dict.iteritems()
                )

        def bucket(self, **kwargs):
            variables = tuple(item[0] for item in sorted(kwargs.iteritems()))
            return self.nodes.get(variables, ())

        def iterBuckets(self, callback=None):
            return self._iterator( self.nodes.iteritems(), callback )

        def iterNodes(self, callback=None):
            return self._iterator( self.nodes.itervalues(), callback )

    class NodeListContainer(NodeContainer):
        _STORE = tuple
        def data_from_view(self, callback, view):
            view.iterNodes(self._set_nodes)

        def data_from_node_list(self, node_list):
            self._set_nodes(node_list)

        def data_from_attribute_tuple_list(self, attribute_tuple_list):
            self._set_nodes( starmap(self.NODE_CLASS, attribute_tuple_list) )

        def bucket(self):
            return self.nodes

        def iterBuckets(self, callback=None):
            return self._iterator( [((), self.nodes)], callback )

        def iterNodes(self, callback=None):
            return self._iterator(self.nodes, callback)

    def build_view_container(self, model):
        name = model.access_name
        view_description = self.view_descriptions[model.type_name]
        attribute_names = sorted(view_description.iterselectnames())

        _setattr, _izip, _chain = setattr, izip, chain
        class Node(object):
            __slots__ = attribute_names
            def __init__(self, *args, **kwargs):
                for name, value in _chain(_izip(attribute_names, args), kwargs.iteritems()):
                    _setattr(self, name, value)

        if model.structured:
            class View(self.StructuredViewContainer):
                NODE_CLASS = Node
                _buckets = sorted((bucket.name, bucket.parsed_declaration)
                                  for bucket in view_description.iterforeach())
        else:
            class View(self.NodeListContainer):
                NODE_CLASS = Node
