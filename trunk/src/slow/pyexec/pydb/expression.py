try:
    from optimize import bind_all
except:
    def bind_all(*args, **kwargs):
        pass

from itertools import *
import math

from specparser import (Attribute, Variable, Function, XRange,
                        Operator, BoolOperator, StatementElement)


class UnknownReferenceError(Exception):
    __ERROR_LINE = "Reference to unknown name %s, only (%s) %s declared."
    def __init__(self, ref, valid):
        Exception.__init__(self, self.__ERROR_LINE % (ref, ','.join(str(v) for v in valid),
                                                      ('was','were')[len(valid) > 1]))

class CompiledExpression(object):
    "A precompiled arithmetic or boolean expression."

    class Bracket(object):
        def __init__(self, bracket):
            self.bracket = bracket
        def __repr__(self):
            return self.bracket

    BEGIN_TERM = Bracket('(')
    END_TERM   = Bracket(')')
    
    __BASIC_GLOBALS = { '__builtins__' : None,   # keep other builtins away ...
                        'True'         : True,
                        'False'        : False,
                        'xrange'       : xrange,
                        }

    __allowed_builtins = ('abs', 'len', 'max', 'min')

    __supported_functions = [
        ( (mname, getattr(math, mname))          for mname in dir(math) ),
        ( (bname, __builtins__.get(bname, None)) for bname in __allowed_builtins ),
        [ ('round', (lambda val, digits=0: int(round(val,digits)))) ]
        ]

    __GLOBALS = dict( (fname,function)
                      for (fname,function) in chain(*__supported_functions)
                      if callable(function) and fname[0] != '_' )

    __valid_functions = set(__GLOBALS.keys())

    __GLOBALS.update(__BASIC_GLOBALS)

    def __init__(self, expression_tree, user_functions={}, all_functions={},
                 known_variables={}):
        """Compile a prefix term into a python expression.
        """

        if all_functions:
            self.functions = all_functions.copy()
            if user_functions:
                self.functions.update(user_functions)
        elif user_functions:
            self.functions = self.__GLOBALS.copy()
            self.functions.update(user_functions)
        else:
            self.functions = self.__GLOBALS

        # convert the expression to parenthesised infix notation
        self.expression = tuple(
            self._prefix2infix(expression_tree, known_variables)
            )

        # collect dependencies
        dependencies = self._collect_dependencies_and_compile_functions(self.expression, known_variables)
        self.__attributes = dependencies[Attribute]
        self.__variables  = dependencies[Variable]
        self.__functions  = dependencies[Function]
        self.__objects    = tuple(sorted(frozenset( attr.object_name for attr in self.__attributes )))

        if self.__variables and self.functions is self.__GLOBALS:
            # self.functions will be filled up with variable values, so copy it!
            self.functions = self.functions.copy()

        # rebuild parsed term and compile
        term = tuple( StatementElement._python_expressions_of(self.expression) )
        self.__term_string = ' '.join(term)
        self.__code = compile(self.__term_string, 'compiled_expression', 'eval')

        self.__constant = False
        self._try_to_make_constant()

    def evaluate(self, object_dict={}):
        "Evaluate the expression using the additional objects in object_dict."
        global_values = self.functions
        for var in self.__variables:
            # this changes self.functions, but it always overwrites
            # *all* variables, so there are no left overs
            global_values[var.name] = var.value
        return eval(self.__code, global_values, object_dict)

    def filter(self, object_name, objects, object_dict=None):
        """Filter objects (referenced as object_name) by evaluating the
        expression as predicate."""
        if self.__constant:
            if self.evaluate():
                for o in objects:
                    yield o
        else:
            values = self.functions.copy()
            if object_dict:
                values.update(object_dict)
            for var in self.__variables:
                values[var.name] = var.value

            expression = self.__code
            for o in objects:
                values[object_name] = o
                if eval(expression, values):
                    yield o

    def _try_to_make_constant(self):
        if self.__objects or self.__variables:
            return
        # precompute if the expression is constant
        try:
            result = self.evaluate()
            self.evaluate   = (lambda d=None : result)
            self.__constant = True
        except:
            pass

    def isConstant(self):
        return self.__constant

    def substituted(self, constant_dict):
        if not constant_dict:
            return self.__term_string

        known_variables = self.getVariableDependencies()
        term = []
        for op in self.expression:
            if isinstance(op, Attribute):
                try: op = repr(getattr(constant_dict[op.object_name], op.name))
                except (KeyError, AttributeError): pass
            elif isinstance(op, Variable):
                try: op = repr(constant_dict[op.name])
                except KeyError: pass
            elif isinstance(op, CompiledExpression):
                op = op.substituted(constant_dict)
            elif hasattr(op, 'function_parameters') and hasattr(op, 'name'):
                op = "%s ( %s )" % (op.name, ' , '.join(
                    param.substituted(constant_dict)
                    for param in op.function_parameters ))
            term.append(str(op))
        return ' '.join(term)

    def getDependencies(self):
        return tuple(sorted(self.__attributes))

    def getVariableDependencies(self):
        return tuple(self.__variables)

    def getObjectDependencies(self):
        return self.__objects

    def getFunctionDependencies(self):
        return self.__functions

    def __call__(self, *args):
        return self.evaluate(*args)

    def __hash__(self):
        return hash(self.__term_string)

    def __repr__(self):
        return self.__term_string

    def __len__(self):
        return len(self.expression)

    def __eq__(self, other):
        try:
            return self.expression == other.expression
        except AttributeError:
            if other is None:
                return False
            else:
                raise TypeError, "Incomparable types"

    def _fix_attribute(self, attribute, known_variables):
        """Morph wrongly created attributes into variables."""
        attr_object = attribute.object_name
        variable = known_variables.get(attr_object)
        if variable:
            # substitute variables for wrongly created attributes
            if str(attribute) == attr_object:
                return variable
            else:
                attribute.object_variable = variable
                return attribute
        else:
            return attribute

    def _prefix2infix(self, prefix_term, known_variables):
        """Recursive generator function to flatten the expression tree.
        Functions are cloned here in order to make their parameters
        modifiable without side effects. XRange objects are expanded."""
        if isinstance(prefix_term, Attribute):
            yield self._fix_attribute(prefix_term, known_variables)
        elif isinstance(prefix_term, Variable):
            yield known_variables[prefix_term]
        elif type(prefix_term) not in (tuple, list):
            if hasattr(prefix_term, 'clone'):
                yield prefix_term.clone()
            else:
                yield prefix_term
        elif len(prefix_term) == 0: # nothing => fine, if grammar allows it
            yield True
        elif len(prefix_term) == 1: # simple term
            for elem in self._prefix2infix(prefix_term[0], known_variables):
                yield elem
        elif len(prefix_term) == 2: # unary operator => (op sub-term)
            if not isinstance(prefix_term[0], Operator):
                raise TypeError, "Only Operator objects allowed in unary terms."
            yield self.BEGIN_TERM
            yield prefix_term[0]
            for term in self._prefix2infix(prefix_term[1], known_variables):
                yield term
            yield self.END_TERM
        else:
            #else: # binary/n-ary operator
            # convert to infix in brackets
            operator = prefix_term[0]
            b_open, b_close = self.BEGIN_TERM, self.END_TERM
            if operator == 'in' and isinstance(prefix_term[2], XRange):
                xrange_obj = prefix_term[2]
                params  = tuple( self._prefix2infix(term, known_variables)
                                 for term in xrange_obj.function_parameters )
                cmp_val = tuple( self._prefix2infix(prefix_term[1], known_variables) )
                for elem in chain( (b_open, b_open),
                                   params[0], (Operator('<='),), cmp_val,
                                   (b_close, BoolOperator('and'), b_open),
                                   cmp_val, (Operator('<'),), params[1],
                                   (b_close, b_close)
                                   ):
                    yield elem
            else:
                operators = chain((b_open,), repeat(operator))
                for term in prefix_term[1:]:
                    yield operators.next()
                    for elem in self._prefix2infix(term, known_variables):
                        yield elem
                yield b_close

    def _collect_dependencies_and_compile_functions(self, expression, known_variables):
        valid_functions = self.__valid_functions
        attributes = set()
        functions  = set()
        variables  = set()

        for elem in expression:
            if isinstance(elem, Attribute):
                attributes.add(elem)
                if elem.object_variable:
                    variables.add(elem.object_variable)
            elif isinstance(elem, Variable):
                variables.add(elem)
            elif isinstance(elem, Function):
                functions.add(elem)
                f_name = elem.name
                try:
                    function = self.functions[f_name]
                except KeyError:
                    raise UnknownReferenceError(f_name, tuple(self.functions.keys()))

                elem.setFunction(function)

            if hasattr(elem, 'function_parameters'):
                params = []
                for param in elem.function_parameters:
                    cparam = CompiledExpression(param, all_functions=self.functions,
                                                known_variables=known_variables)
                    params.append(cparam)

                    attributes.update( cparam.getDependencies() )
                    variables.update(  cparam.getVariableDependencies() )
                    functions.update(  cparam.getFunctionDependencies() )

                elem.function_parameters = tuple(params)

        return { Attribute : frozenset(attributes),
                 Function  : frozenset(functions),
                 Variable  : frozenset(variables) }


import sys
bind_all(sys.modules[__name__])
