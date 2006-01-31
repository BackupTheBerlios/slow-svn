try:
    from psyco.classes import *
except:
    pass

import logging
from weakref import WeakValueDictionary

from slow.pyexec.utils.observable import Observable, ReflectiveObservable
from node import StaticNode


class PyAttribute(object):
    def __init__(self, attribute):
        self.name = attribute.name
        self.type_name    = attribute.type_name
        self.selected     = attribute.selected
        self.transferable = attribute.transferable
        self.identifier   = attribute.identifier
        self.static       = attribute.static

class NodeDB(ReflectiveObservable):
    NOTIFY_ADD_NODES    = 'add_nodes'
    NOTIFY_REMOVE_NODES = 'remove_nodes'
    NOTIFY_UPDATE_NODES = 'update_nodes'

    def __init__(self, name, local_node,
                 pyattributes, attribute_defaults=None):
        ReflectiveObservable.__init__(self)
        self.name = name
        self.local_node = local_node

        self.__identifiers = sorted( attribute.name for attribute in pyattributes.values()
                                     if attribute.identifier )

        def node_identifier(node):
            return tuple(getattr(node, name) for name in self.__identifiers)

        self.node_identifier = node_identifier
        self.__orig_attributes = pyattributes
        self.__attributes = pyattributes
        self.__attribute_defaults = attribute_defaults or {}

        self.__nodes = {}
        self.__views = {}

        self.__logger = logging.getLogger('DB')

    def __iter__(self):
        return self.__nodes.itervalues()

    def __true_predicate(self, node):
        return True

##     def addAttribute(self, name, atype, default_value=None):
##         attributes = self.__attributes
##         if name in attributes:
##             raise ValueError, "Attribute '%s' is already declared." % name
##         if attributes is self.__orig_attributes:
##             self.__attributes = attributes = attributes.copy()
##         attributes[name] = atype
##         self.__attribute_defaults[name] = default_value

    def getIdentifiers(self):
        return self.__identifiers

    def getAttributeTypes(self):
        return self.__attributes.values()

    def getNodeAttributes(self):
        return self.__attributes.keys()

    def getAttributeType(self, name):
        return self.__attributes[name]

    def getAttributeDefault(self, name):
        try:
            return self.__attribute_defaults[name]
        except KeyError:
            if name in self.__attributes:
                return None
            else:
                raise

    def wrap_node(self, node):
        if isinstance(node, DBNode):
            return node
        else:
            return DBNode(self, **dict(node._iter_attributes()))

    def addNode(self, node):
        self.addNodes( (node,) )

    def addNodes(self, nodes):
        identifier = self.node_identifier
        identifiers = self.__identifiers
        local_node  = self.local_node

        def is_local_node(node):
            for id_attr in identifiers:
                try:
                    if getattr(node, id_attr) == getattr(local_node, id_attr):
                        return True
                except AttributeError:
                    pass
            return False

        wrap_node   = self.wrap_node
        current_nodes = self.__nodes
        added   = []
        updated = []
        for node in nodes:
            if is_local_node(node):
                continue
            node_id = identifier(node)
            db_node = current_nodes.get( node_id )
            if db_node is None:
                node = wrap_node(node)
                added.append(node)
                current_nodes[node_id] = node
            else:
                updated.append(db_node)
                for name, value in node._iter_attributes():
                    setattr(db_node, name, value)
        if added or updated: # FIXME
            self._notify(self.NOTIFY_ADD_NODES, added+updated)

    def removeNode(self, node):
        try:
            del self.__nodes[self.node_identifier(node)]
        except KeyError:
            return
        self._notify(self.NOTIFY_REMOVE_NODES, (node,))

    def updateNodeAttribute(self, node, attr):
        self._notify(self.NOTIFY_UPDATE_NODES, node,
                            attr, getattr(node,attr))

    def addView(self, view):
        #view.setDB(self)
        self.__views[view] = view
        self.subscribe(view)

    def removeView(self, view):
        self.unsubscribe(view)
        del self.__views[view]


class TypedAttributeDescriptor(object):
    __slots__ = ('name', 'type')
    def __init__(self, name, atype):
        self.name, self.type = name, atype
    def __get__(self, instance, owner):
        if instance is None: return self
        try:
            return instance._values[self.name]
        except KeyError:
            raise AttributeError, self.name
    def __set__(self, instance, value):
        atype = self.type
        aname = self.name
        if atype is None or isinstance(value, atype):
            instance._values[aname] = value
            instance._notify_update(instance, aname, value)
        else:
            raise TypeError, "got %s, expected %s" % (type(value), atype)


