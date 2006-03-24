'''
This module implements an XPath driven model class.

Subclasses implement methods (or string attributes) given names that
start with "_get_", "_set_" or "_del_".  These will be folded into
either properties or functions, depending on the availability of
function arguments.

A simple subclassing example might look like this::

    class Test(XPathModel):
        def _get_tvalues(self, _xpath_result):
            u"./bla2/@t"
            return [ int(a.value) for a in _xpath_result ]

        @result_filter(textnode_str_converter)
        def _get_etext(self, t):
            u"./bla2[@t = $t]/e/text()"
        def _set_etext(self, _xpath_result, t, text):
            u"./bla2[@t = $t]/e"
            self._update_node_text(_xpath_result, text)

        @result_filter(bool)
        def _get_hasE(self, t):
            u"./bla2[@t = $t]/e"

        _compiled_xpath_bla2 = u"./bla2[@t = $t]"
        def _set_t(self, t, value):
            self._update_xpath_attribute(self._compiled_xpath_bla2, u"t", unicode(value), t=t)


This example will result in a class containing the following attributes:

    1) a property "tvalues" calling "_get_tvalues". The special
    argument "_xpath_result" contains the evaluation result of the
    XPath expression in the __doc__ string of the method.

    2) two methods "getEtext(self, t)" and "setEtext(self, t, text)".
    "getEtext" calls "textnode_str_converter" with the result of the
    evaluated XPath expression in the __doc__ string of
    "_get_etext". "setEtext" essentially calls "_set_etext". As in 1),
    the "_xpath_result" argument will contain the evaluation result of
    the __doc__ string.

    3) a method "hasE(self, t)", called that way as it starts with
    "has" and a capital letter ("is" is also recognized). It behaves
    as "getEtext", but uses a different XPath expression and filters
    the result through "bool".

    4) a method "setT(self, t, value)" that calls "_set_t".

Further notes:

    * The getter method is called either if it contains the argument
    "_xpath_result" directly after "self" (which it must contain) or
    if it does not contain a __doc__ string (i.e. no XPath
    expression).

    * Instead of a method, the getter may be a simple string
    containing an XPath expression. No further result conversion is
    possible in this case.

    * Keyword arguments are commonly used to specify attribute values
    in XPath expressions.

    * Note that all XPath expressions are compiled on first class
    instantiation. This includes all class attributes starting with
    "_compiled_xpath_". You will therefore know at startup time if
    your expressions are parsable.

'''

import sys, re
from StringIO import StringIO
from itertools import chain, izip

from lxml import etree
from lxml.etree import (ElementTree, SubElement, Element, ElementBase,
                        ETXPath, XPathEvaluator, RelaxNG)
# decorators

def on_xpath(expression, namespaces=None):
    "Use this decorator to register an XPath expression for a method."
    def set_expression(function):
        function.__doc__ = expression
        function.XPATH = ETXPath(expression, namespaces)
        return function
    return set_expression

__RE_ELEMENT_NAME = re.compile('({[^}]+})?([a-zA-Z_][a-zA-Z0-9_.-]*)')

def autoconstruct(*args):
    """Decorator to auto construct an element for set() or get().
    Limited to existing parents.
    Possible arguments are:
    * autoconstruct(parent_path, element_tag [, namespace_dict])
    * autoconstruct
    The argument free version only works if set/get uses a docstring (or
    on_xpath()) XPath expression that ends with '/{ns}element' or
    '/element'.
    """
    namespaces = None
    def set_autoconstruct(function):
        try:
            parent_path, element_name = args
        except ValueError:
            try:
                xpath = function.XPATH.path
            except AttributeError:
                xpath = function.__doc__
            parent_path, element_name = xpath.rsplit('/', 1)
            parent_path = parent_path or '.'
        assert __RE_ELEMENT_NAME.match(element_name)
        function.AUTOCONSTRUCT = (parent_path, namespaces, element_name)
        return function

    if len(args) == 1 and hasattr(args[0], 'func_name'):
        # allow usage without parameters
        return set_autoconstruct(args[0])
    elif len(args) == 3:
        namespaces = args[2]
        args = args[:2]
    elif len(args) not in (0,2):
        raise ValueError, "Only 0, 2 or 3 arguments are accepted."
    return set_autoconstruct

