from lxml       import etree
from lxml.etree import Element, parse

from xpathmodel import XPathModel, autoconstruct, get_first
from model import NamedObject

SLOW_FILE_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slow"

from message_hierarchy_model  import MSG_NAMESPACE_URI
from attribute_model          import DB_NAMESPACE_URI
from slosl_model              import SLOSL_NAMESPACE_URI
from edsm_model               import EDSM_NAMESPACE_URI
from gui_model                import GUI_NAMESPACE_URI

def buildFile():
    return Element(u"{%s}file" % SLOW_FILE_NAMESPACE_URI)

def buildTypes():
    return Element(u"{%s}types" % SLOW_FILE_NAMESPACE_URI)

class FileModel(XPathModel):
    DEFAULT_NAMESPACE = SLOW_FILE_NAMESPACE_URI
    SLOSL_NAMESPACE   = SLOSL_NAMESPACE_URI
    EDSM_NAMESPACE    = EDSM_NAMESPACE_URI
    GUI_NAMESPACE     = GUI_NAMESPACE_URI
    MSG_NAMESPACE     = MSG_NAMESPACE_URI
    DB_NAMESPACE      = DB_NAMESPACE_URI

    @get_first
    @autoconstruct
    def _get_types(self):
        u"./{%(DEFAULT_NAMESPACE)s}types"

    @get_first
    @autoconstruct
    def _get_attributes(self):
        u"./{%(DB_NAMESPACE)s}attributes"

    @get_first
    @autoconstruct
    def _get_edsm(self):
        u"./{%(EDSM_NAMESPACE)s}edsm"

    @get_first
    @autoconstruct
    def _get_message_hierarchy(self):
        u"./{%(MSG_NAMESPACE)s}message_hierarchy"

    @get_first
    @autoconstruct
    def _get_statements(self):
        u"./{%(SLOSL_NAMESPACE)s}statements"

    @get_first
    @autoconstruct
    def _get_guidata(self):
        u"./{%(GUI_NAMESPACE)s}gui"


class TypeModel(XPathModel):
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


ns = etree.Namespace(SLOW_FILE_NAMESPACE_URI)
ns[u'file']  = FileModel
ns[u'types'] = TypeModel
