from itertools import *
import random, copy, heapq

try:
    from psyco.classes import *
except ImportError:
    pass

try:
    from optimize import bind_all
except:
    def bind_all(*args, **kwargs):
        pass

from lxml import etree
from lxml.etree import ETXPath

from mathml.utils import pyterm

from slow.pyexec.utils.observable import ReflectiveObservable
from db   import NodeDB
from node import AbstractNode


ATTRIBUTE_XPATH  = ETXPath(u"//{http://www.w3.org/1998/Math/MathML}ci[contains('node.', text())]")
DEPENDENCY_XPATH = ETXPath(u"//{http://www.w3.org/1998/Math/MathML}ci")

class PySlosl(object):
    class PyRanked(object):
        def __init__(self, ranked, _math_compile):
            self.function = ranked.function
            self.parameters = [
                _math_compile(param, '<rankparam%d>' % i)
                for i, param in enumerate(ranked.parameters)
                ]
    def __init__(self, slosl):
        self.xml_slosl = slosl
        self.attribute_dependencies = set(
            a.name() for a in ATTRIBUTE_XPATH.evaluate(slosl))

        mcompile = self._math_compile
        self.name     = slosl.name
        self.parents  = slosl.parents
        self.bucket   = slosl.bucket
        self.where    = mcompile(slosl.where,  '<where>')  or 'True'
        self.having   = mcompile(slosl.having, '<having>') or 'True'
        self.selects  = list((n, mcompile(v, '<select>'))  for (n,v) in slosl.selects)
        self.withs    = list((n, mcompile(v, '<with>'))    for (n,v) in slosl.withs)
        self.foreachs = list((n, mcompile(v, '<foreach>')) for (n,v) in slosl.foreachs)
        try:
            self.ranked = self.PyRanked(slosl.ranked, self._math_compile)
        except AttributeError:
            self.ranked = None

    def _math_compile(self, expr, name):
        try:
            return compile(expr.serialize('python'), name, 'eval')
        except AttributeError:
            return None


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

    @property
    def local_node(self):
        return self.base_view.local_node

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
    def __init__(self, pyslosl, viewreg, name_override=None,
                 **variable_initializations):
        ReflectiveObservable.__init__(self)
        self._slosl_statement = pyslosl

        self.parents  = tuple( viewreg[parent] # raises KeyError
                               for parent in pyslosl.parents )
        self.name     = name_override or pyslosl.name
        self._viewreg = viewreg
        self._attribute_dependencies = pyslosl.attribute_dependencies
        self._variables = variables = {}
        _globals = globals()
        _locals  = {}
        for var_name, var_value in pyslosl.withs:
            variables[var_name] = eval(var_value, _globals, _locals)

        ranked = pyslosl.ranked
        function_name = ranked.function or None

        if function_name in VIEW_FUNCTIONS.VALID_FUNCTIONS:
            node_selector = getattr(VIEW_FUNCTIONS, function_name)
            self._node_ranker = node_selector(*ranked.parameters)
        else:
            self._node_ranker = None

        for var_name, value in variable_initializations.iteritems():
            self._setVariable(var_name, value)

        # check attribute dependencies against parent
        # TODO: how to supply all parent attributes if the spec list is empty (i.e. unrestricted?)
##         for parent in self.parents:
##             if hasattr(parent, 'getNodeAttributes'):
##                 parent_attributes = parent.getNodeAttributes()
##                 for attr_dep in self._attribute_dependencies:
##                     if attr_dep.name not in parent_attributes:
##                         raise DependencyError(parent.name, attr_dep.name)

        # build class for view nodes
        self._node_class = self._build_node_class()

        self.distinct_selector = VIEW_FUNCTIONS._hash_distinct

        # populate view and register
        self._select_parent_nodes()
        viewreg.register(self)

    @property
    def local_node(self):
        return self._viewreg.local_node

    def _build_node_class(self):
        """Build a new view node class.
        Attributes are converted using the expressions defined in the
        view specification.
        """
        selects = self._slosl_statement.selects

        dependencies = {}
        class ViewNode(AbstractNode):
            _attributes   = tuple(sorted(name for (name, value) in selects))
            _dependencies = dependencies
            __slots__ = ('_back_node', '_hashval', '_values', '_ids') + _attributes
            def __init__(self, back_node, value_dict):
                self._back_node = back_node
                self._hashval   = hash(back_node)
                self._ids       = back_node._getIDs()

                self._values = values = value_dict.copy()
                values['node'] = back_node