class DBNode(object):
    def __init__(self, database, change_observer=None, **kwargs):
        self._database = database
        self._values   = kwargs

        for attribute_name in self._database.getNodeAttributes():
            self.__create_attribute(attribute_name)

        self.setChangeObserver(change_observer)

    def __silent(self, observable, name, value):
        pass

    def __create_attribute(self, name):
        try:
            atype = self._database.getAttributeType(name)
        except KeyError:
            raise AttributeError, name

        setattr(self.__class__, name, TypedAttributeDescriptor(name, atype))

    def __setattr__(self, name, value):
        if name[:1] == '_':
            object.__setattr__(self, name, value)
            return
        self.__create_attribute(name)
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        try:
            value = self._database.getAttributeDefault(name)
            setattr(self, name, value)
            return value
        except KeyError:
            raise AttributeError, name

    def _iter_attributes(self):
        # FIXME: default values?
        for name in sorted(self._database.getAttributeTypes()):
            yield (name, getattr(self, name))

    def getAttributeTypes(self):
        return self._database.getAttributeTypes()

    def setChangeObserver(self, observer):
        self._notify_update = observer or self.__silent

    def __repr__(self):
        return "node[%s]" % ','.join( "%s=%r" % (name, getattr(self,name,None))
                                      for name in self._getIDs() )

    def _getIDs(self):
        return self._database.getIdentifiers()


class LocalNode(StaticNode):
    def __init__(self, ids, **kwargs):
        ids = sorted(name for name in ids if name in kwargs)
        StaticNode.__init__(self, kwargs, ids)


################################################################################
################################################################################
################################################################################


class DBNodeProperty(property, Observable):
    __slots__ = ()
    def __init__(self, *args):
        l = len(args)
        if l >= 4:
            doc = args[3]
        else:
            doc = None

        if l < 2:
            args += (None, None)
        fget, fset = args[:2]

        self.__getval = fget
        if fget:
            fget = self._get

        self.__setval = fset
        if fset:
            fset = self._set

        property.__init__(self, fget, fset, None, doc)
        Observable.__init__(self)

    def _get(self, obj):
        return self.__getval()

    def _set(self, obj, value):
        self.__setval(value)


class BoundProperty(property):
    __slots__ = ()
    def __init__(self, *args):
        l = len(args)
        if l >= 4:
            doc = args[3]
        else:
            doc = None

        if l < 2:
            args += (None, None)
        fget, fset = args[:2]

        self.__getval = fget
        if fget:
            fget = self._get

        self.__setval = fset
        if fset:
            fset = self._set

        property.__init__(self, fget, fset, None, doc)

    def _get(self, obj):
        return self.__getval()

    def _set(self, obj, value):
        self.__setval(value)


class ObservableProperty(BoundProperty, Observable):
    __slots__ = ()
    def __init__(self, *args):
        BoundProperty.__init__(self, *args)
        Observable.__init__(self)

    def _set(self, obj, value):
        BoundProperty._set(self, obj, value)
        self._notify(value)


class DescriptorProxy(object):
    __slots__ = ()
    def __init__(self, name, doc=None):
        self.__name = name
        if doc:
            self.__doc__ = doc

    def __get__(self, instance, owner):
        if instance == None:
            return self
        else:
            return getattr(instance._back_object, self.__name)

    def __set__(self, instance, value):
        setattr(instance._back_object, self.__name, value)


class ObservableDescriptorProxy(DescriptorProxy):
    __slots__ = ()
    def __init__(self, observable, *args):
        DescriptorProxy.__init__(self, *args)
        self.__observable = observable

    def __set__(self, instance, value):
        DescriptorProxy.__set__(self, instance, value)
        self.__observable._notify(value)


#_node_classes = WeakValueDictionary()

class BackedNode(object):
    __slots__ = ('_back_object')

    def __new__(cls, property_names, back_object):
        property_names = tuple(sorted(set( name for name in property_names
                                           if name and name[0] != '_' )))
        key = (cls,) + property_names
        try:
            node_class = _node_classes[key]
        except KeyError:
            properties = { '__slots__' : property_names }
            node_class = type('Node', (cls,), properties)
            for name in property_names:
                setattr(node_class, name, DescriptorProxy(name))

            _node_classes[key] = node_class

        return object.__new__(node_class)

    def __init__(self, property_names, back_object):
        self._back_object = back_object
        cls = self.__class__


