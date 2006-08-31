GUI_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slow-gui"

from lxml import etree
from xpathmodel import XPathModel, autoconstruct, get_first
from edsm_model import EDSM_NAMESPACE_URI
from code_model import CodeContainer

class GuiDataModel(XPathModel):
    DEFAULT_NAMESPACE = GUI_NAMESPACE_URI
    def _get_pos_dict(self, _xpath_result):
        u"./{%(DEFAULT_NAMESPACE)s}pos"
        return dict( (el.ref, el.pos) for el in _xpath_result )

    def _get_pos(self, ref):
        u"./{%(DEFAULT_NAMESPACE)s}pos[ @ref = $ref ]"

    def _set_pos(self, _xpath_result, ref, x, y):
        u"./{%(DEFAULT_NAMESPACE)s}pos[ @ref = $ref ]"
        if _xpath_result:
            _xpath_result[0].pos = (x,y)
        else:
            tag = u"{%s}pos" % GUI_NAMESPACE_URI
            etree.SubElement(self, tag, ref=ref, x=str(x), y=str(y))

    def _get_test_list(self):
        u"./{%(DEFAULT_NAMESPACE)s}testcode"

    def _get_testCode(self, _xpath_result, name):
        u"./{%(DEFAULT_NAMESPACE)s}testcode[ @name = $name ]"
        if _xpath_result:
            return _xpath_result[0].code
        else:
            return ''

    def _set_testCode(self, _xpath_result, name, code):
        u"./{%(DEFAULT_NAMESPACE)s}testcode[ @name = $name ]"
        if _xpath_result:
            if code:
                _xpath_result[0].code = code
            else:
                self.remove(_xpath_result[0])
        else:
            self.buildTestCode(name, code)

    _compiled_xpath_testcode = u"./{%(DEFAULT_NAMESPACE)s}testcode[ @name = $name ]"
    def buildTestCode(self, name, code=None):
        test_case = self._compiled_xpath_testcode(self, name=name)
        if test_case:
            test_case = test_case[0]
        else:
            tag = u"{%s}testcode" % GUI_NAMESPACE_URI
            test_case = etree.SubElement(self, tag, name = name)
        if code is not None:
            test_case.code = code
        return test_case


class IconPositionModel(XPathModel):
    DEFAULT_NAMESPACE = GUI_NAMESPACE_URI
    _attr_ref = u"./@ref"

    def _get_pos(self):
        return (int(self.get('x')), int(self.get('y')))
    def _set_pos(self, pos_tuple):
        self.set(u'x', str(pos_tuple[0]))
        self.set(u'y', str(pos_tuple[1]))


class TestCodeContainer(CodeContainer):
    DEFAULT_NAMESPACE = GUI_NAMESPACE_URI
    _attr_name = u"./@name"


ns = etree.Namespace(GUI_NAMESPACE_URI)
ns[u'gui']       = GuiDataModel
ns[u'pos']       = IconPositionModel
ns[u'testcode']  = TestCodeContainer