##             def _set_qos(self, attr_name, function):
##                 propagate_qos = self._back_node._set_qos
##                 for attribute in self._dependencies[attr_name]:
##                     propagate_qos(attribute.name, function)

        _globals = globals()
        for attr_name, function in selects:
            value = self.FunctionAttributeDescriptor( function, _globals )
            setattr(ViewNode, attr_name, value)
##             f_dependencies = set(d.name for d in DEPENDENCY_XPATH.evaluate(attr_value))
            dependencies[attr_name] = function.co_names

        return ViewNode

    class FunctionAttributeDescriptor(object):
        __slots__ = ('function', '_globals')
        def __init__(self, function, _globals):
            self.function = function
            self._globals = _globals
        def __get__(self, instance, owner):
            if instance is None: return self
            return eval(self.function, self._globals, instance._values)

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

    class ConstantAttributeDescriptor(object):
        __slots__ = 'value'
        def __init__(self, value):
            self.value = value
        def __get__(self, instance, owner):
            if instance is None: return self
            return self.value

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
        return self._slosl_statement

    def getNodeAttributes(self):
        return [ select.name for select in self._slosl_statement.selects ]

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
            return self._variables[name]
        except KeyError:
            raise ValueError, "Unknown variable name: %s" % name

    def _setVariable(self, name, value):
        try:
            self._variables[name] = value
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

    def variables(self):
        return self._variables

    # trivial implementations:
    def add(self, nodes):
        self._select_parent_nodes()
        self._notify(NodeDB.NOTIFY_ADD_NODES, ())

    def remove(self, nodes):
        self._select_parent_nodes()
        self._notify(NodeDB.NOTIFY_REMOVE_NODES, ())

    def update(self, nodes, attr, new_val):
        if attr.name in self._attribute_dependencies:
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
        spec = self._slosl_statement
        from_buckets = spec.foreachs

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

    def _iter_foreach_values(self, foreachs, value_dict):
        if not foreachs:
            yield ()
        else:
            _pyeval  = eval
            _globals = globals()
            variable_name, values = foreachs[0]
            for var_values in self._iter_foreach_values(foreachs[1:], value_dict):
                py_values = _pyeval(values, _globals, value_dict)
                for value in py_values:
                    value_dict[variable_name] = value
                    yield var_values + (value,)

    def _select_nodes_into_buckets(self, spec, all_nodes,
                                   buckets, tuple_prefix=()):
        static_value_dict = self._variables.copy()
        static_value_dict['local'] = self.local_node

        _eval = eval
        _bool = bool
        where_expr = spec.where
        eval_globals = globals()
        eval_globals['local'] = self.local_node
        def where(node):
            eval_globals['node'] = node
            return _bool(_eval(where_expr, eval_globals, static_value_dict))

        node_rank       = self._node_ranker
        build_view_node = self._node_class

        loop_value_dict = static_value_dict.copy()
        having_expr = spec.having
        def having(node):
            eval_globals['node'] = node
            return _bool(_eval(having_expr, eval_globals, loop_value_dict))

        candidates = filter(where, all_nodes)

        if node_rank:
            # without loops, value_tuple is just ()
            for value_tuple in self._iter_foreach_values(spec.foreachs,
                                                         loop_value_dict):
                candidate_iterator = ifilter(having, candidates)
                matches = [ build_view_node(node, loop_value_dict)
                            for node in node_rank(candidate_iterator,
                                                  loop_value_dict)
                            ]
                buckets[tuple_prefix+value_tuple] = matches
##         elif spec.select_distinct:
##             distinct = self.distinct_selector
##             for value_tuple in self._iter_foreach_values(spec.foreachs,
##                                                          value_dict):
##                 candidate_iterator = ifilter(where, all_nodes)
##                 matches = [ build_view_node(node, value_dict)
##                             for node in distinct(candidate_iterator) ]
##                 buckets[tuple_prefix+value_tuple] = matches
        else:
            for value_tuple in self._iter_foreach_values(spec.foreachs,
                                                         loop_value_dict):
                candidate_iterator = ifilter(having, candidates)
                matches = [ build_view_node(node, loop_value_dict)
                            for node in candidate_iterator ]
                buckets[tuple_prefix+value_tuple] = matches

    def _select_parent_nodes(self):
        "Selects nodes from the parent view and wraps them into this view."
        self._nodes = self._match_nodes(self.parents)
##         qos = self._spec.getQoSParameters()
##         if qos:
##             self._setQoSParameters(qos)

##     def _set_qos_parameters(self, parameters):
##         for node in self._nodes:
##             for attribute_name in node:
##                 for function in parameters.get(attribute_name, ()):
##                     node._set_qos(attribute_name, function)

