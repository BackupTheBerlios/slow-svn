from model import NamedObject, FlagContainer


MAX_NUMERIC_BITS=256


class XdrDataType(NamedObject):
    def __init__(self, type_name, base_type, option_dict):
        NamedObject.__init__(self, type_name)
        self.__dict__.update(option_dict)
        self.base_type = base_type
        self.options = sorted(option_dict.keys())

    def optiondict(self):
        if self.options:
            valueget = self.__dict__.get
            return dict( (name, valueget(name)) for name in self.options )
        else:
            return {}


class SimpleType(XdrDataType):
    def __init__(self, type_name, base_type, **options):
        XdrDataType.__init__(self, type_name, base_type, options)


class ContainerType(XdrDataType):
    def __init__(self, type_name, base_type, content, **options):
        XdrDataType.__init__(self, type_name, base_type, options)
        self.content = content


############################################################
# Concrete Types
############################################################

class EnumType(SimpleType):
    def __init__(self, type_name, base_type, valid_values):
        SimpleType.__init__(self, type_name, 'enumeration')
        self._valid_values = tuple(map(str, valid_values))
    def __str__(self):
        return '[%s]' % ','.join(self._valid_values)
    def __iter__(self):
        return iter(self._valid_values)


class StructType(ContainerType):
    def __init__(self, type_name, base_type, fields):
        ContainerType.__init__(self, type_name, 'structure', fields)
    def __iter__(self):
        return iter(self.content)


class UnionType(ContainerType):
    def __init__(self, type_name, base_type, fields):
        ContainerType.__init__(self, type_name, 'union', fields)


class ArrayType(ContainerType):
    def __init__(self, type_name, base_type, field_type, length=-1):
        if base_type != 'varray' and length >= 0:
            ContainerType.__init__(self, type_name, 'farray', field_type, length=length)
        else:
            ContainerType.__init__(self, type_name, 'varray', field_type)


############################################################
# Python Mapping
############################################################

class XdrDataTypes(object):
    TYPES = (
        ('boolean',     bool),
        ('char',        str),
        ('short',       int),
        ('int',         int),
        ('long',        long),
        ('float',       float),
        ('double',      float),
        ('enumeration', EnumType),
        ('structure',   StructType),
        ('string',      str),
        ('farray',      ArrayType),
        ('varray',      ArrayType),
        ('union',       UnionType),
        ('opaque',      str)
        )

    FLAT_TYPES   = tuple(t for t in TYPES
                         if t[0] not in ('structure', 'union'))
    SIMPLE_TYPES = tuple(t for t in FLAT_TYPES
                         if t[0] not in ('farray', 'varray', 'enumeration'))

    TYPE_NAMES        = [ t[0] for t in TYPES ]
    FLAT_TYPE_NAMES   = [ t[0] for t in FLAT_TYPES ]
    SIMPLE_TYPE_NAMES = [ t[0] for t in SIMPLE_TYPES ]

    TYPE_DICT         = dict(TYPES)
    XDR_TYPE_DICT     = dict( item for item in TYPES
                              if issubclass(item[1], XdrDataType) )

    @classmethod
    def create(cls, name, data):
        _type = cls.TYPE_DICT[name]
        return _type(name, None, data)

    @classmethod
    def create_descriptor(cls, name, base_type, *args, **kwargs):
        _type = cls.XDR_TYPE_DICT.get(base_type, SimpleType)
        return _type(name, base_type, *args, **kwargs)

############################################################
# Attributes
############################################################

class XdrAttribute(NamedObject, FlagContainer):
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


class XdrAttributeModel(NamedObject):
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

class XdrSimpleAttributeModel(XdrAttributeModel):
    VALID_TYPES = XdrDataTypes.SIMPLE_TYPE_NAMES
    def _setTypeDescription(self, atype, description):
        pass

XdrAttributeModel._add_subclass(XdrSimpleAttributeModel)

class XdrArrayAttributeModel(XdrAttributeModel):
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

XdrAttributeModel._add_subclass(XdrArrayAttributeModel)

class XdrEnumerationAttributeModel(XdrAttributeModel):
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

XdrAttributeModel._add_subclass(XdrEnumerationAttributeModel)