class ObservableBackedNode(BackedNode):
    __slots__ = ('__notifiers')

    def __init__(self, property_names, *args):
        self.__notifiers = dict( (name, Observable()) for name in property_names )
        BackedNode.__init__(self, property_names, *args)

    def _build_proxies(self, property_names):
        return iter( (name, ObservableDescriptorProxy(observable, name))
                     for name, observable in self.__notifiers.iteritems()
                     )

    def subscribe(self, name, listener):
        self.__notifiers[name].subscribe(listener)

    def unsubscribe(self, name, listener):
        self.__notifiers[name].unsubscribe(listener)


class Node(object):
    """Node is a property container.
    It only carries properties, no data.
    """

    def __new__(cls, properties={}):
        "Create and instantiate a new Node subclass with the given properties."
        for name in properties:
            cls.__check_property_name(name)

        cls = type('Node', (cls,), dict(properties))

        return object.__new__(cls)

    @staticmethod
    def __check_property_name(name):
        if not name or name[0] == '_':
            raise AttributeError, "Invalid property name"

    @classmethod
    def _setProperty(cls, name, property_object):
        cls.__check_property_name(name)
        setattr(cls, name, property_object)

    @classmethod
    def _getProperty(cls, name, *args):
        cls.__check_property_name(name)
        return getattr(cls, name, *args)

    @classmethod
    def _getProperties(cls, pnames=None):
        if pnames is None:
            pnames = dir(cls)
        return dict( cls._iterProperties(pnames) )

    @classmethod
    def _iterProperties(cls, pnames=None):
        return ( (name, getattr(cls, name))
                 for name in (pnames or dir(cls))
                 if name and name[0] != '_' )

    @classmethod
    def __iter__(cls):
        return cls._iterProperties()

    @classmethod
    def __copy__(cls):
        return cls._getCopy()

    _copy = __copy__

    @classmethod
    def _getCopy(cls, property_names=None):
        properties = cls._getProperties(property_names)
        return cls(properties)

    @classmethod
    def _subscribe(cls, property_name, listener):
        cls.__check_property_name(property_name)
        property_object = getattr(cls, property_name)
        property_object.subscribe(listener)

    @classmethod
    def _unsubscribe(cls, property_name, listener):
        cls.__check_property_name(property_name)
        property_object = getattr(cls, property_name)
        property_object.unsubscribe(listener)


class PropertyTransformer(object):
    """Convert a property value on get and set.
    The constructor takes two functions as argument and applies them
    after getting and before setting a value.
    """
    def __init__(self, get_transform, set_transform):
        self._get_transform, self._set_transform = get_transform, set_transform

#    @cachedmethod
    def __build_setter(self, property_object, transform, setter):
        if transform:
            def set_transform(value):
                return setter(property_object, transform(value))
        else:
            def set_transform(value):
                return setter(property_object, value)

        return set_transform

#    @cachedmethod
    def __build_getter(self, property_object, transform, getter):
        if transform:
            def get_transform():
                return transform(getter(property_object))
        else:
            def get_transform():
                return getter(property_object)

        return get_transform

    def __call__(self, property_object):
        if self._get_transform is None and self._set_transform is None:
            return property_object

        fget, fset, fdel, doc = property_object.fget, property_object.fset, property_object.fdel, property_object.__doc__

        if fget:
            fget = self.__build_getter(property_object, self._get_transform, fget)

        if fset:
            fset = self.__build_setter(property_object, self._set_transform, fset)

        return property_object.__class__(fget, fset, fdel, doc)


class NodeTransformer(object):
    "Transforms a node by selecting and transforming its properties."
    def __init__(self, selected_properties, transformers={}, node_type=None):
        self._selected_properties, self._transformers = selected_properties, transformers
        self._node_type = node_type

    def __call__(self, node):
        """Selects node properties and applies all property transformers
        to them.
        """
        properties = node._getProperties(self._selected_properties)
        for name, transformer in self._transformers:
            if name in properties:
                properties[name] = transformer(properties[name])

        if self._node_type:
            node_type = self._node_type
        else:
            node_type = type(node)

        return node_type(properties)