def result_filter(converter):
    "Filter result of get() through 'converter'."
    def set_converter(method):
        try:
            method.RESULT_CONVERTERS.append(converter)
        except AttributeError:
            method.RESULT_CONVERTERS = [converter]
        return method
    return set_converter

@result_filter
def get_first(result):
    if result:
        return result[0]
    else:
        return None


def validate_relaxng(schema):
    """Register a schema that validates the node after setting the
    value. You can use it in combination with on_xpath() to specify
    the root node of the schema evaluation. Note that validation can
    only be done after executing the setter."""
    validate = RelaxNG(schema).validate
    def set_validator(function):
        try:
            xpath_eval = function.XPATH.evaluate
        except AttributeError:
            xpath_eval = lambda x:x

        def set_and_validate(self, *args, **kwargs):
            function(self, *args, **kwargs)
            if not validate( xpath_eval(self) ):
                raise ValueError, "Validation failed."
        set_and_validate.__name__ = function.__name__
        set_and_validate.__dict__ = function.__dict__
        set_and_validate.__doc__  = function.__doc__
        return set_and_validate
    return set_validator

def validate_regexp(regexp):
    """Decorator to assign regular expressions to setters that
    validate the new value before setting it."""
    match = re.compile(regexp).match
    def set_validator(function):
        def validate_and_set(*args, **kwargs):
            value = args[-1]
            if not match(value):
                raise ValueError, "Validation failed."
            function(*args, **kwargs)
        validate_and_set.__name__ = function.__name__
        validate_and_set.__dict__ = function.__dict__
        validate_and_set.__doc__  = function.__doc__
        return validate_and_set
    return set_validator


# helper functions

def disconnect_element(element):
    parent = element.getparent()
    if parent:
        parent.remove(element)


# main implementation

