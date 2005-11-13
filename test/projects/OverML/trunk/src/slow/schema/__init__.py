import os
from os import path
from lxml.etree import tostring, parse, XMLSchema, RelaxNG, XSLT, ElementTree, XML

__all__ = ['SCHEMAS']

schema_dir = path.dirname(__file__)
schema_files = [ filename for filename in os.listdir(schema_dir)
                 if filename.endswith('.rng') or filename.endswith('.xsd')]

class RelocatableRelaxNG(object):
    _RELOCATE_ROOT_XSLT = XSLT(ElementTree(XML('''
    <xsl:stylesheet version="1.0"
         xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
         xmlns:math="http://www.w3.org/1998/Math/MathML"
         xmlns="http://relaxng.org/ns/structure/1.0">
      <xsl:param name="new_ref"/>
      <xsl:template match="start/ref"><ref name="{$new_ref}"/></xsl:template>
      <xsl:template match="text()"><xsl:value-of select="normalize-space()"/></xsl:template>
      <xsl:template match="node()">
        <xsl:copy><xsl:copy-of select="@*"/><xsl:apply-templates /></xsl:copy>
      </xsl:template>
    </xsl:stylesheet>
    ''')))
    def __init__(self, tree, start=None):
        self._tree  = tree
        self._start = start
        self.validate # initialize

    @property
    def validate(self):
        if self._start is None:
            rng_tree = self._tree
        else:
            rng_tree = self._RELOCATE_ROOT_XSLT.apply(self._tree, new_ref=self._start)
        rng = RelaxNG(rng_tree)
        self.__dict__['validate'] = rng.validate
        return rng.validate

    def copy(self, start=None):
        return self.__class__(self._tree, start)

    def relocate(self, start):
        self._start = start
        try: del self.__dict__['validate']
        except AttributeError: pass

class SchemaDict(dict):
    def __init__(self):
        dict.__init__(self)
        self.BROKEN = {}
        for filename in schema_files:
            file_path = path.join(schema_dir, filename)
            name, ext = path.splitext(filename)
            ext = ext.lower()
            try:
                tree = parse(file_path)
                if ext == 'xsd':
                    self[name] = XMLSchema(tree)
                else:
                    self[name] = RelocatableRelaxNG(tree)
            except Exception, e:
                self.BROKEN[name] = e

SCHEMAS = SchemaDict()
