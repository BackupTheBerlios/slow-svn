PREF_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slow-gui-setup"

from lxml import etree
from xpathmodel import XPathModel, autoconstruct

def buildPreferences():
    prefs = etree.Element(u"{%s}prefs" % PREF_NAMESPACE_URI)
    prefs.optimize_xml_size = True
    prefs.auto_update_edsm_graph = True
    return prefs

def _build_bool_element(name):
    tag = u"{%%(DEFAULT_NAMESPACE)s}%s" % name
    get = u"./%s/@on = 'true'" % tag
    def set(self, _xpath_result, value):
        value = unicode(bool(value)).lower()
        if not _xpath_result:
            etree.SubElement(self, tag, on=value)
        else:
            _xpath_result[0].set(u"on", value)
    set.__doc__ = u"./" + tag
    return get, autoconstruct(set)

class PreferenceModel(XPathModel):
    DEFAULT_NAMESPACE = PREF_NAMESPACE_URI

    _get_optimize_xml_size, _set_optimize_xml_size = _build_bool_element(
        u"optimize_xml_size")
    _get_auto_update_edsm_graph, _set_auto_update_edsm_graph = _build_bool_element(
        u"auto_update_edsm_graph")

    def __iter__(self):
        for name, value in vars(self.__class__).iteritems():
            if isinstance(value, property):
                yield name, getattr(self, name)

etree.register_namespace_classes(PREF_NAMESPACE_URI, {
    u'prefs' : PreferenceModel,
})