class AugmenterMetaClass(type):
    match_attribute_type = re.compile('([a-z][a-z0-9]*)#.').match
    
    def __new__(mcls, cls, bases, class_dict):
        complete_dict = dict(
            item for base in reversed(bases)
            for c in reversed(type.mro(base))
            for item in c.__dict__.iteritems()
            )
        complete_dict.update(class_dict)
        mcls.__augment(class_dict, complete_dict)
        return type.__new__(mcls, cls, bases, class_dict)

    @classmethod
    def __augment(mcls, class_dict, complete_dict):
        """This is where all the magic happens.
        We generate properties, getter, setter and delete methods from
        XPath driven stubs defined in the class and then remove the stubs.
        """
        getters, setters, dellers, validators = {}, {}, {}, {}
        _dict, _izip, _chain = dict, izip, chain

        xpath_namespaces = complete_dict.get('XPATH_NAMESPACES', None)

        # helper for building attribute properties from "_attr_" fields
        def attribute_access(path, validator):
            attr_type = mcls.match_attribute_type(path)
            if attr_type:
                attr_type = attr_type.group(1)
                typecast = __builtins__[attr_type]
                path = path.split('#', 1)[1]
            else:
                typecast = None

            parent_path, name = path.rsplit('@')
            if parent_path[-1:] == '/':
                parent_path = parent_path[:-1]
            if parent_path and parent_path != '.':
                xpath_eval = ETXPath(parent_path).evaluate
                def get_parent(context_node):
                    return xpath_eval(context_node)[0]
            else:
                get_parent = lambda x:x

            if attr_type == 'bool':
                def _get(self):
                    return get_parent(self).get(name) == "true"
                def _set(self, value):
                    get_parent(self).set(name, value and "true" or "false")
            elif typecast:
                def _get(self):
                    return typecast( get_parent(self).get(name) )
                def _set(self, value):
                    get_parent(self).set(name, unicode(typecast(value)))
            else:
                def _get(self):
                    return get_parent(self).get(name)
                def _set(self, value):
                    get_parent(self).set(name, value)
            if validator:
                builder = validate_regexp(validator)
                _set = builder(_set)
            return property(_get, _set, doc=(parent_path or '.') + '/@' + name)

        # collect getter, setters, etc. and compile XPath expressions in class dict
        # replace "%(...)s" references by class dictionary entries
        dicts = {'_get_':getters, '_set_':setters, '_del_':dellers, '_val_':validators}
        for name, class_attribute in complete_dict.items():
            if len(name) <= 5:
                continue
            if name[:5] in dicts:
                if class_attribute:
                    if isinstance(class_attribute, (str, unicode)):
                        class_attribute %= complete_dict
                    d = dicts[name[:5]]
                    d[name[5:]] = class_attribute
            else:
                if name.startswith('_attr_'):
                    if isinstance(class_attribute, (str, unicode)):
                        attr_name = name[6:]
                        try:
                            validator = validators[attr_name]
                        except KeyError:
                            validator = complete_dict.get('_val_'+attr_name, None)
                        class_dict[attr_name] = attribute_access(class_attribute, validator)
                elif name.startswith('_compiled_xpath_'):
                    class_dict[name] = ETXPath(class_attribute % complete_dict, xpath_namespaces)

        attribute_names = frozenset(chain(getters, setters))

        # helper functions to build getters and setters from XPath expressions
        def xpath_of(method):
            try:
                return method.XPATH
            except AttributeError:
                pass
            if method.__doc__:
                doc = method.__doc__ % complete_dict
                return ETXPath(doc, xpath_namespaces)
            else:
                return None

        RE_VARIABLE_REFERENCE = re.compile(r'\$([a-zA-Z_][:a-zA-Z0-9_.-]*)')
        def build_xpath_getter(getter, xpath_expr, argnames, converters, autoconstruct):
            evaluate  = xpath_expr.evaluate
            var_names = frozenset( RE_VARIABLE_REFERENCE.findall(xpath_expr.path) )
            auto_constructor = build_autoconstruct(autoconstruct)

            if argnames:
                def mget(self, *args, **kwargs):
                    if var_names and (args or kwargs):
                        variables = _dict( var for var in _chain(_izip(argnames, args),
                                                                 kwargs.iteritems())
                                           if var[0] in var_names )
                        xpath_result = evaluate(self, **variables)
                    else:
                        xpath_result = evaluate(self)

                    if auto_constructor and not xpath_result:
                        xpath_result = auto_constructor(self)
                    if getter:
                        xpath_result = getter(self, xpath_result, *args, **kwargs)
                    for converter in converters:
                        xpath_result = converter(xpath_result)
                    return xpath_result
            elif converters:
                def mget(self):
                    xpath_result = evaluate(self)
                    if auto_constructor and not xpath_result:
                        xpath_result = auto_constructor(self)
                    if getter:
                        xpath_result = getter(self, xpath_result)
                    for converter in converters:
                        xpath_result = converter(xpath_result)
                    return xpath_result
            elif getter:
                def mget(self):
                    xpath_result = evaluate(self)
                    if auto_constructor and not xpath_result:
                        xpath_result = auto_constructor(self)
                    return getter(self, xpath_result)
            elif auto_constructor:
                def mget(self):
                    return evaluate(self) or auto_constructor(self)
            else:
                def mget(self):
                    return evaluate(self)
            mget.__doc__ = xpath_expr.path
            return mget

        def build_converted_getter(function, converters):
            if not converters:
                return function
            elif len(converters) == 1:
                converter = converters[0]
                def new_function(*args, **kwargs):
                    return converter( function(*args, **kwargs) )
            else:
                def new_function(*args, **kwargs):
                    result = function(*args, **kwargs)
                    for converter in converters:
                        result = converter(result)
                    return result
            return new_function

        def build_autoconstruct(auto_tuple):
            if not auto_tuple:
                return None
            parent_path = ETXPath(auto_tuple[0] % complete_dict, auto_tuple[1])
            element_tag = auto_tuple[2] % complete_dict

            if element_tag[:1] != '{':
                try:
                    element_tag = "{%s}%s" % (complete_dict['DEFAULT_NAMESPACE'], element_tag)
                except KeyError:
                    pass

            evaluate = parent_path.evaluate

            def build(root_element, variables={}):
                parent = evaluate(root_element, **variables)
                if not hasattr(parent, 'getchildren'):
                    parent = parent[0] # assume node list or raise IndexException
                return [ SubElement(parent, element_tag) ]
            return build

        def build_xpath_call(setter, xpath_expr, argnames, autoconstruct):
            evaluate = xpath_expr.evaluate
            var_names = frozenset( RE_VARIABLE_REFERENCE.findall(xpath_expr.path) )
            auto_constructor = build_autoconstruct(autoconstruct)

            if var_names:
                def mset(self, *args, **kwargs):
                    if args or kwargs:
                        variables = _dict( var for var in _chain(_izip(argnames, args),
                                                                 kwargs.iteritems())
                                           if var[0] in var_names )
                        xpath_result = evaluate(self, **variables)
                    else:
                        variables = kwargs
                        xpath_result = evaluate(self)
                    if auto_constructor and not xpath_result:
                        xpath_result = auto_constructor(self, variables)

                    return setter(self, xpath_result, *args, **kwargs)
            elif auto_constructor:
                def mset(self, *args, **kwargs):
                    xpath_result = evaluate(self) or auto_constructor(self)
                    return setter(self, xpath_result, *args, **kwargs)
            else:
                def mset(self, *args, **kwargs):
                    return setter(self, evaluate(self), *args, **kwargs)
            mset.__doc__ = xpath_expr.path
            return mset

        def func_argnames(function):
            return function.func_code.co_varnames[:function.func_code.co_argcount]

        # create getters/setters/dels for each attribute name found in the class dictionary

        for name in attribute_names:
            mget = getters.get(name, None)
            mset = setters.get(name, None)
            mdel = dellers.get(name, None)

            converters = getattr(mget, 'RESULT_CONVERTERS', ())
            set_autoconstruct = getattr(mset, 'AUTOCONSTRUCT', None)
            get_autoconstruct = getattr(mget, 'AUTOCONSTRUCT', None)

            # get
            getter_call = None
            getter_argnames = ()

            if isinstance(mget, (str, unicode)):
                getter_xpath = ETXPath(mget, xpath_namespaces)
            elif mget:
                getter_argnames = func_argnames(mget)
                assert getter_argnames[0] == 'self'
                getter_argnames = getter_argnames[1:]
                getter_xpath = xpath_of( mget )
                if getter_xpath and getter_argnames[:1] == ('_xpath_result',):
                    getter_argnames = getter_argnames[1:]
                    getter_call = mget
            else:
                getter_xpath = None

            if getter_xpath:
                mget = build_xpath_getter(getter_call, getter_xpath,
                                          getter_argnames, converters, get_autoconstruct)
            elif converters:
                mget = build_converted_getter(mget, converters)

            # set
            setter_xpath = xpath_of( mset )
            if setter_xpath:
                setter_argnames = func_argnames(mset)

            if setter_xpath:
                if setter_argnames[:2] == ('self', '_xpath_result'):
                    mset = build_xpath_call(mset, setter_xpath,
                                            setter_argnames[2:], set_autoconstruct)
            # del
            def default_del(self, _xpath_result, *args, **kwargs):
                for child in reversed(_xpath_result):
                    parent = child.getparent()
                    if parent:
                        parent.remove(child)

            if isinstance(mdel, (str, unicode)):
                deller_xpath = ETXPath(mdel, xpath_namespaces)
                mdel = default_del
                deller_argnames = func_argnames(default_del)
            else:
                deller_xpath = xpath_of( mdel )
                if deller_xpath:
                    deller_argnames = func_argnames(mdel)
                    if deller_argnames[:2] == ('self', '_xpath_result'):
                        deller_argnames = deller_argnames[2:]
                    else:
                        deller_argnames = deller_argnames[1:] # (self, ...)
                        mdel = default_del

            if deller_xpath:
                mdel = build_xpath_call(mdel, deller_xpath, deller_argnames, None)

            # attach methods
            method_name = name[:1].upper() + name[1:]
            if getter_argnames:
                if name[:3] == 'has' and name[3].isupper():
                    getter_name = name
                elif name[:2] == 'is'  and name[2].isupper():
                    getter_name = name
                else:
                    getter_name = 'get%s' % method_name
                class_dict[getter_name] = mget
                class_dict['set%s' % method_name] = mset
                if mdel:
                    class_dict['del%s' % method_name] = mdel
            elif mget:
                class_dict[name] = property(mget, mset, mdel, doc=getter_xpath and getter_xpath.path or None)
            elif mset:
                class_dict['set%s' % method_name] = mset
                if mdel:
                    class_dict['del%s' % method_name] = mdel
            elif mdel:
                class_dict['del%s' % method_name] = mdel

        # setup validation for the complete model
        if 'DOCUMENT_SCHEMA_FILE' in complete_dict:
            try:
                schema_file = open(complete_dict['DOCUMENT_SCHEMA_FILE'])
                schema = schema_file.read()
                schema_file.close()
            except IOError:
                schema = None
        elif 'DOCUMENT_SCHEMA' in complete_dict:
            schema = complete_dict['DOCUMENT_SCHEMA']
        else:
            schema = None

        if schema:
            if hasattr(schema, 'validate'):
                rng_schema = schema
            else:
                relaxng_doc = etree.parse( StringIO(schema) )
                rng_schema  = etree.RelaxNG(relaxng_doc)

            def validate(self):
                return rng_schema.validate(ElementTree(self))
            class_dict['validate'] = validate


