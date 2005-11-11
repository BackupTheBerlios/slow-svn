from itertools import *
import random, copy

try:
    from psyco.classes import *
except ImportError:
    pass

try:
    from optimize import bind_all
except:
    def bind_all(*args, **kwargs):
        pass

from viewspec   import ViewFunctions
from observable import ReflectiveObservable
from db         import NodeDB
from node       import AbstractNode


class DependencyError(AttributeError):
    __ERROR_LINE = "Parent view '%s' misses attribute '%s' that this view depends on."
    def __init__(self, parent_view_name, attr_name):
        AttributeError.__init__(self, self.__ERROR_LINE % (parent_view_name,attr_name))

class ViewRegistry(object):
    def __init__(self, base_view):
        self.base_view = base_view
        self.unregister_all()

    def unregister_all(self):
        self.__register = {}
        self.register(self.base_view)

    def register(self, view, replace=False):
        name = view.name
        if not name or name[0] == '_':
            raise ValueError, name
        elif self.__register.has_key(name):
            if replace:
                self.unregister(self.__register[name])
            else:
                raise ValueError, name

        self.__register[name] = view

        if hasattr(view, 'parents'):
            for parent in view.parents:
                if hasattr(parent, 'addView'):
                    parent.addView(view)

    def unregister(self, view):
        del self.__register[view.name] # raises appropriate KeyError
        for parent in view.parents:
            if hasattr(parent, 'removeView'):
                parent.removeView(view)

    def __iter__(self):
        return self.__register.iterkeys()

    def __len__(self):
        return len(self.__register)

    def __getitem__(self, view_name):
        return self.__register[view_name]

    def __contains__(self, view):
        if hasattr(view, 'name'):
            view = view.name
        return view in self.__register


#STATIC_VIEWREG = ViewRegistry() # FIXME: base_view ???


