from lxml.etree import SubElement, Element, ElementBase, Namespace

SQL_NAMESPACE_URI = u"http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/sql"

MAX_NUMERIC_BITS=256


############################################################
# Base classes
############################################################

class SqlDataType(ElementBase):
    def _is_typedef(self):
        return self.get(u'type_name', None) is not None

    def _is_typeref(self):
        return self.get(u'access_name', None) is not None

    @property
    def base_type(self):
        return self.tag.split(u'}',1)[-1]

    @property
    def attributes(self):
        return tuple(self.ATTRIBUTES[ self.base_type ])

    def __getattr__(self, name):
        return self.attrib[name]

    def __setattr__(self, name, value):
        self.attrib[name] = value


class SimpleType(SqlDataType):
    def type_precision(self):
        return self.BIT_PRECISION[ self.base_type ]

    ATTRIBUTES = {
        u'bytea'       : [u'length'],
        u'boolean'     : (),
        u'smallint'    : (u'minval', u'maxval'),
        u'integer'     : (u'minval', u'maxval'),
        u'bigint'      : (u'minval', u'maxval'),
        u'real'        : (),
        u'double'      : (),
        u'decimal'     : [u'bits'],
        u'money'       : (),
        u'text'        : (u'minlength', u'maxlength'),
        u'char'        : [u'length'],
        u'interval'    : (),
        u'date'        : (),
        u'time'        : (), 
        u'timestamp'   : (),
        u'timetz'      : [u'timezone'],
        u'timestamptz' : [u'timezone'],
        u'inet'        : (u'version', u'netmask'),
        u'macaddr'     : (),
        }

    BIT_PRECISION = {
        u'smallint' : 16,
        u'integer'  : 32,
        u'bigint'   : 64,
        u'real'     : 32,
        u'double'   : 64,
        }


class ContainerType(SqlDataType):
    ATTRIBUTES = {
        u'array'       : [u'length'],
        u'composite'   : (),
    }

class ArrayType(ContainerType):
    pass

class CompositeType(ContainerType):
    pass


SIMPLE_TYPES    = tuple(sorted( SimpleType.ATTRIBUTES.keys() ))
CONTAINER_TYPES = tuple(sorted( ContainerType.ATTRIBUTES.keys() ))

ALL_TYPES = tuple(sorted( SIMPLE_TYPES + CONTAINER_TYPES ))

ns = Namespace(SQL_NAMESPACE_URI)
ns[None]         = SimpleType
ns[u'array']     = ArrayType
ns[u'composite'] = CompositeType