class XPathModel(ElementBase):
    __metaclass__ = AugmenterMetaClass

    def _strip(self):
        """Remove empty or unnecessary or other children/text/etc that may
        hinder validation or bloat the XML output.
        """
        for child in self:
            if hasattr(child, '_strip') and child._strip:
                child._strip()
        self._strip_text()

    def _strip_text(self):
        text = self.text
        if text and not text.strip():
            self.text = None
        tail = self.tail
        if tail and not tail.strip():
            self.tail = None

    def _evaluate(self, _xpath, _variables=None, **kwargs):
        """Evaluate an XPath expression against the root element used
        in the model.  Either a second argument (_variables) or
        keyword arguments may be specified, the first being ignored if
        keywords are present."""
        if kwargs:
            _variables = kwargs
        elif not _variables:
            return _xpath.evaluate(self)
        return _xpath.evaluate(self, **_variables)

    def _update_node_attribute(self, nodes, name, value):
        "Set a node attribute."
        # raise an exception if node is None
        if hasattr(nodes, 'getchildren'):
            nodes = (nodes,)
        for node in nodes:
            node.set(name, value)

    def _update_xpath_attribute(self, _xpath, name, value, **kwargs):
        "Set an attribute of a node matching the XPath expression."
        nodes = _xpath.evaluate(self, **kwargs)
        if nodes:
            self._update_node_attribute(nodes, name, value)
        return nodes

    def _update_node_child(self, nodes, child_tag, new_child):
        "Replace (or add) a named child of a node."
        if hasattr(nodes, 'getchildren'):
            nodes = (nodes,)

        for node in nodes:
            found = False
            for i, child in enumerate(node.getchildren()):
                if child.tag == child_tag:
                    node[i] = new_child
                    found = True
            if not found:
                node.append(new_child)

    def _update_xpath_child(self, compiled_path, child_tag, new_child, **kwargs):
        "Replace (or add) a named child of a node matching the XPath expression."
        nodes = compiled_path.evaluate(self, **kwargs)
        if nodes:
            self._update_node_child(nodes, child_tag, new_child)
        return nodes

    def _update_node_text(self, nodes, text):
        "Replace (or add) the text child of a node."
        if hasattr(nodes, 'getchildren'):
            nodes = (nodes,)

        for node in nodes:
            node.text = text
        return nodes

    def _update_xpath_text(self, compiled_path, text, **kwargs):
        "Replace (or add) the text child of a node matching the XPath expression."
        nodes = compiled_path.evaluate(self, **kwargs)
        if nodes:
            self._update_node_text(nodes, text)
        return nodes

    def _del_nodes(self, nodes):
        "Remove nodes from their parents.  Returns a list of failed nodes."
        failed = []
        for node in nodes:
            parent = node.getparent()
            if parent:
                parent.remove(node)
            else:
                failed.append(node)
        return failed

    def _del_xpath_nodes(self, compiled_path, **kwargs):
        """Remove nodes matching an XPath expression from their parents.
        Returns a list of failed nodes."""
        return self._del_nodes( compiled_path.evaluate(self, **kwargs) )

    def _find_child(self, node, child_tag):
        "Find the child of a node that has a specific name and namespace."
        for child in node.getchildren():
            if child.tag == child_tag:
                return child
        return None

    def _create_path(self, element_tags, node=None, xpath=None, **kwargs):
        """Create the nodes along a path if they do not already exist.
        Very simplistic, does not currently support attributes, etc."""
        if node is None:
            node = self
        if xpath:
            node = xpath.evaluate(node, kwargs)

        for tag in element_tags:
            new_node = self._find_child(node, tag)
            if new_node is None:
                new_node = Element(tag)
                node.append(new_node)
            node = new_node
        return node

    def _create_element(self, _tag_name, **attributes):
        if _tag_name[:1] != '{':
            try:
                _tag_name = "{%s}%s" % (self.DEFAULT_NAMESPACE, _tag_name)
            except AttributeError:
                pass

        return Element(_tag_name, attributes)

    def _print(self, out=None, encoding='UTF-8'):
        ElementTree(self).write(out or sys.stdout, encoding)

    def _pretty_print(self, out=None, encoding='UTF-8'):
        PrettyPrint(self, out or sys.stdout, encoding)
    _pretty_print = _print # PrettyPrint is not supported by lxml


