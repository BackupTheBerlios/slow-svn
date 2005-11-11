import re, operator, os
from itertools import *

#from specparser import (BaseParser, BoolExpressionParser, ArithmeticParser,
#                        Variable, Attribute, Function)
#from model import ParsedValue, NamedObject, GenericModel


__all__ = ('RankingFunction', 'SloslStatement', 'SLOSL_NAMESPACE_URI')
    

SLOSL_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slosl"
SLOSL_RNG = os.path.join(os.path.dirname(__file__), "..", "schema", "slosl.m.rng")

SLOSL_NAMESPACE_DICT = {u'slosl' : SLOSL_NAMESPACE_URI}

from StringIO        import StringIO
from lxml            import etree
from lxml.etree      import ElementTree, Element, SubElement
from xpathmodel      import XPathModel, XPathModelHelper, result_filter, autoconstruct, get_first
from mathml.lmathdom import MathDOM


__statements_tag = u"{%s}statements" % SLOSL_NAMESPACE_URI
def buildStatements():
    return Element(__statements_tag)

__statement_tag = u"{%s}statement"  % SLOSL_NAMESPACE_URI
def buildStatement(statements=None):
    if statements:
        return SubElement(statements, __statement_tag)
    else:
        return Element(__statement_tag)


EMPTY_MODEL = Element(__statements_tag)

__schema = open(SLOSL_RNG, 'r')
SLOSL_RNG_SCHEMA = unicode(__schema.read(), 'UTF-8')
__schema.close()
del __schema

_RE_GRAMMAR = re.compile(r'(<grammar[^>]*>)')
_GRAMMAR_START = r'\1<start><ref name="%s"/></start>'


def _build_named_attribute(name, *args):
    return XPathModelHelper._build_referenced_access(u"{%s}%s" % (SLOSL_NAMESPACE_URI, name), u'name', *args)

def _build_slosl_tree_node(name, *args):
    return XPathModelHelper._build_tree_node(u"{%s}%s" % (SLOSL_NAMESPACE_URI, name), *args)


class SloslElement(XPathModel):
    DEFAULT_NAMESPACE = SLOSL_NAMESPACE_URI


class SloslStatements(SloslElement):
    DEFAULT_ROOT_NAME=u'statements'
    DOCUMENT_SCHEMA = _RE_GRAMMAR.sub(_GRAMMAR_START % u"slosl_statements", SLOSL_RNG_SCHEMA, 1)

    _get_names = u"./slosl:statement/@name"
    def _get_statements(self):
        u"./{%(DEFAULT_NAMESPACE)s}statement"

    def _get_statement(self, _xpath_result, name):
        u"./{%(DEFAULT_NAMESPACE)s}statement[@name = $name]"
        if _xpath_result:
           node = _xpath_result[0]
        else:
            node = SubElement(self, u'{%s}statement' % SLOSL_NAMESPACE_URI, name=name)
        return node

    def _set_statement(self, _xpath_result, name, statement):
        u"./{%(DEFAULT_NAMESPACE)s}statement[@name = $name]"
        if statement.tag != u'{%s}statement' % SLOSL_NAMESPACE_URI:
            raise ValueError, "Invalid statement element."

        for old_node in _xpath_result:
            self.remove(old_node)
        self.append(statement)

    def _del_statement(self, name):
        u"./{%(DEFAULT_NAMESPACE)s}statement[@name = $name]"

    def _strip(self):
        for statement in self.statements:
            if not statement.name:
                self.remove(statement)
            else:
                statement._strip()


