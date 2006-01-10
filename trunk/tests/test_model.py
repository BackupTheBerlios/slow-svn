from tests import run_testsuites

import unittest, time
from StringIO import StringIO

from lxml import etree

from slow.model.xpathmodel import XPathModel, autoconstruct, result_filter, on_xpath


class XPathModelTestCase(unittest.TestCase):
    def setUp(self):
        self.namespaces = []

    def tearDown(self):
        for namespace in self.namespaces:
            try: etree.Namespace(namespace).clear()
            except: pass

    def _setup_test(self, cls, xml, namespace=None):
        class_name = cls.__name__
        self.namespaces.append(namespace)
        etree.Namespace(namespace)[class_name] = cls
        tree = etree.parse(StringIO(xml))
        return tree, tree.getroot()

    def _tostring(self, element):
        try:
            element = element.getroot()
        except AttributeError:
            pass
        return etree.tostring(element)

    def test_attr(self):
        class test(XPathModel):
            _attr_myattrib = u"./@myattrib"

        tree, test = self._setup_test(test, u'<test myattrib="hui" />')

        self.assertEqual(test.myattrib, u"hui")
        test.myattrib = u"pfui"
        self.assertEqual(test.myattrib, u"pfui")

        self.assertEqual(self._tostring(tree), u'<test myattrib="pfui"/>')

    def test_onxpath(self):
        class test(XPathModel):
            @on_xpath(u"./bla/@t")
            def _get_tvalues(self, _xpath_result):
                return map(int, _xpath_result)

        tree, test = self._setup_test(test, u'<test><bla t="1"/><bla t="2"/></test>')
        self.assertEqual(sorted(test.tvalues), [1,2])

    def test_autoconstruct(self):
        class test(XPathModel):
            def _get_etext(self, t):
                u"string(./bla[@t = $t]/e/text()[1])"
            _get_etexts = u"./bla/e/text()"
            @autoconstruct
            def _set_etext(self, _xpath_result, t, text):
                u"./bla[@t = $t]/e"
                self._update_node_text(_xpath_result, text)

        tree, test = self._setup_test(test, u'<test><bla t="1"/><bla t="2"/></test>')
        test.setEtext(1, u"t1")
        self.assertEqual(test.getEtext(1), u"t1")
        self.assertEqual(test.getEtext(2), '')
        self.assertEqual(test.getEtext(3), '')

        test.setEtext(2, u"t2")
        self.assertEqual(test.getEtext(1), u"t1")
        self.assertEqual(test.getEtext(2), u"t2")
        self.assertEqual(test.getEtext(3), '')

        self.assertRaises(IndexError, test.setEtext, 3, u"t3")
        self.assertEquals(self._tostring(tree), u'<test><bla t="1"><e>t1</e></bla><bla t="2"><e>t2</e></bla></test>')

    def test_filter(self):
        class test(XPathModel):
            @result_filter(bool)
            def _get_hasE(self, t):
                u"./bla[@t = $t]/e"

        tree, test = self._setup_test(test, u'<test><bla t="1"><e/></bla><bla t="2"/></test>')
        self.assert_(test.hasE(1) is True)
        self.assert_(test.hasE(2) is False)
        self.assert_(test.hasE(3) is False)

    def test_compiled_path(self):
        class test(XPathModel):
            _compiled_xpath_bla = u"./bla[@t = $t]/@t"
            def _get_t(self, t):
                return int( self._compiled_xpath_bla.evaluate(self, t=t)[0] )

        tree, test = self._setup_test(test, u'<test><bla t="1"/><bla t="2"/></test>')
        self.assertEquals(test.getT(1), 1)
        self.assertEquals(test.getT(2), 2)
        self.assertRaises(IndexError, test.getT, 3)

    def test_default_ns(self):
        class test(XPathModel):
            DEFAULT_NAMESPACE=u"test_ns"
            _compiled_xpath_bla = u"./{%(DEFAULT_NAMESPACE)s}bla[@t = $t]/@t"
            def _get_t1(self, t):
                return self._compiled_xpath_bla.evaluate(self, t=t)
            def _get_t2(self, t):
                u"./{%(DEFAULT_NAMESPACE)s}bla[@t = $t]/@t"

        tree, test = self._setup_test(test, u'<test><ns:bla xmlns:ns="test_ns" t="1"/><bla t="2"/></test>')

        self.assertEquals(test.getT1(1), ["1"])
        self.assertEquals(test.getT2(1), ["1"])

        self.assertEquals(test.getT1(2), [])
        self.assertEquals(test.getT2(2), [])

    def test_update_xpath_attribute(self):
        class test(XPathModel):
            _compiled_xpath_bla2 = u"./bla[@t = $t]"
            def _set_t(self, t, value):
                self._update_xpath_attribute(self._compiled_xpath_bla2, u't', unicode(value), t=t)

        tree, test = self._setup_test(test, u'<test><bla t="1"/><bla t="2"/></test>')
        test.setT(2, 3)
        self.assertEquals(self._tostring(tree), u'<test><bla t="1"/><bla t="3"/></test>')


if __name__ == "__main__":
    run_testsuites( globals().values() )