class XPathModelHelper(object):
    _RE_NAMESPACE = re.compile(r'\{([^\}]+)}')
    @staticmethod
    def _build_referenced_access(el_name, ref_attribute, parent_expression=""):
        xpath_all = u".%s/%s" % (parent_expression, el_name)
        xpath_set = u"(%s[@%s = $ref])[1]" % (xpath_all, ref_attribute)
        xpath_get = xpath_set + u"/*"

        @get_first
        def _get_one(self, ref):
            pass
        _get_one.__doc__ = xpath_get

        _del_one = xpath_get

        @autoconstruct('.'+parent_expression, el_name)
        def _set_one(self, _xpath_result, ref, value_node):
            node = _xpath_result[0]
            node.set(ref_attribute, ref)
            node.text = None
            node[:] = value_node and [value_node] or []
        _set_one.__doc__ = xpath_set

        def _get_all(self, _xpath_result):
            return [ (e.get(ref_attribute), len(e) and e[0] or None) for e in _xpath_result ]
        _get_all.__doc__ = xpath_all

        def _del_all(self, _xpath_result):
            for child in _xpath_result:
                parent = child.getparent()
                if parent:
                    parent.remove(child)
        _del_all.__doc__ = xpath_all

        return (_get_one, _set_one, _del_one, _get_all, _del_all)

    @staticmethod
    def _build_tree_node(el_tag, parent_expression=""):
        xpath_set = u".%s/%s[1]" % (parent_expression, el_tag)
        xpath_get = xpath_set + u"/*"

        @get_first
        def mget(self):
            pass
        mget.__doc__ = xpath_get

        @autoconstruct('.'+parent_expression, el_tag)
        def mset(self, _xpath_result, value_node):
            node = _xpath_result[0]
            node.text = None
            node[:] = value_node and [value_node] or []
        mset.__doc__ = xpath_set

        def mdel(self, _xpath_result):
            for child in _xpath_result:
                parent = child.getparent()
                if parent:
                    parent.remove(child)
        mdel.__doc__ = xpath_get

        return mget, mset, mdel


