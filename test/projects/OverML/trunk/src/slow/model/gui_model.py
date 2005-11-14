GUI_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slow-gui"

from lxml import etree
from xpathmodel import XPathModel, autoconstruct
from edsm_model import EDSM_NAMESPACE_URI

class GuiDataModel(XPathModel):
    DEFAULT_NAMESPACE = GUI_NAMESPACE_URI
    def _get_pos(self, ref):
        u"./{%(DEFAULT_NAMESPACE)s}pos[ @ref = $ref ]"

    def _get_pos_dict(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}pos"
        return dict( (el.ref, el.pos) for el in _xpath_result )

    def _set_pos(self, _xpath_result, ref, x, y):
        u"./{%(DEFAULT_NAMESPACE)s}pos[ @ref = $ref ]"
        if _xpath_result:
            _xpath_result[0].pos = (x,y)
        else:
            tag = u"{%s}pos" % GUI_NAMESPACE_URI
            etree.SubElement(self, tag, ref=ref, x=str(x), y=str(y))

class IconPositionModel(XPathModel):
    DEFAULT_NAMESPACE = GUI_NAMESPACE_URI
    _attr_ref = u"./@ref"

    def _get_pos(self):
        return (int(self.get('x')), int(self.get('y')))
    def _set_pos(self, pos_tuple):
        self.set(u'x', str(pos_tuple[0]))
        self.set(u'y', str(pos_tuple[1]))


ns = etree.Namespace(GUI_NAMESPACE_URI)
ns[u'gui'] = GuiDataModel
ns[u'pos'] = IconPositionModel
