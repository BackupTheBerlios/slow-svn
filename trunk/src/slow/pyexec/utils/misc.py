__all__ = [ 'compose', 'curry', 'cachedmethod', 'caller_info', 'lazy' ]


class compose(object):
    "Compose two functions: compose(f,g)(y...) = f(*g(y...)))"
    def __init__(self, f, g):
        self.f, self.g = f, g

    def __call__(self, *args, **kwargs):
        mid = self.g(*args, **kwargs)
        if isinstance(mid, tuple):
            return self.f(*mid)
        else:
            return self.f(mid)


class curry(object):
    "Curry a function: curry(curry(func, a, b), c, d)(e, f) = func(a,b,c,d,e,f)"
    def __init__(self, f, *args, **kwargs):
        if isinstance(f, curry):
            self.__func = f.__func
            self.__args = f.__args + args
            if kwargs:
                self.__kwargs = kwargs
                if f.__kwargs:
                    kwargs.update(item for item in f.__kwargs.iteritems()
                                  if item[0] not in kwargs)
            elif f.__kwargs:
                self.__kwargs = f.__kwargs.copy()
            else:
                self.__kwargs = kwargs
        else:
            self.__func = f
            self.__args = args
            self.__kwargs = kwargs

    def __call__(self, *args, **kwargs):
        if kwargs:
            if self.__kwargs:
                kwargs.update(item for item in self.__kwargs.iteritems()
                              if item[0] not in kwargs)
        else:
            kwargs = self.__kwargs
        args = self.__args + args
        return self.__func(*args, **kwargs)

    def __repr__(self):
        try:
            name = self.__func.func_name
        except AttributeError:
            try:
                name = self.__func.__name__
            except AttributeError:
                name = '<anonymous>'

        args = self.__args + tuple( '%s=%r' % item for item in self.__kwargs.iteritems() )
        return "curry(%s(%s, ...))" % (name, ', '.join(args))


def cachedmethod(function):
    # broken in Py2.4
    import types
    return types.MethodType(Memorize(function), None)

class Memorize(object):
    def __new__(cls, function):
        from weakref import WeakValueDictionary
        cls.WeakValueDictionary = WeakValueDictionary
        Memorize.__new__ = object.__new__
        return object.__new__(cls)

    def __init__(self, function):
        self._cache    = self.WeakValueDictionary()
        self._callable = function

    def __call__(self, *args):
        cache = self._cache
        try:
            return cache[args]
        except KeyError:
            cache_val = cache[args] = self._callable(*args)
            return cache_val


def caller_info():
    """ Returns a list of calling functions.
        E.g. if foo calls bar, and bar calls baz, and baz calls popo,
        we get: ['popo', 'baz', 'bar', 'foo']
    """
    try:
        raise SyntaxError
    except:
        import sys
        names = []
        frame = sys.exc_traceback.tb_frame
        while frame:
            name = frame.f_code.co_name
            names.append(name)
            frame = frame.f_back
        return names[1:-1] 
        # first one is 'caller_info', last one is '?' 
        # these names can be omitted...


class lazy(object):
    def __init__(self, calculate_function):
        self._calculate = calculate_function

    def __get__(self, obj, _=None):
        if obj is None:
            return self
        value = self._calculate(obj)
        setattr(obj, self._calculate.func_name, value)
        return value
