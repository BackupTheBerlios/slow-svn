import zlib, base64

from xpathmodel import XPathModel, autoconstruct, validate_regexp

_RE_CLASSNAME  = r"[a-zA-Z][a-zA-Z0-9_]*"
_RE_METHODNAME = _RE_CLASSNAME

class CodeContainer(XPathModel):
    "Code blocks as sub-elements."
    DEFAULT_NAMESPACE=u"local"

    _attr_language = u"./@language"

    _attr_code_type = u"./@type"
    _val_code_type  = u"exec|eval"

    def _get_code(self, _xpath_result):
        u"string(./text())"
        if _xpath_result:
            return zlib.decompress( base64.b64decode(_xpath_result) )
        else:
            return u''
    def _set_code(self, code):
        if code:
            self.text = base64.b64encode( zlib.compress(code, 9) )
        else:
            self.text = None

    @property
    def compiled_code(self):
        if self.language != 'python':
            self._compiled_code = None
            return None
        if hasattr(self, '_compiled_code') and self._compiled_code:
            return self._compiled_code
        else:
            code = self.code
            if code:
                ccode = self._compiled_code = compile(code, '<string>', self.code_type or 'exec')
                return ccode
            else:
                return None

    _get_class_name = u"string(./@classname)"
    @validate_regexp(_RE_CLASSNAME)
    def _set_class_name(self, name):
        self.set(u"classname", name)

    _get_method_name = u"string(./@methodname)"
    @validate_regexp(_RE_METHODNAME)
    def _set_method_name(self, name):
        self.set(u"methodname", name)
