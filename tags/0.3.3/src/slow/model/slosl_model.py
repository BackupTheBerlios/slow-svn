import re, operator, os
from itertools import *

#from specparser import (BaseParser, BoolExpressionParser, ArithmeticParser,
#                        Variable, Attribute, Function)
#from model import ParsedValue, NamedObject, GenericModel


__all__ = ('RankingFunction', 'SloslStatement', 'SLOSL_NAMESPACE_URI')
    

SLOSL_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slosl"

SLOSL_NAMESPACE_DICT = {u'slosl' : SLOSL_NAMESPACE_URI}

from StringIO        import StringIO
from lxml            import etree
from lxml.etree      import ElementTree, Element, SubElement
from xpathmodel      import XPathModel, XPathModelHelper, result_filter, autoconstruct, get_first
from mathml.lmathdom import MathDOM

from slow.schema import SCHEMAS

__statements_tag = u"{%s}statements" % SLOSL_NAMESPACE_URI
def buildStatements():
    return Element(__statements_tag)

__statement_tag = u"{%s}statement"  % SLOSL_NAMESPACE_URI
def buildStatement(statements=None):
    if statements:
        element = SubElement(statements, __statement_tag)
    else:
        element = Element(__statement_tag)
    SubElement(element, u"{%s}buckets"  % SLOSL_NAMESPACE_URI)
    return element


EMPTY_MODEL = Element(__statements_tag)

SLOSL_RNG_SCHEMA = SCHEMAS['slosl']


def _build_named_attribute(name, *args):
    return XPathModelHelper._build_referenced_access(u"{%s}%s" % (SLOSL_NAMESPACE_URI, name), u'name', *args)

def _build_slosl_tree_node(name, *args):
    return XPathModelHelper._build_tree_node(u"{%s}%s" % (SLOSL_NAMESPACE_URI, name), *args)


class SloslElement(XPathModel):
    DEFAULT_NAMESPACE = SLOSL_NAMESPACE_URI


class SloslStatements(SloslElement):
    DEFAULT_ROOT_NAME=u'statements'
    DOCUMENT_SCHEMA = SLOSL_RNG_SCHEMA.copy(start=u"slosl_statements")

    _get_names = u"./{%(DEFAULT_NAMESPACE)s}statement/@name"
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

    _get_function = u"string(./@function)"
    def _set_function(self, name):
        arg_count = self.FUNCTIONS[name]
        self.set(u'function', name)

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
        return self.FUNCTIONS[ self.get(u'function') ]

    @get_first
    def _get_parameter(self, i):
        u"./{%(DEFAULT_NAMESPACE)s}parameter[$i+1]/*"
    def _set_parameter(self, _xpath_result, i, value_node):
        u"./{%(DEFAULT_NAMESPACE)s}parameter[$i+1]"
        arg_count = self.FUNCTIONS[ self.get(u'function') ]
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
    DOCUMENT_SCHEMA = SLOSL_RNG_SCHEMA.copy(start=u"slosl_statement")

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

    _del_ranked = u"./{%(DEFAULT_NAMESPACE)s}ranked"

    @result_filter(bool)
    def _get_bucket(self):
        u"./{%(DEFAULT_NAMESPACE)s}buckets[@inherit = 'true'] or not(./{%(DEFAULT_NAMESPACE)s}buckets)"
    @autoconstruct(u'.', u'{%(DEFAULT_NAMESPACE)s}buckets')
    def _set_bucket(self, _xpath_result, value):
        u"./{%(DEFAULT_NAMESPACE)s}buckets"
        node = _xpath_result[0]
        if value:
            str_val = 'true'
            node.clear()
        else:
            str_val = 'false'
        node.set(u'inherit', str_val)


ns = etree.Namespace(SLOSL_NAMESPACE_URI)
ns[None]          = SloslElement
ns[u'statements'] = SloslStatements
ns[u'statement']  = SloslStatement
ns[u'ranked']     = RankingFunction


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
