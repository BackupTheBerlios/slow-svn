try: from psyco.classes import *
except ImportError: pass

from Plex import *

__all__ = ('SpecScanner',)

p_space       = Any(" \t\n")
p_eol_comment = Str("--") + Rep(AnyBut('\n'))

#p_letter     = Range("AZaz")
p_lc_letter  = Range("az")
p_digit      = Range("09")

p_int        = Rep1(p_digit)
p_float      = Rep(p_digit) + Str('.') + Rep1(p_digit)
p_string     = ( Str("'") + AnyBut("'") + Str("'") ) | ( Str('"') + AnyBut('"') + Str('"') )
p_bool       = NoCase(Str('true', 'false'))
p_bopen      = Any('([{')
p_bclose     = Any(')]}')

p_identifier = p_lc_letter + Rep(p_lc_letter | p_digit | Str('_'))
p_attribute  = p_identifier + Rep1(Str('.') + p_identifier)

p_arithmetic_operator = Any('+-*/#%^')
p_cmp_operator        = Str('==', '<>', '<', '>', '<=', '>=')
p_bool_operator       = NoCase(Str('and', 'or', 'not'))

p_create_view = NoCase(Str('create')  + Rep1(p_space) + Str('view'))
p_as_select   = NoCase(Opt(Str('as')) + Rep1(p_space) + Str('select'))
KEYWORDS = ( 'ranked', 'from', 'with', 'where',
             'having', 'foreach', 'bucket', 'in', 'set', 'update' )


class SpecScanner(Scanner):
    def __init__(self, input_stream):
        self.par_level = [0, 0]
        Scanner.__init__(self, self._lexicon, input_stream)

    def _make_bool(self, text):
        self.produce('const_bool',   text.lower() == 'true')
    def _make_float(self, text):
        self.produce('const_float',  float(text))
    def _make_int(self, text):
        self.produce('const_int',    int(text))
    def _make_string(self, text):
        self.produce('const_string', text[1:-1])

    def _make_attribute(self, text):
        self.produce('attribute',    tuple(text.split('.')))

    _tokens = [
        (p_space | p_eol_comment, IGNORE),

        (p_bopen,    'popen'),
        (p_bclose,   'pclose'),
        (Any(',;:'), TEXT),

        (p_bool,   _make_bool),
        (p_int,    _make_int),
        (p_float,  _make_float),
        (p_string, _make_string),

        (p_arithmetic_operator, 'arithmetic_operator'),
        (p_cmp_operator,        'cmp_operator'),
        (p_bool_operator,       'bool_operator'),
        (Str('='),              'assign'),

        (p_create_view, 'kw_createview'),
        (p_as_select,   'kw_select'),
        ] + [ (NoCase(Str(keyword)), 'kw_'+keyword.lower())
              for keyword in KEYWORDS ] + [

        (p_attribute,  _make_attribute),
        (p_identifier, 'identifier')
        ]

    _lexicon = Lexicon(_tokens)


if __name__ == '__main__':
    import unittest, sys
    args = sys.argv[1:]

    def print_scan():
        for token in SpecScanner(sys.stdin):
            print token

    def list_scan():
        return list( SpecScanner(sys.stdin) )

    if '-P' in args or '-PP' in args:
        try:
            import psyco
            if '-PP' in sys.argv[1:]:
                psyco.profile()
            else:
                psyco.full()
            print "Using Psyco."
        except:
            pass

    if '-p' in args:
        import os, hotshot, hotshot.stats
        LOG_FILE="profile.log"

        profiler = hotshot.Profile(LOG_FILE)
        profiler.runcall(list_scan)
        profiler.close()

        stats = hotshot.stats.load(LOG_FILE)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(60)

        try: os.unlink(LOG_FILE)
        except: pass
    else:
        print_scan()