def build_view_cascade(view_specs, viewreg, view_type=NodeView):
    "Creates the views in order of dependency and interconnects them."
    view_specs    = set(view_specs)
    view_names    = set(spec.name for spec in view_specs)

    orphant_specs = set()

    def is_known_view(view_name):
        return (view_name in view_names) or (view_name in viewreg)

    for spec in view_specs:
        known_parents = filter(is_known_view, spec.parents)
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
            known_parents = filter(is_known_view, spec.parents)
            if len(known_parents) == len(spec.parents):
                add_success = True
                views.append( view_type(spec, viewreg) )
                #known_names.add(spec.view_name)
                remaining_specs.discard(spec)
        if not add_success:
            break

    return (views, tuple(remaining_specs))


class ViewFunctions(object):
    """Provide implementations of ranking functions.
    'object_name' is the name space under which attributes are referenced.
    Each method returns a specialized list predicate that filters a list
    of objects.
    """
    def __init__(self, object_name):
        self.object_name = object_name
        self._globals    = globals()

    class __ReversedLowerEqual(object):
        __slots__ = ('item',)
        def __init__(self, item): self.item = item
        def __le__(self, other):  return other.item <= self.item

    def _select(self, key_expr, objects, count, var_values,
                distinct=False, reverse=False):
        object_name = self.object_name
        _globals    = self._globals
        val_dict    = var_values.copy()

        count = eval(count, _globals, var_values)
        if count == 0:
            return ()

        if reverse:
            comparator = self.__ReversedLowerEqual
        else:
            comparator = (lambda x:x)

        decorated_objects = []
        append_object     = decorated_objects.append
        for i, obj in enumerate(objects):
            val_dict[object_name] = obj
            append_object( (comparator(key_expr(val_dict)), i, obj) )

        if len(decorated_objects) == 0:
            return ()

        if count == 1:
            iter_result = [ min(decorated_objects) ]
        elif count < 0 or count > len(decorated_objects)//3:
            # use sort and slice the result list
            decorated_objects.sort()
            iter_result = decorated_objects
        else:
            # use heapsort if return list is short
            heapq.heapify(decorated_objects)
            iter_result = imap(heapq.heappop,
                               repeat(decorated_objects, len(decorated_objects)))

        iter_result = imap(lambda x:x[2], iter_result)

        if distinct:
            iter_result = self._hash_distinct(iter_result)

        if count > 1:
            iter_result = islice(iter_result, 0, count)

        return iter_result

    def _hash_distinct(self, iterator):
        seen_set  = set()
        have_seen = seen_set.add
        count = 0
        for item in iterator:
            have_seen(item)
            if count < len(seen_set):
                count += 1
                yield item

    def lowest(self, count, expression, distinct=False):
        return self._absolute(count, expression, distinct=distinct)

    def highest(self, count, expression, distinct=False):
        return self._absolute(count, expression, distinct=distinct, reverse=True)

    def closest(self, count, near_value, expression, distinct=False):
        return self._relative(count, near_value, expression, distinct=distinct)

    def furthest(self, count, far_value, expression, distinct=False):
        return self._relative(count, far_value, expression, distinct=distinct, reverse=True)

    def _absolute(self, count, expression,
                  distinct=False, reverse=False):
        _pyeval  = eval
        _globals = self._globals
        def evaluate(var_dict):
            return _pyeval(expression, _globals, var_dict)
        select = self._select
        def _absolute_rank(objects, var_values={}):
            return select(evaluate, objects, count, var_values,
                          distinct=distinct, reverse=reverse)

        return _absolute_rank

    def _relative(self, count, rel_value, expression,
                  distinct=False, reverse=False):
        _abs     = abs
        _pyeval  = eval
        _globals = self._globals
        try:
            rel_value = _pyeval(rel_value, _globals, {})
            constant = True
        except:
            constant = False

        if constant:
            def _eval_expression(var_values):
                return _abs(rel_value  - _pyeval(expression, _globals, var_values))
        else:
            def _eval_expression(var_values):
                return _abs(_pyeval(rel_value,  _globals, var_values) -
                            _pyeval(expression, _globals, var_values))

        select = self._select
        def _relative_rank(objects, var_values={}):
            return select(_eval_expression, objects, count, var_values,
                          distinct=distinct, reverse=reverse)

        return _relative_rank

    VALID_FUNCTIONS = frozenset(func for func in locals() if func[0] != '_')


VIEW_FUNCTIONS = ViewFunctions('node')

import sys
bind_all(sys.modules[__name__])
del sys, bind_all
