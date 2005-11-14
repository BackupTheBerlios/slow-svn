from itertools  import chain
from lxml       import etree
#from lxml.etree import SubElement

from xpathmodel import XPathModel
from model import NamedObject

MSG_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/msg"


def buildMessageElement(parent, node_type, **kwargs):
    tag = "{%s}%s" % (MSG_NAMESPACE_URI, node_type)
    return etree.SubElement(parent, tag, **kwargs)


class MessageHierarchyBaseClass(XPathModel):
    DEFAULT_NAMESPACE = MSG_NAMESPACE_URI

class MessageHierarchyRoot(MessageHierarchyBaseClass):
    TYPE_NAME = 'message_hierarchy'
    _get_containers = u"./{%(DEFAULT_NAMESPACE)s}container"
    _get_protocols  = u"./{%(DEFAULT_NAMESPACE)s}protocol"
    _get_headers    = u"./{%(DEFAULT_NAMESPACE)s}header"
    _get_access_names  = u"./*/@access_name"
    _get_message_names = u".//{%(DEFAULT_NAMESPACE)s}message/@type_name"


class AccessibleMixin(object):
    _val_access_name  = NamedObject._val_name
    _attr_access_name = u"./@access_name"

class MessageFieldBase(MessageHierarchyBaseClass):
    # rename property:
    _val_type_name  = NamedObject._val_name
    _attr_type_name = u"./@type_name"
    _attr_readable_name = u"./@readable_name"

class MessageFieldHierarchy(MessageFieldBase):
    _get_access_names = u"./*/@access_name"

class LinkModel(MessageFieldBase):
    pass

class MessageLinkModel(LinkModel):
    TYPE_NAME = 'message-ref'


class ContainerLinkModel(LinkModel, AccessibleMixin):
    TYPE_NAME = 'container-ref'


class ContentModel(MessageFieldBase, AccessibleMixin):
    TYPE_NAME = 'content'

class ViewDataModel(MessageFieldBase, AccessibleMixin):
    TYPE_NAME = 'viewdata'
    _attr_structured = u"bool#./@structured"
    _attr_bucket     = u"bool#./@single_bucket"
    _attr_list       = u"bool#./@list"

class ContainerModel(MessageFieldHierarchy, AccessibleMixin):
    TYPE_NAME = 'container'
    _attr_list = u"bool#./@list"

class HeaderModel(MessageFieldHierarchy, AccessibleMixin):
    TYPE_NAME = 'header'

class IPProtocolModel(MessageFieldHierarchy, AccessibleMixin):
    TYPE_NAME = 'protocol'

class MessageModel(MessageFieldHierarchy, AccessibleMixin):
    TYPE_NAME = 'message'


ns = etree.Namespace(MSG_NAMESPACE_URI)
ns.update( chain(
    ( (cls.TYPE_NAME, cls)
      for cls in globals().itervalues()
      if hasattr(cls, 'TYPE_NAME')
      ),
    [ (None, MessageHierarchyBaseClass) ]
    ))
