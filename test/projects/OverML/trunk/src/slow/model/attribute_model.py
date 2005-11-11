from lxml       import etree
from lxml.etree import SubElement, Element

from xpathmodel import XPathModel, get_first
from model import NamedObject

DB_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/nala"


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


etree.register_namespace_classes(DB_NAMESPACE_URI, {
    None          : AttributeClass,
    u'attributes' : AttributeRoot,
    u'attribute'  : Attribute,
    }
)
