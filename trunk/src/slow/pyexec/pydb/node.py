class AbstractNode(object):
    __slots__ = ()
    def _iter_attributes(self):
        for name in self._attributes:
            yield (name, getattr(self, name))
    def __iter__(self):
        return iter(self._attributes)
    def __hash__(self):
        return self._hashval
    def __eq__(self, other):
        return self._hashval == hash(other)
    def __repr__(self):
        return "node[%s]" % ','.join( '%s=%r' % (attr, getattr(self,attr,None))
                                      for attr in self._getIDs() )
    def _getIDs(self):
        "Default implementation, returns self._ids (which may not exist)"
        return self._ids

class StaticNode(AbstractNode):
    def __init__(self, attribute_value_dict, ids, hash_val=None):
        self._ids = ids
        self._attributes = tuple(sorted(attribute_value_dict.iterkeys()))
        for attr_name in self._attributes:
            if attr_name.startswith('_'):
                del attribute_value_dict[attr_name]
        if hash_val is None:
            hash_val = id(self)
        self._hashval = hash_val
        self.__dict__.update( attribute_value_dict.iteritems() )
