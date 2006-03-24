from itertools import *
import heapq

try:
    from psyco.classes import *
except ImportError:
    pass

try:
    from optimize import bind_all
except:
    def bind_all(*args, **kwargs):
        pass


from expression import CompiledExpression, UnknownReferenceError
from specparser import StatementParser, Variable, Operator

__all__ = ('parse_view_spec', 'UnknownReferenceError',
           'ViewSpecification', 'ViewFunctions')

def parse_view_spec(statement, user_functions={}):
    """Convenience method for parsing a single view statement
    into a ViewSpecification."""
    return ViewSpecification( StatementParser.parse(statement),
                              user_functions )


class AmbiguousNameError(Exception):
    __ERROR_LINE = "Name %s has been declared multiple times."
    def __init__(self, ref):
        Exception.__init__(self, self.__ERROR_LINE % ref)


class ViewObjectSpec(object):
    _EMPTY_SET = frozenset()
    def __init__(self, name, attribute_value_select,
                 user_functions={}, known_variables={}):
        self.name = name
        self.attributes = attributes = {}

        self.reverse_deps = reverse_deps = {}
        for (attr, value) in attribute_value_select.iteritems():
            if value:
                expr = CompiledExpression(value, user_functions=user_functions,
                                          known_variables=known_variables)
                dependencies = expr.getDependencies()
            else:
                expr = None
                dependencies = (attr,)

            attributes[attr] = expr
            for attribute in dependencies:
                deps = reverse_deps.get(attribute)
                if deps is None:
                    deps = set()
                    reverse_deps[attribute] = deps
                deps.add(attr)

    def __repr__(self):
        return "%s(%s)" % (self.name, ','.join('%s=%s' % item for item in self.attributes.iteritems()))

    def dependencies(self, parent_attr):
        return frozenset(reverse_deps.get(parent_attr, self._EMPTY_SET))

    def all_dependencies(self):
        return frozenset(chain(*self.reverse_deps.values()))


class ViewFunctions(object):
    """Provide implementations of ranking functions.
    'object_name' is the name space under which attributes are referenced.
    Each method returns a specialized list predicate that filters a list
    of objects.
    """
    __slots__ = ('object_name',)

    def __init__(self, object_name=None):
        self.object_name = object_name

    class __ReversedLowerEqual(object):
        __slots__ = ('item',)
        def __init__(self, item): self.item = item
        def __le__(self, other):  return other.item <= self.item

    def _select(self, key_expr, objects, count, var_values,
                distinct=False, reverse=False):
        object_name = self.object_name
        val_dict    = var_values.copy()

        if hasattr(count, 'evaluate'):
            count = count.evaluate(var_values)
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
            iter_result = self.hash_distinct(iter_result)

        if count > 1:
            iter_result = islice(iter_result, 0, count)

        return iter_result

    def hash_distinct(self, iterator):
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
        evaluate = expression.evaluate
        select = self._select
        def _absolute_rank(objects, var_values={}):
            return select(evaluate, objects, count, var_values,
                          distinct=distinct, reverse=reverse)

        return _absolute_rank

    def _relative(self, count, rel_value, expression,
                  distinct=False, reverse=False):
        _abs = abs
        evaluate = expression.evaluate
        if rel_value.isConstant():
            rel_value = rel_value.evaluate()
            def _eval_expression(var_values):
                return _abs(rel_value  - evaluate(var_values))
        else:
            rel_eval = rel_value.evaluate
            def _eval_expression(var_values):
                return _abs(rel_eval(var_values) - evaluate(var_values))

        select = self._select
        def _relative_rank(objects, var_values={}):
            return select(_eval_expression, objects, count, var_values,
                          distinct=distinct, reverse=reverse)

        return _relative_rank

    VALID_FUNCTIONS = frozenset(func for func in locals() if func[0] != '_')


