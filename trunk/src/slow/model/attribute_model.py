from lxml       import etree
from lxml.etree import SubElement, Element

from xpathmodel import XPathModel, get_first
from model import NamedObject

DB_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/nala"


def buildTypes():
    return Element(u"{%s}types" % DB_NAMESPACE_URI)

def buildAttributes():
    return Element(u"{%s}attributes" % DB_NAMESPACE_URI)

def buildAttribute(attributes, attr_name, type_name, attribute_dict={}):
    return SubElement(attributes, u"{%s}attribute" % DB_NAMESPACE_URI,
                      name=attr_name, type_name=type_name, **attribute_dict)

def _bool_element(name):
    tag = u"{%s}%s" % (DB_NAMESPACE_URI, name)
    get = u"boolean(./%s)" % tag
    def set(self, _xpath_result, value):
        if _xpath_result:
            if not value:
                element = _xpath_result[0]
                element.getparent().remove(element)
        elif value:
            SubElement(self, tag)
    set.__doc__ = u"./" + tag
    return get, set


class TypeModel(XPathModel):
    DEFAULT_NAMESPACE = DB_NAMESPACE_URI
    @get_first
    def _get_type(self, type_name):
        u"./*[ @type_name = $type_name ]"
    def _del_type(self, type_name):
        u"./*[ @type_name = $type_name ]"

    def _get_type_dict(self, _xpath_result):
        u"./*[ string(@type_name) ]"
        return dict( (child.get(u"type_name"), child)
                     for child in _xpath_result)

    def _get_type_list(self):
        u"./*[ string(@type_name) ]"

    _get_type_names =u"./*/@type_name"


class AttributeClass(XPathModel):
    DEFAULT_NAMESPACE = DB_NAMESPACE_URI


class AttributeRoot(AttributeClass):
    def _get_attributes(self):
        u"./{%(DEFAULT_NAMESPACE)s}attribute"

    @get_first
    def _get_attribute(self, name):
        u"./{%(DEFAULT_NAMESPACE)s}attribute[ @name = $name ]"

    def _del_attribute(self, name):
        u"./{%(DEFAULT_NAMESPACE)s}attribute[ @name = $name ]"


class Attribute(AttributeClass):
    _val_name  = NamedObject._val_name
    _attr_name = u"./@name"

    _attr_selected  = u"bool#./@selected"
    _attr_type_name = u"./@type_name"

    _get_static,       _set_static       = _bool_element(u"static")
    _get_transferable, _set_transferable = _bool_element(u"transferable")
    _get_identifier,   _set_identifier   = _bool_element(u"identifier")


ns = etree.Namespace(DB_NAMESPACE_URI)
ns[None]          = AttributeClass
ns[u'types']      = TypeModel
ns[u'attributes'] = AttributeRoot
ns[u'attribute']  = Attribute