# CLEAN UP
#del _augment_class


# TEST in __main__
if __name__ == '__main__':
    xml_data = u'''<?xml version="1.0" encoding="UTF-8" ?>
    <bla1 myattrib="juhu">
      <bla2 t="1">
        <e />
      </bla2>
      <bla2 t="2">
        <e>text2</e>
      </bla2>
      <bla2 t="3">
        <e>text3</e>
      </bla2>
      <bla2 t="5" />
    </bla1>
    '''

    schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0" datatypeLibrary="http://www.w3.org/2001/XMLSchema-datatypes">
  <start>
    <ref name="bla1"/>
  </start>
  <define name="bla1">
    <element name="bla1">
      <attribute name="myattrib" />
      <zeroOrMore>
        <ref name="bla2"/>
      </zeroOrMore>
    </element>
  </define>
  <define name="bla2">
    <element name="bla2">
      <attribute name="t">
        <data type="integer"/>
      </attribute>
      <optional>
        <element name="e">
          <text/>
        </element>
      </optional>
    </element>
  </define>
</grammar>
        '''

    class Test(XPathModel):
        DOCUMENT_SCHEMA = schema # -> validate()

        _attr_myattrib = u"./@myattrib"

        @on_xpath(u"./bla2/@t")
        def _get_tvalues(self, _xpath_result):
            return [ int(a) for a in _xpath_result ]

        def _get_etext(self, t):
            u"string(./bla2[@t = $t]/e/text()[1])"
        _get_etexts = u"./bla2/e/text()"
        @autoconstruct
        def _set_etext(self, _xpath_result, t, text):
            u"./bla2[@t = $t]/e"
            self._update_node_text(_xpath_result, text)

        @result_filter(bool)
        def _get_hasE(self, t):
            u"./bla2[@t = $t]/e"

        _compiled_xpath_bla2 = u"./bla2[@t = $t]"
        def _set_t(self, t, value):
            self._update_xpath_attribute(self._compiled_xpath_bla2, u't', unicode(value), t=t)

    ns = etree.Namespace(None)
    ns['bla1'] = Test

    tree = ElementTree(file=StringIO(xml_data))
    #print dir(tree)
    tree.write(sys.stdout)
    print

    bla1 = tree.getroot()

    print bla1.validate() and "Valid document!" or "Non valid document!"

    max_t = max(bla1.tvalues)

    def print_e():
        print "Text of e element for t=(1..%d): " % max_t,
        for t in range(1,max_t+1):
            print "%5d:%10s" % (t, bla1.getEtext(t=t)),
        print

    print_e()

    print "myattrib (1):", bla1.myattrib
    bla1.myattrib = u"juhu2"
    print "myattrib (2):", bla1.myattrib

    print "Has e element for t=(1..%d):     " % max_t,
    for t in range(1,max_t+1):
        print "%5d:%10s" % (t, bla1.hasE(t=t)),
    print

    print "Changing text for t=1"
    bla1.setEtext(1, u'newtext')
    print_e()

    print "Changing t for t=3"
    bla1.setT(3, 4)
    print_e()

    print "Changing text for t=5"
    bla1.setEtext(5, u'newertext')
    print_e()

    print "All texts:", bla1.etexts

    print
    print "XML:"
    tree.write(sys.stdout)
    print