class ViewSpecification(object):
    """This is the compiled representation of a view specification.
    View specifications are guaranteed not to interfere with each other,
    i.e. variables and options are cloned.
    """
    _view_functions = ViewFunctions
    def __init__(self, parsed_viewdef, user_functions={}, new_name=None,
                 new_parents=None, **variable_defaults):
        "Semantically check the view spec, compile it, store it."

        self.user_functions = user_functions
        self.view_name      = new_name or parsed_viewdef.view_name
        self.view_parents   = new_parents or parsed_viewdef.view_parents

        self.select_distinct = distinct = parsed_viewdef.select_distinct
        self.select_buckets  = parsed_viewdef.select_buckets

        # we create new variables here to make different specs independent
        self.loops = [ (Variable(str(var.name)), values)
                       for (var,values) in parsed_viewdef.loops ]
        self.loop_variables = [ loop[0] for loop in self.loops ]

        self.__all_known_variables = dict( (var,var) for var in self.loop_variables )

        # compile and evaluate default values of view variables
        self.variable_options = {}
        for variable in parsed_viewdef.variable_options:
            if variable in self.__all_known_variables:
                raise AmbiguousNameError, variable

            if variable.name in variable_defaults:
                value = variable_defaults[variable.name]
            elif variable.default_value:
                val_exp = CompiledExpression(variable.default_value,
                                             user_functions=user_functions,
                                             known_variables=self.__all_known_variables)
                value = val_exp.evaluate()
            else:
                value = None

            variable = Variable(variable.name, value)
            self.variable_options[variable]      = variable
            self.__all_known_variables[variable] = variable

        # build view interface
        self.view_object = ViewObjectSpec(
            self.view_name, parsed_viewdef.view_attributes,
            user_functions=user_functions,
            known_variables=self.__all_known_variables )

        self.object_select  = parsed_viewdef.object_select
        self.qos_statements = parsed_viewdef.qos_statements

        # prepare __all_attributes to collect all attribute dependencies
        self.__all_attributes = {}
        for obj in self.object_select.keys():
            if obj in self.__all_known_variables:
                # duplicate declaration!
                raise AmbiguousNameError, obj
            self.__all_attributes[obj] = set()

        # compile expression for 'where' and 'having'
        self.where_expression = CompiledExpression(
            parsed_viewdef.where_expression,
            user_functions=user_functions,
            known_variables=self.__all_known_variables
            )
        self.having_expression = CompiledExpression(
            parsed_viewdef.having_expression,
            user_functions=user_functions,
            known_variables=self.__all_known_variables
            )

        # compile expressions in object selector
        for object_name, rank_function in self.object_select.iteritems():
            if object_name in self.__all_known_variables:
                raise AmbiguousNameError, object_name
            self.__compile_rank_function(rank_function, object_name, distinct)

        # find and verify attribute names in created view and where expression
        self.__collect_attributes( self.view_object.all_dependencies() )
        self.__collect_attributes( self.where_expression.getDependencies() )

        self.__dependencies = tuple(sorted( chain(*self.__all_attributes.values()) ))

        # check dependencies of qos statements
        qos_attributes = set(chain(*[ st[1] for st in self.qos_statements ]))
        unresolved_dependencies = qos_attributes - frozenset(self.__dependencies)
        for unknown_attribute in unresolved_dependencies:
            raise UnknownReferenceError, (unknown_attribute, self.__dependencies)

        # compile and evaluate qos statements
        self.__qos_functions = {}
        for qos_function, qos_attributes in self.qos_statements:
            self.__compile_function(qos_function)
            for target_attribute in qos_attributes:
                functions = self.__qos_functions.get(target_attribute)
                if not functions:
                    functions = self.__qos_functions[target_attribute] = []
                functions.append(qos_function)

        select_string = ','.join(sorted('%s[%s]' % item for item in self.object_select.iteritems()))
        self.__hash = hash( (str(self.view_object),
                             self.select_distinct, self.select_buckets,
                             select_string, self.view_parents,
                             self.where_expression) )

    def _multi_loop_iterator(self, loops, value_dict):
        if not loops:
            yield ()
        else:
            variable, values = loops[0]
            variable_name = variable.name
            for loop_values in self._multi_loop_iterator(loops[1:], value_dict):
                for value in values:
                    if hasattr(value, 'evaluate'):
                        value = value.evaluate(value_dict)
                    variable.value = value
                    value_dict[variable_name] = value
                    yield loop_values + (value,)

    def iter_loop_variables(self, value_dict=None):
        """Builds an iterator that returns one tuple for each combination of
        values of the loop variables. It returns () if there are no loops.

        The optional dictionary argument is filled with variable-value pairs.
        Note that these must not be changed outside the iterator."""
        if value_dict is None:
            value_dict = {}
        return self._multi_loop_iterator(self.loops, value_dict)

    def __compile_rank_function(self, function, object_name, distinct):
        if function is None:
            return

        view_function_class = self._view_functions
        if function.name not in view_function_class.VALID_FUNCTIONS:
            raise UnknownReferenceError(function.name, view_function_class.VALID_FUNCTIONS)

        self.__compile_function(function)

        view_functions = view_function_class(object_name)
        build_function = getattr(view_functions, function.name)
        function.setFunction( build_function(distinct=distinct, *function.function_parameters) )

    def __compile_function(self, function):
        parameters = []
        for param in function.function_parameters:
            cparam = CompiledExpression(param, user_functions=self.user_functions,
                                        known_variables=self.__all_known_variables)
            parameters.append(cparam)
            self.__collect_attributes( cparam.getDependencies() )
        function.function_parameters = tuple(parameters)

    def __collect_attributes(self, attributes):
        "Verify that object refences have been declared."
        for attribute in attributes:
            object_name = attribute.object_name
            if object_name in self.__all_known_variables:
                continue
            object_attributes = self.__all_attributes.get(object_name, None)
            if object_attributes is None:
                raise UnknownReferenceError(object_name, self.__all_attributes.keys())
            else:
                object_attributes.add(attribute)

    def getDependencies(self):
        return self.__dependencies

    def getObjectDependencies(self):
        objects = self.__all_attributes.keys()
        objects.sort()
        return objects

    def getQoSParameters(self):
        return self.__qos_functions

    def __hash__(self):
        return self.__hash


