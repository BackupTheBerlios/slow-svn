"""MixIns and Elements for XPathModel.

All MixIns require the final class to provide the attribute
DEFAULT_NAMESPACE.
"""

import re, operator
from itertools import izip

from xpathmodel import autoconstruct

class NameError(ValueError):
    def __init__(self, name):
        if name:
            message = "invalid name: %s" % name
        else:
            message = "missing name: %s" % name
        ValueError.__init__(self, message)


class NamedObject(object):
    "MixIn for name attributes and readablename sub-elements as properties."
    _val_name  = '[a-z][_a-z0-9]*$'
    _attr_name = u"./@name"

    _get_readable_name = u"string(./{%(DEFAULT_NAMESPACE)s}readablename/text())"
    @autoconstruct
    def _set_readable_name(self, _xpath_result, name):
        u"./{%(DEFAULT_NAMESPACE)s}readablename"
        _xpath_result[0].text = name
