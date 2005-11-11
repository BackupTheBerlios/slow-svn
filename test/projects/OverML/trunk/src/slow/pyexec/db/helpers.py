import md5

def _md5hex(obj):
    return md5.new(repr(obj)).hexdigest()


def add_type_mapping(py_type, db_type):
    _TYPE_MAPPING_PYDB[py_type] = db_type
    _TYPE_MAPPING_DBPY[db_type] = py_type

_TYPE_MAPPING_PYDB = {
    int     : 'integer',
    long    : 'integer',
    XRange  : 'integer',
    str     : 'text',
    unicode : 'text',
    bool    : 'boolean',
    # FIXME: more ?
    }

_TYPE_MAPPING_DBPY = {
    'integer' : int,
    'text'    : str,
    'boolean' : bool,
    }