class RankingFunction(SloslElement):
    DEFAULT_ROOT_NAME=u'ranked'
    FUNCTIONS = {
        'lowest'  : 2,
        'highest' : 2,
        'closest' : 3,
        'furthest': 3
        }

    _get_function = u"string(./@name)"
    def _set_function(self, name):
        arg_count = self.FUNCTIONS[name]
        self.set(u'name', name)

        while len(self) < arg_count:
            SubElement(self, u'{%s}parameter' % SLOSL_NAMESPACE_URI)
        while len(self) > arg_count:
            del self[-1]

    _get_name, _set_name = _get_function, _set_function

    _get_parameterCount = u"count(./{%(DEFAULT_NAMESPACE)s}parameter)"
    def _get_parameters(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}parameter/*"
        return _xpath_result

    def function_parameter_count(self):
        return self.FUNCTIONS[ self.get(u'name') ]

    @get_first
    def _get_parameter(self, i):
        u"./{%(DEFAULT_NAMESPACE)s}parameter[$i+1]/*"
    def _set_parameter(self, _xpath_result, i, value_node):
        u"./{%(DEFAULT_NAMESPACE)s}parameter[$i+1]"
        arg_count = self.FUNCTIONS[ self.get(u'name') ]
        if _xpath_result:
            parent = _xpath_result[0]
        elif i < arg_count:
            while len(self) <= i:
                parent = SubElement(self, u'{%s}parameter' % SLOSL_NAMESPACE_URI)
        else:
            raise IndexError, "Maximum %s parameters allowed." % arg_count
        parent.clear()
        parent.append(value_node)


class SloslStatement(SloslElement):
    DEFAULT_ROOT_NAME = u'statement'
    DOCUMENT_SCHEMA = _RE_GRAMMAR.sub(_GRAMMAR_START % u"slosl_statement", SLOSL_RNG_SCHEMA, 1)

    _get_where,  _set_where,  _del_where  = _build_slosl_tree_node(u'where')
    _get_having, _set_having, _del_having = _build_slosl_tree_node(u'having')

    (_get_select,   _set_select, _del_select,
     _get_selects,  _del_selects)  = _build_named_attribute(u'select')
    (_get_with,     _set_with, _del_with,
     _get_withs,    _del_withs)    = _build_named_attribute(u'with')
    (_get_foreach,  _set_foreach, _del_foreach,
     _get_foreachs, _del_foreachs) = _build_named_attribute(u'foreach', u'/{%s}buckets' % SLOSL_NAMESPACE_URI)

    _get_view = u"string(./@name)"
    def _set_view(self, name):
        self.set(u'name', name)

    _get_name, _set_name = _get_view, _set_view

    _attr_selected = u"bool#./@selected"

    def _set_parent(self, _xpath_result, parent):
        u"./{%(DEFAULT_NAMESPACE)s}parent[string(.) = normalize-space($parent)]"
        if not _xpath_result:
            node = SubElement(self, u'{%s}parent' % SLOSL_NAMESPACE_URI)
            node.text = parent.strip()
    def _get_parents(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}parent/text()"
        return map(unicode, _xpath_result)
    def _set_parents(self, parent_list):
        parent_list = [ name.strip() for name in parent_list ]
        parent_tag = u'{%s}parent' % SLOSL_NAMESPACE_URI
        for child in self[:]:
            if child.tag == parent_tag:
                name = child.text
                try:
                    parent_list.remove(name)
                except ValueError:
                    self.remove(child)

        for name in parent_list:
            child = SubElement(self, parent_tag)
            child.text = name

    _del_parents = u"./{%(DEFAULT_NAMESPACE)s}parent"

    @get_first
    @autoconstruct(u'.', u'{%s}ranked' % SLOSL_NAMESPACE_URI)
    def _get_ranked(self):
        u"./{%(DEFAULT_NAMESPACE)s}ranked"

    @result_filter(bool)
    def _get_bucket(self):
        u"./{%(DEFAULT_NAMESPACE)s}buckets[@bucket = 'true'] or not(./{%(DEFAULT_NAMESPACE)s}buckets)"
    @autoconstruct(u'.', u'{%(DEFAULT_NAMESPACE)s}buckets')
    def _set_bucket(self, _xpath_result, value):
        u"./{%(DEFAULT_NAMESPACE)s}buckets"
        node = _xpath_result[0]
        if value:
            str_val = 'true'
            node.clear()
        else:
            str_val = 'false'
        node.set(u'bucket', str_val)


etree.register_namespace_classes(SLOSL_NAMESPACE_URI, {
    None          : SloslElement,
    u'statements' : SloslStatements,
    u'statement'  : SloslStatement,
    u'ranked'     : RankingFunction
    }
)

if __name__ == '__main__':
    from mathml import MATHML_NAMESPACE_URI
    slosl_xml = u'''
  <slosl:statements xmlns:slosl="%s" xmlns:m="%s">
    <slosl:statement name="chord_last_neighbour" selected="true">
      <slosl:select name="id"><m:ci>node.id</m:ci></slosl:select>
      <slosl:select name="local_dist"><m:ci>node.local_dist</m:ci></slosl:select>
      <slosl:parent>chord_neighbours</slosl:parent>
      <slosl:ranked function="highest">
        <slosl:parameter><m:cn type="integer">1</m:cn></slosl:parameter>
        <slosl:parameter><m:ci>node.local_dist</m:ci></slosl:parameter>
      </slosl:ranked>
      <slosl:where>
        <m:apply><m:eq/><m:ci>node.side</m:ci><m:cn type="integer">1</m:cn></m:apply>
      </slosl:where>
      <slosl:buckets inherit="true"/>
    </slosl:statement>

    <slosl:statement name="chord_fingertable" selected="true">
      <slosl:select name="id"><m:ci>node.id</m:ci></slosl:select>
      <slosl:parent>db</slosl:parent>
      <slosl:ranked function="highest">
        <slosl:parameter><m:cn type="integer">1</m:cn></slosl:parameter>
        <slosl:parameter><m:ci>node.id</m:ci></slosl:parameter>
      </slosl:ranked>
      <slosl:with name="log_k"><m:cn type="integer">160</m:cn></slosl:with>
      <slosl:with name="max_id">
        <m:apply><m:power/><m:cn type="integer">2</m:cn><m:ci>log_k</m:ci></m:apply>
      </slosl:with>
      <slosl:where>
        <m:apply><m:and/><m:apply><m:eq/><m:ci>node.knows_chord</m:ci><m:true/></m:apply><m:apply><m:eq/><m:ci>node.alive</m:ci><m:true/></m:apply></m:apply>
      </slosl:where>
      <slosl:having>
        <m:apply><m:in/><m:ci>node.id</m:ci><m:list><m:apply><m:power/><m:cn type="integer">2</m:cn><m:ci>i</m:ci></m:apply><m:apply><m:power/><m:cn>2</m:cn><m:apply><m:plus/><m:ci>i</m:ci><m:cn type="integer">1</m:cn></m:apply></m:apply></m:list></m:apply>
      </slosl:having>
      <slosl:buckets>
        <slosl:foreach name="i">
          <m:interval closure="closed-open"><m:cn type="integer">0</m:cn><m:ci>log_k</m:ci></m:interval>
        </slosl:foreach>
      </slosl:buckets>
    </slosl:statement>
  </slosl:statements>
''' % (SLOSL_NAMESPACE_URI, MATHML_NAMESPACE_URI)

    doc = ElementTree(file=StringIO(slosl_xml))

    import sys
    statements = doc.getroot()
    statements._pretty_print()

    print
    print statements.validate() and "Valid" or "Invalid"

"""
class VariableDeclaration(NamedObject, ParsedValue):
    PARSER = BaseParser.p_any_list
    def __init__(self, name=None, values=None):
        NamedObject.__init__(self, name)
        ParsedValue.__init__(self)
        if values is not None:
            self.setDeclaration(values)

    def validate(self, maybe_none=False):
        return ParsedValue.validate(self, maybe_none) and \
               NamedObject.validate(self, maybe_none)
    def __repr__(self):
        return "%s: %s" % (self._name, self._declaration)

    def getDeclaration(self):
        return self._value
    def setDeclaration(self, declaration):
        self._parse(declaration)
    declaration = property(getDeclaration, setDeclaration)

    @property
    def parsed_declaration(self):
        return self._parsed

class AssignableName(NamedObject, ParsedValue):
    PARSER = ArithmeticParser.p_arithmetic_exp
    def __init__(self, name=None, value=None):
        NamedObject.__init__(self, name)
        ParsedValue.__init__(self, value)

    def validate(self, maybe_none=False):
        return NamedObject.validate(self, maybe_none) and \
               (self._value is not None or maybe_none)
    def __repr__(self):
        if self._value is None:
            return self._name
        else:
            return "%s = %s" % (self._name, self._value)

    def getValue(self):
        return self._value
    def setValue(self, value):
        self._value = value
    value = property(getValue, setValue)

class AssignableAttribute(AssignableName):
    pass

class AssignableOption(AssignableName):
    pass


class FunctionParameter(ParsedValue):
    PARSER = ArithmeticParser.p_arithmetic_exp

class RankingFunction(NamedObject):
    VALID_FUNCTIONS = ('lowest', 'highest', 'closest', 'furthest')
    PARAMETER_COUNT = dict(zip(VALID_FUNCTIONS, (2,2,3,3)))
    def __init__(self, name=None, params=None):
        self._param_count = 0
        NamedObject.__init__(self, name)
        if params is not None:
            self.setParameters(*params)
        else:
            self._params = (None,)*3

    def validate(self, maybe_none=False):
        return NamedObject.validate(self, maybe_none) and \
               maybe_none or not [ p for p in self.getParameters() if p is not None ]
    def __repr__(self):
        return "%s(%s)" % (self._name, ', '.join(imap(str, self._params)))

    def _acceptsName(self, name):
        return name in self.VALID_FUNCTIONS
    def _setName(self, name):
        self._name, self._param_count = name, self.PARAMETER_COUNT[name]

    def setParameters(self, param1, param2, param3=None):
        if self._param_count < 3:
            param3 = None
        self._params = tuple(imap(FunctionParameter,
                                  (param1, param2, param3)))
    def getParameters(self):
        return tuple(p._value for p in islice(self._params, self._param_count))
    parameters = property(getParameters, setParameters)


class Expression(ParsedValue):
    def __init__(self, expression=None):
        ParsedValue.__init__(self, expression)
        self._expression = expression

    def getExpression(self):
        return self._expression
    def setExpression(self, expression):
        self._parse(expression)
        self._expression = expression
    expression = property(getExpression, setExpression)

    @property
    def parsed_expression(self):
        return self._parsed


class ArithmeticExpression(Expression):
    PARSER = ArithmeticParser.p_arithmetic_exp

class BooleanExpression(Expression):
    PARSER = BoolExpressionParser.p_bool_exp


class SloslStatement(GenericModel):
    _TYPE_MAPPING = {
        'view'        : NamedObject,
        'select'      : {'name' : AssignableAttribute},
        'from'        : {'name' : NamedObject},
        'with'        : {'name' : AssignableAttribute},
        'ranked'      : RankingFunction,
        'where'       : BooleanExpression,
        'having'      : BooleanExpression,
        'foreach'     : {'name' : VariableDeclaration},
        'bucket'      : bool,
        'selected'    : bool,
        'distinct'    : bool
        }

    @property
    def name(self):
        name = self._view
        if name:
            return str(name)
        else:
            return ''

    @property
    def attribute_dependencies(self):
        return [ a for a in self.dependencies
                 if isinstance(a, Attribute) ]

    @property
    def variable_dependencies(self):
        return [ v for v in self.dependencies
                 if isinstance(v, Variable) ]

    @property
    def function_dependencies(self):
        return [ f for f in self.dependencies
                 if isinstance(f, Function) ]

    @property
    def dependencies(self):
        expressions = (
            expression.parsed_value
            for expression in chain(self.iterselect(), self.iterwith(),
                                    self.iterforeach(),
                                    (self.where, self.having))
            if hasattr(expression, 'parsed_value')
            )

        rank_function = self.ranked
        if rank_function:
            rank_params = rank_function.parameters
        else:
            rank_params = ()

        return frozenset(chain(*map(self._find_symbols,
                                    chain(rank_params, expressions))))

    def _find_symbols(self, parsed_expression):
        if not parsed_expression:
            return ()
        symbols = set()
        for elem in parsed_expression:
            if isinstance(elem, (tuple, list)):
                symbols.update(imap(self._find_symbols, elem))
            elif isinstance(elem, (Variable, Attribute)):
                symbols.add(elem)
            elif isinstance(elem, Function):
                symbols.add(elem)
                symbols.update(imap(self._find_symbols, elem.function_parameters))
        return symbols

    def validate(self):
        for name in self._TYPE_MAPPING.iterkeys():
            value = getattr(self, name, None)
            validate = getattr(value, 'validate', None)
            maybe_none = name not in ('view', 'select', 'from')
            if validate and not validate(maybe_none):
                return False
        return True

    def __repr__(self):
        return '\n'.join( "%s %r" % (name, getattr(self, name))
                          for name in self._TYPE_MAPPING.iterkeys() )

"""