class NodeView(ReflectiveObservable):
    """Holds a dict (of dicts of dicts of dicts) of nodes that match
    the view specification."""
    def __init__(self, spec, viewreg, **variable_initializations):
        ReflectiveObservable.__init__(self)
        self.parents  = tuple( viewreg[parent] # raises KeyError
                               for parent in spec.view_parents )
        self.name     = spec.view_object.name

        self._spec    = spec
        self._viewreg = viewreg
        self._attribute_dependencies = spec.getDependencies()
        self._variables = spec.variable_options

        node_selector = spec.object_select.get('node')
        if hasattr(node_selector, 'getFunction'):
            node_selector = node_selector.getFunction()
        self._node_selector = node_selector

        for var_name, value in variable_initializations.iteritems():
            self._setVariable(var_name, value)

        # check attribute dependencies against parent
        # TODO: how to supply all parent attributes if the spec list is empty (i.e. unrestricted?)
        for parent in self.parents:
            if hasattr(parent, 'getNodeAttributes'):
                parent_attributes = parent.getNodeAttributes()
                for attr_dep in self._attribute_dependencies:
                    if attr_dep.name not in parent_attributes:
                        raise DependencyError(parent.name, attr_dep.name)

        # build class for view nodes
        self._node_class = self._build_node_class()

        view_functions = ViewFunctions()
        self.distinct_selector = view_functions.hash_distinct

        # populate view and register
        self._select_parent_nodes()
        viewreg.register(self)

    def _build_node_class(self):
        """Build a new view node class.
        Attributes are converted using the expressions defined in the
        view specification.
        """
        spec = self._spec
        attributes = spec.view_object.attributes

        class ViewNode(AbstractNode):
            _attributes   = tuple(sorted(attr.name for attr in attributes.iterkeys()))
            _dependencies = {}
            __slots__ = ('_back_node', '_hashval', '_values') + _attributes
            def __init__(self, back_node, value_dict):
                self._back_node = back_node
                self._hashval   = hash(back_node)

                self._values = values = value_dict.copy()
                values['node'] = back_node
            def _set_qos(self, attr_name, function):
                propagate_qos = self._back_node._set_qos
                for attribute in self._dependencies[attr_name]:
                    propagate_qos(attribute.name, function)

        dependencies = ViewNode._dependencies
        for attr, function in attributes.iteritems():
            if function is None:
                value = self.BackedAttributeDescriptor( attr.name )
                f_dependencies = (attr,)
            elif function.isConstant():
                value = self.ConstantAttributeDescriptor( function.evaluate() )
                f_dependencies = ()
            else:
                value = self.FunctionAttributeDescriptor( function.evaluate )
                f_dependencies = function.getDependencies()
            setattr(ViewNode, attr.name, value)
            dependencies[attr.name] = f_dependencies

        return ViewNode

    class FunctionAttributeDescriptor(object):
        __slots__ = 'function'
        def __init__(self, function):
            self.function = function
        def __get__(self, instance, owner):
            if instance is None: return self
            return self.function(instance._values)
        def __set__(self, instance, value):
            raise AttributeError, "can't set attribute value"

    class BackedAttributeDescriptor(object):
        __instances = {}
        __slots__ = 'attr_name'
        def __new__(cls, attr_name):
            try: return cls.__instances[attr_name]
            except KeyError:
                instance = cls.__instances[attr_name] = object.__new__(cls)
                instance.attr_name = attr_name
                return instance
        def __get__(self, instance, owner):
            if instance is None: return self
            return getattr(instance._back_node, self.attr_name)
        def __set__(self, instance, value):
            raise AttributeError, "can't set attribute value"

    class ConstantAttributeDescriptor(object):
        __slots__ = 'value'
        def __init__(self, value):
            self.value = value
        def __get__(self, instance, owner):
            if instance is None: return self
            return self.value
        def __set__(self, instance, value):
            raise AttributeError, "can't set attribute value"

    def __getitem__(self, val_tuple):
        return self._nodes[val_tuple]

    def getBucket(self, *val_tuple):
        if len(val_tuple) == 1 and isinstance(val_tuple[0], tuple):
            val_tuple = val_tuple[0]
        return self._nodes[val_tuple]

    def iterBuckets(self):
        return iter(self._nodes.items())

    def discard(self):
        try: self._viewreg.unregister(self)
        except ValueError: pass

    def getSpec(self):
        return self._spec

    def getNodeAttributes(self):
        return [ attr.name for attr in self._spec.view_object.attributes.iterkeys() ]

    def __iter__(self):
        # FIXME!
        return chain(*self._nodes.values())

    def __len__(self):
        # FIXME!
        return sum( len(nodes) for nodes in self._nodes.itervalues() )

    def randomNode(self):
        return random.choice(tuple(self._nodes))

    def getVariable(self, name):
        try:
            return self._variables[name].value
        except KeyError:
            raise ValueError, "Unknown variable name: %s" % name

    def _setVariable(self, name, value):
        try:
            self._variables[name].value = value
        except KeyError:
            raise ValueError, "Unknown variable name: %s" % name

    def setVariable(self, name, value):
        self._setVariable(name, value)
        self._select_parent_nodes()
        self._notify(NodeDB.NOTIFY_ADD_NODES, ())

    def setVariables(self, **variables):
        for name, value in variables.iteritems():
            self._setVariable(name, value)
        self._select_parent_nodes()
        self._notify(NodeDB.NOTIFY_ADD_NODES, ())

    # trivial implementations:
    def add(self, nodes):
        self._select_parent_nodes()
        self._notify(NodeDB.NOTIFY_ADD_NODES, ())

    def remove(self, nodes):
        self._select_parent_nodes()
        self._notify(NodeDB.NOTIFY_REMOVE_NODES, ())

    def update(self, nodes, attr, new_val):
        if attr in self._attribute_dependencies:
            self._select_parent_nodes()
            self._notify(NodeDB.NOTIFY_UPDATE_NODES, ())

    def addView(self, view):
        self.subscribe(view)

    def removeView(self, view):
        self.unsubscribe(view)

    notify_add_nodes    = add
    notify_remove_nodes = remove
    notify_update_nodes = update

    def _match_nodes(self, bucket_list):
        """Selects nodes from the given buckets that match the view spec.
        If requested via 'DISTINCT', duplicates are removed based on their
        hash value after ranking. This means that the duplicate with the
        highest ranking will end up in the result. However, if the ranking
        is the same for the duplicates, the choice may be arbitrary.
        """
        spec = self._spec
        from_buckets = spec.select_buckets

        if len(bucket_list) == 0:
            return {():[]}

        buckets = {}
        select_nodes_into_buckets = self._select_nodes_into_buckets

        if from_buckets:
            if len(bucket_list) > 1:
                raise ValueError, "Bucket selection needs single node source."
            all_nodes = bucket_list[0]
            if not hasattr(all_nodes, 'iterBuckets'):
                select_nodes_into_buckets(spec, all_nodes, buckets)
            else:
                for bucket_tuple, node_list in all_nodes.iterBuckets():
                    select_nodes_into_buckets(spec, node_list, buckets, bucket_tuple)
        elif len(bucket_list) == 1:
            select_nodes_into_buckets(spec, bucket_list[0], buckets)
        else:
            all_nodes = []
            for l in bucket_list:
                all_nodes.extend(l)
            select_nodes_into_buckets(spec, all_nodes, buckets)

        return buckets

    def _select_nodes_into_buckets(self, spec, all_nodes, buckets, tuple_prefix=()):
        value_dict = dict( (var.name, var.value)
                           for var in self._variables.values() )

        filter          = spec.where_expression.filter
        node_select     = self._node_selector
        build_view_node = self._node_class

        if node_select:
            # without loops, value_tuple is just ()
            for value_tuple in spec.iter_loop_variables(value_dict):
                candidate_iterator = filter('node', all_nodes, value_dict)
                matches = [ build_view_node(node, value_dict)
                            for node in node_select(candidate_iterator, value_dict)
                            ]
                buckets[tuple_prefix+value_tuple] = matches
        elif spec.select_distinct:
            distinct = self.distinct_selector
            for value_tuple in spec.iter_loop_variables(value_dict):
                candidate_iterator = filter('node', all_nodes, value_dict)
                matches = [ build_view_node(node, value_dict)
                            for node in distinct(candidate_iterator) ]
                buckets[tuple_prefix+value_tuple] = matches
        else:
            for value_tuple in spec.iter_loop_variables(value_dict):
                candidate_iterator = filter('node', all_nodes, value_dict)
                matches = [ build_view_node(node, value_dict)
                            for node in candidate_iterator ]
                buckets[tuple_prefix+value_tuple] = matches

    def _select_parent_nodes(self):
        "Selects nodes from the parent view and wraps them into this view."
        self._nodes = self._match_nodes(self.parents)
        qos = self._spec.getQoSParameters()
        if qos:
            self._setQoSParameters(qos)

    def _set_qos_parameters(self, parameters):
        for node in self._nodes:
            for attribute_name in node:
                for function in parameters.get(attribute_name, ()):
                    node._set_qos(attribute_name, function)

def build_view_cascade(view_specs, viewreg, view_type=NodeView):
    "Creates the views in order of dependency and interconnects them."
    view_specs    = set(view_specs)
    view_names    = set(spec.view_name for spec in view_specs)

    orphant_specs = set()

    def is_known_view(view_name):
        return (view_name in view_names) or (view_name in viewreg)

    for spec in view_specs:
        known_parents = filter(is_known_view, spec.view_parents)
        if not known_parents:
            orphant_specs.add(spec)

    views = []
    base_name = viewreg.base_view
    for spec in orphant_specs:
        spec = copy.copy(spec)
        spec.view_parent = base_name
        views.append( view_type(spec, viewreg) )

    remaining_specs = view_specs - orphant_specs
    while remaining_specs:
        add_success = False
        for spec in tuple(remaining_specs):
            known_parents = filter(is_known_view, spec.view_parents)
            if len(known_parents) == len(spec.view_parents):
                add_success = True
                views.append( view_type(spec, viewreg) )
                #known_names.add(spec.view_name)
                remaining_specs.discard(spec)
        if not add_success:
            break

    return (views, tuple(remaining_specs))


import sys
bind_all(sys.modules[__name__])
