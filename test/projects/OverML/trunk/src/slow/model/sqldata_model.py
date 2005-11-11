from lxml.etree import SubElement, Element, ElementBase, register_namespace_classes

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

register_namespace_classes(SQL_NAMESPACE_URI, {
    None         : SimpleType,
    u'array'     : ArrayType,
    u'composite' : CompositeType
    })


"""
class _attr_property(object):
    def __init__(self, name):
        self.name = name
    def __get__(self):
        return self.get(self.name)
    def __et__(self, value):
        self.set(self.name, value)

class SqlDataType(ElementBase):

    def __init__(self, type_name, base_type=None, option_dict=None):
        NamedObject.__init__(self, type_name)
        if base_type is None:
            base_type = type_name

##         if base_type not in self.VALID_BASE_TYPES:
##             raise ValueError, "invalid base type %s" % base_type

        self.base_type = base_type

        try:
            valid_attributes = self.VALID_ATTRIBUTES
        except AttributeError:
            valid_attributes = ()

        if option_dict:
            for attribute in option_dict:
                if attribute not in valid_attributes:
                    raise ValueError, "invalid attribute name %s" % attribute

            self.__dict__.update(option_dict)
            self.options = sorted(option_dict.keys())
        else:
            self.options = []

    def optiondict(self):
        if self.options:
            valueget = self.__dict__.get
            return dict( (name, valueget(name)) for name in self.options )
        else:
            return {}


class SimpleType(SqlDataType):
    def __init__(self, type_name, base_type, **options):
        SqlDataType.__init__(self, type_name, base_type, options)


class ContainerType(SqlDataType):
    CONTENT_VALUE_ERROR = ValueError('Invalid content type')
    def __init__(self, type_name, base_type, content, **options):
        SqlDataType.__init__(self, type_name, base_type, options)
        self.setContent(content)
    def setContent(self, content):
        self.content = content


############################################################
# Concrete Types
############################################################

from model import NamedObject, FlagContainer

class ByteArrayType(SimpleType):
    VALID_BASE_TYPES = ('bytea',)
    VALID_ATTRIBUTES = ('length',)


class BooleanType(SimpleType):
    VALID_BASE_TYPES = ('boolean',)


class NumericType(SimpleType):
    pass

class ExactNumericType(NumericType):
    VALID_BASE_TYPES = ('smallint', 'integer', 'bigint')
    BIT_PRECISION    = dict(zip(VALID_BASE_TYPES, (16, 32, 64)))
    VALID_ATTRIBUTES = ('minval', 'maxval')

class FloatNumericType(NumericType):
    VALID_BASE_TYPES = ('real', 'double')
    BIT_PRECISION    = dict(zip(VALID_BASE_TYPES, (32, 64)))

class ArbitraryNumericType(NumericType):
    VALID_BASE_TYPES = ('decimal',)
    VALID_ATTRIBUTES = ('bits',)
    
class CurrencyType(NumericType):
    VALID_BASE_TYPES = ('money',)


class TextType(SimpleType):
    pass

class VarLengthTextType(TextType):
    VALID_BASE_TYPES = ('text',)
    VALID_ATTRIBUTES = ('maxlength',)

class FixLengthTextType(TextType):
    VALID_BASE_TYPES = ('char',)
    VALID_ATTRIBUTES = ('length',)


class TimeType(SimpleType):
    pass

class TimespanType(TimeType):
    VALID_BASE_TYPES = ('interval',)

class DateType(TimeType):
    VALID_BASE_TYPES = ('date',)

class TimeType(TimeType):
    VALID_BASE_TYPES = ('time', 'timestamp')

class TimezoneTimeType(TimeType):
    VALID_BASE_TYPES = ('timetz', 'timestamptz')
    VALID_ATTRIBUTES = ('timezone',)


class NetworkType(SimpleType):
    pass

class IPAddress(NetworkType):
    VALID_BASE_TYPES = ('inet',)
    VALID_ATTRIBUTES = ('version', 'netmask')

class MacAddress(NetworkType):
    VALID_BASE_TYPES = ('macaddr',)


class ArrayType(ContainerType):
    VALID_BASE_TYPES = ('array',)
    VALID_ATTRIBUTES = ('length',)
    def setContent(self, content):
        if not isinstance(content, SqlDataType):
            raise self.CONTENT_VALUE_ERROR
        ContainerType.setContent(self, content)

class CompositeType(ContainerType):
    VALID_BASE_TYPES = ('composite',)
    def setContent(self, content):
        ContainerType.setContent(self, list(content))
    def setChild(self, pos, child):
        self.content[pos] = child
    def iterchildren(self):
        return iter(self.content)


############################################################
# Python Mapping
############################################################

class SqlDataTypes(object):
    import operator
    # build subclasses for each type
    TYPES = tuple( (base_type, type(base_type, (t,), {}))
                   for t in (t for (name, t) in globals().iteritems()
                             if isinstance(t, type) and issubclass(t, SqlDataType) \
                             and name[:1] != '_' \
                             and hasattr(t, 'VALID_BASE_TYPES') )
                   for base_type in t.VALID_BASE_TYPES )

    # may change when Composites become available
    FLAT_TYPES   = tuple(sorted((t for t in TYPES if t[0] != 'composite'),
                                key=operator.itemgetter(0)))

    SIMPLE_TYPES = tuple(t for t in FLAT_TYPES if t[0] != 'array')

    TYPE_NAMES        = sorted( t[0] for t in TYPES )
    FLAT_TYPE_NAMES   = sorted( t[0] for t in FLAT_TYPES )
    SIMPLE_TYPE_NAMES = sorted( t[0] for t in SIMPLE_TYPES )

    TYPE_DICT         = dict(TYPES)

    def __init__(self):
        self.__type_dict   = self.TYPE_DICT.copy()
        self.__descriptors = set()

    def __contains__(self, name):
        return name in self.__type_dict

    def __iter__(self):
        return iter(self.__type_dict.values())

    def copy(self):
        new_instance = type(self)()
        new_instance.__type_dict.update(self.__type_dict)
        new_instance.__descriptors = self.__descriptors.copy()
        return new_instance

    def descriptors(self):
        return self.__descriptors

    def register_descriptor(self, descriptor):
        self.__descriptors.add(descriptor)
        self.__type_dict[descriptor.name] = descriptor.type_class

    def create_descriptor(self, name, base_type=None, *args, **kwargs):
        name = str(name)
        if base_type is None:
            base_type = name

        base_class = self.__type_dict[base_type]
        descriptor = base_class(name, base_type, *args, **kwargs)

        descriptor.type_class = type(name, (base_class,), {})

        return descriptor

############################################################
# Attributes
############################################################

class SqlAttribute(NamedObject, FlagContainer):
    _FLAGS = ('static', 'transferable', 'identifier')
    def __init__(self, name=None, atype=None, selected=True,
                 static=False, transferable=True, identifier=False):
        NamedObject.__init__(self, name)
        FlagContainer.__init__(self, static, transferable, identifier)
        self._selected = selected
        if atype is None:
            self._type_name = None
        else:
            self.setTypeName(atype)

    def getSelected(self):
        return self._selected
    def setSelected(self, selected):
        self._selected = bool(selected)
    selected = property(getSelected, setSelected)

    def getTypeName(self):
        return self._type_name
    def setTypeName(self, type_name):
        self._type_name = str(type_name)
    type_name = property(getTypeName, setTypeName)


class SqlAttributeModel(NamedObject):
    INVALID_TYPE = ValueError("invalid data type requested")
    DEFAULT_DESCRIPTION = None
    __SUBCLASSES = set()
    def __init__(self, name=None, atype=None, static=False):
        NamedObject.__init__(self, name)
        self._static = static
        if atype is None:
            self._type = atype
            self._type_description = self.DEFAULT_DESCRIPTION
        else:
            self.setType(atype, self.DEFAULT_DESCRIPTION)

    def __new__(cls, atype=None):
        for class_type in cls.__SUBCLASSES:
            if atype in class_type.VALID_TYPES:
                instance = class_type()
                instance.setType(atype)
                return instance
        raise cls.INVALID_TYPE

    @classmethod
    def _add_subclass(cls, new_class):
        cls.__SUBCLASSES.add(new_class)

    @property
    def getTypeDescription(self):
        return self._type_description

    def getType(self):
        return self._type
    def setType(self, atype, description=None):
        if atype not in self.VALID_TYPES:
            raise self.INVALID_TYPE
        if description is None:
            description = self.DEFAULT_DESCRIPTION
        self._setTypeDescription(atype, description)
        self._type = atype
    atype = property(getType, setType)

    def _setTypeDescription(self, atype, description):
        self._type_description = self.DEFAULT_DESCRIPTION

class SqlSimpleAttributeModel(SqlAttributeModel):
    VALID_TYPES = SqlDataTypes.SIMPLE_TYPE_NAMES
    def _setTypeDescription(self, atype, description):
        pass

SqlAttributeModel._add_subclass(SqlSimpleAttributeModel)

class SqlArrayAttributeModel(SqlAttributeModel):
    VALID_TYPES = ('farray', 'varray')
    def _setTypeDescription(self, atype, description):
        if atype == 'farray':
            if isinstance(description, (list, tuple)):
                description = description[0]
            else:
                description = int(description or 0)
            self._type_description = [description, description]
        else:
            if isinstance(description, tuple):
                description = list(description)
            elif not isinstance(description, list):
                description = [0,0]
            self._type_description = description

    def setLength(self, min, max=None):
        self._setTypeDescription(self._type, [min, max])

SqlAttributeModel._add_subclass(SqlArrayAttributeModel)

class SqlEnumerationAttributeModel(SqlAttributeModel):
    VALID_TYPES = ('enumeration')
    def _setTypeDescription(self, atype, description):
        if isinstance(description, tuple):
            description = list(description)
        elif not isinstance(description, list):
            description = []
        self._type_description = description

    def appendValue(self, name):
        if name and name not in self._type_description:
            self._type_description.append(name)

    def removeValue(self, name):
        try: self._type_description.remove(name)
        except: pass

SqlAttributeModel._add_subclass(SqlEnumerationAttributeModel)
"""