class Bucket(dict):
    "A dictionary (of dictionaries of dictionaries ...) of lists of nodes."
    def filter_nodelists(self, filter_list, bucket=None):
        "Applies filter_list to all node lists and builds a new Bucket."
        if not isinstance(bucket, Bucket):
            if bucket is None:
                bucket = self
            else:
                return filter_list(subbucket)

        buckets = type(self)()
        for key, subbucket in bucket.iteritems():
            if isinstance(subbucket, Bucket):
                subbucket = mutate_nodelists(filter_list, subbucket)
            else:
                subbucket = filter_list(subbucket)
            buckets[key] = subbucket
        return buckets

    def filter_nodes(self, filter_node, bucket=None):
        "Specialized filter_select"
        def nodefilter(nodelist):
            return [ filter_node(node) for node in nodelist ]
        return self.filter_nodelists(nodefilter, bucket)

    def select_nodes(self, select_node, filter_node=None, bucket=None):
        "Specialized filter_select"
        if filter_node is None:
            def filter_node(node):
                return node
        def nodefilter(nodelist):
            return [ filter_node(node) for node in nodelist
                     if select_node(node) ]
        return self.filter_nodelists(nodefilter, bucket)

    def filter_select(self, select_node=None, filter_node=None,
                      filter_list=None, prefilter_list=None, bucket=None):
        "Select and filter each node and filter its list in the bucket."
        def ident(item):
            return item
        if select_node is None:
            select_node = ident
        if filter_node is None:
            filter_node = ident
        if filter_list is None:
            filter_list = list
        if prefilter_list is None:
            prefilter_list = ident

        def listfilter(nodelist):
            return filter_list( filter_node(node)
                                for node in prefilter_list(nodelist)
                                if select_node(node) )

        return self.filter_nodelists(listfilter, bucket)

    def iter_nodes(self, bucket=None):
        if not isinstance(bucket, Bucket):
            if bucket is None:
                bucket = self
            else:
                for node in bucket:
                    yield node

        for key, node_iterable in sorted(bucket.iteritems()):
            if isinstance(node_iterable, Bucket):
                node_iterable = self.iter_nodes(subbucket)
            for node in node_iterable:
                yield node

    def iter_buckets(self, stop_level=-1):
        """Returns an iterator over all node lists up to the maximum level.
        A stop_level < 0 yields all buckets.
        """
        return self._iter_buckets(stop_level)

    def _iter_buckets(self, stop_level=-1, bucket=None, keys=()):
        if bucket is None:
            bucket = self
        if level == 0:
            return ( (keys+(key,), item) for (key,item) in bucket.iteritems() )
        else:
            level -= 1
            buckets = []
            for key, entry in bucket.iteritems():
                path = keys+(key,)
                if isinstance(entry, Bucket):
                    buckets.append( self._iter_buckets(level, entry, path) )
                else:
                    buckets.append( [(path, entry)] )
            return chain(*buckets)


class BucketSelector(object):
    def __init__(self, object_name, selector):
        self.object_name   = object_name
        self.rank_function = selector.rank_function
        self.if_expr = selector.if_expr
        self.run_var, self.var_values = selector.run_var, selector.var_values

        # provide optimized implementations
        if self.if_expr: # and self.run_var: [by grammar!]
            self.__call = self._complete
        elif self.run_var:
            if self.rank_function:
                self.__call = self._for_and_rank
            else:
                self.__call = self._for_only
        elif self.rank_function:
            self.__call = self._rank_only
        else:
            self.__call = self._id

    def __call__(self, objects):
        return self.__call(objects)

    def _postrank(self, run_var, bucket):
        rank     = self.rank_function
        var_dict = {}
        def filter(matches):
            return rank(matches, var_dict)
        for key, subbucket in bucket.items():
            var_dict[run_var] = key
            bucket[key] = bucket.filter_nodelists(filter, subbucket)

    def _id(self, objects):
        "Id function, returns objects as single entry in Bucket."
        return Bucket( [(self.object_name, list(objects))] )

    def _rank_only(self, objects):
        return Bucket( [(self.object_name, self.rank_function(objects))] )

    def _for_and_rank(self, objects):
        buckets = self._for_only(objects)
        self._postrank(self.run_var, buckets)
        return buckets

    def _for_only(self, objects):
        objects = list(objects)
        run_var = str(self.run_var)

        return Bucket( (i, objects) for i in self.var_values )

    def _complete(self, objects):
        object_name = str(self.object_name)
        run_var     = str(self.run_var)
        var_values  = self.var_values

        eval_expression = self.if_expr.evaluate

        values = {}
        def node_filter(node):
            values[object_name] = node
            return eval_expression(values)

        match_buckets = Bucket()
        for i in self.var_values:
            values[run_var]  = i
            match_buckets[i] = objects.filter_nodes(node_filter)

        if self.rank_function:
            self._postrank(run_var, match_buckets)

        return match_buckets


import sys
bind_all(sys.modules[__name__])
