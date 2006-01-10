#!/usr/bin/env python

try:
    #raise ImportError
    from psyco.classes import *
except:
    pass

import sys, unittest
from string import Template

from tests import run_testsuites

from specparser import ParseException
from viewspec   import (parse_view_spec, ViewFunctions,
                        UnknownReferenceError, AmbiguousNameError)

class TestStatements(object):
    t_view_def = Template('''
    CREATE VIEW view_name
    AS SELECT node.a5 = node.a5*2,
              node.a6 = node.a1+node.a6, -- a comment here
              node.a9
    RANKED lowest(2*5, -abs(2/-1)*4/(-1)/(abs(node.a5)+1)^-2*2)
    FROM old_view
    WITH var1 = 5, var2= 29,myconfval -- some comment
    $where -- my little where comment
    $having
    $loops
    $qos
    ;
    ''')

    where_clause = '''
    WHERE (
       node.a4 and node.a4 == True
       or (1+2*round(node.a1,2) = .1E5+4.E-4)
       or node.a1 == 1 and node.as == "test"
       or 3 <= node.a1 < 8 and 8 > node.a1 < 8
       or 1+node.a1 <> 4
       )
    '''

    qos_clause = '''SET currency(10 m) ON (node.a9, node.a5)'''

    loop = Template('FOREACH $var IN ($list)')

    create = []
    select_def = Template(t_view_def.safe_substitute(loops='', having=''))

    create.append( select_def.substitute(where='', qos='') )
    create.append( select_def.substitute(where=where_clause, qos='') )
    create.append( select_def.substitute(where='', qos=qos_clause) )
    create.append( select_def.substitute(where=where_clause, qos=qos_clause) )

    complete_create = create[-1]

    create_buckets = []
    loops = loop.substitute(var='i', list='1:20,22,25:50')

    t_bucket_def = Template(t_view_def.safe_substitute(
        loops=loops, having='HAVING node.a5 in (2^i : 2^(i+1))'))

    create_buckets.append( t_bucket_def.substitute(
        where='', qos='') )
    create_buckets.append( t_bucket_def.substitute(
        where=where_clause, qos='') )
    create_buckets.append( t_bucket_def.substitute(
        where='', qos=qos_clause) )
    create_buckets.append( t_bucket_def.substitute(
        where=where_clause, qos=qos_clause) )

    #create_buckets.append( bucket_def.substitute(where='', qos='') )
    #create_buckets.append( bucket_def + where_clause + ';' )
    #create_buckets.append( bucket_def + qos_clause + ';' )
    #create_buckets.append( bucket_def + where_clause + qos_clause + ';' )

    complete_bucket_create = create_buckets[-1]


class StatementTestCase(unittest.TestCase):
    def setUp(self):
        self.create          = TestStatements.create
        self.complete_create = TestStatements.complete_create
        self.create_buckets  = TestStatements.create_buckets
        self.complete_bucket_create = TestStatements.complete_bucket_create

    def testParseStatement(self):
        statements = []
        for cr in self.create:
            try:
                statements.append(parse_view_spec(cr))
            except ParseException:
                print >>sys.stderr, cr
                raise

        self.assertEqual(True, statements[0].where_expression.evaluate())

        for statement in statements:
            self.assert_(repr(statement))

        for i in range(1,len(statements)):
            self.assertEqual(1, len(statements[i].object_select))

            self.assertEqual(statements[0].view_object.name,
                             statements[i].view_object.name)


    def testParseBuckets(self):
        statements = []
        for cr in self.create_buckets:
            try:
                statements.append(parse_view_spec(cr))
            except ParseException:
                print >>sys.stderr, cr
                raise

        self.assertEqual(True, statements[0].where_expression.evaluate())

        for i in range(1,len(statements)):
            self.assertEqual(1, len(statements[i].object_select))

            self.assertEqual(statements[0].view_object.name,
                             statements[i].view_object.name)


    def testValidStatements(self):
        valid_replacements = (
            ('CREATE VIEW view', 'CREATE VIEW new_view2'),
            #('SELECT node', 'SELECT message, node'), # -> ParseError
            ('WHERE ', 'WHERE not '),
            (' == ', ' eq '),
            (' == ', ' <> '),
            (' < ', ' lt '),
            (' and ', ' and not '),
            (' or ', ' or not '),
            ('abs(', 'tan('),
            ('abs(', 'abs(var1+'),
            ('lowest(', 'highest('),
            ('lowest(', 'closest(3/4^2,'),
            ('"test"', '"test\'s"'),
            ('10 m', '95 d'),
            ('ON (node.a5)', 'ON (node.a5, node.a2)'),
            ('myconfval', 'myconfval=1*54'),
            ('old_view', 'old1, old2, old3'),
            )

        create = self.complete_create
        for old_token, new_token in valid_replacements:
            parse_view_spec(create.replace(old_token,new_token))


    def testInvalidStatements(self):
        invalid_replacements = (
            (' and ', ' (and) '),
            (' == ', ' != '),
            ('SELECT ', 'SELECTS '),
            ('WHERE', 'WHEN'),
            ('WHERE', 'IF'),
            ('myconfval', 'myconfval+1'),
            )

        create = self.complete_create
        for token, broken in invalid_replacements:
            self.assertRaises(ParseException,
                              parse_view_spec, create.replace(token,broken))


    def testInvalidReferences(self):
        invalid_references = (
            ('lowest(', 'unknown_function('),
            ('abs(', 'unknown_function('),
            ('abs(', 'bool('),
            #('SELECT node', 'SELECT nodes'), # -> ParseError
            ('node.', 'nodes.'),
            )

        create = self.complete_create
        for token, broken in invalid_references:
            self.assertRaises(UnknownReferenceError,
                              parse_view_spec, create.replace(token,broken))

        multiple_declarations = (
            ('myconfval', 'i'),
            ('myconfval', 'node'),
            (' i ', ' node '),
            )

        create = self.complete_bucket_create
        for token, broken in multiple_declarations:
            self.assertRaises(AmbiguousNameError,
                              parse_view_spec, create.replace(token,broken))

        invalid_references = (
            (' ON (node.a9', ' ON (node.a2'),
            )

        create = self.create[2]
        for token, broken in invalid_references:
            self.assertRaises(UnknownReferenceError,
                              parse_view_spec, create.replace(token,broken))


    def testMoreFunctions(self):
        def test1(val):
            return val+1
        def test2(v1,v2):
            return v1+v2

        valid_replacements = (
            ('abs(',   'abs123(', {'abs123':test1}),
            ('round(', 'abs321(', {'abs321':test2}),
            ('',       '',        {'abs':test1}),
            ('',       '',        {'abs':test1, 'round':test2}),
            )

        create = self.complete_create
        for old_token, new_token, functions in valid_replacements:
            parse_view_spec( create.replace(old_token,new_token), functions )

        self.assertRaises(UnknownReferenceError,
                          parse_view_spec, create.replace('abs','abs1'),
                          {'abs2':test1})

    def testLists(self):
        where = 'WHERE node.a5 in ($list)'
        where_statement = Template(TestStatements.t_view_def.safe_substitute(
            where=where, qos='', loops='', having=''))

        loop = 'FOREACH i IN ($list)'
        loop_statement = Template(TestStatements.t_view_def.safe_substitute(
            where='', qos='', loops=loop, having=''))

        valid_lists = [
            '1',
            '1:5',
            '"1"',
            '1,2,3,5,6,24',
            '1,2,3,5:6,24',
            '1.5,6.5,7.6',
            '"1", "2", "3","4"',
            'True, False, True, True, False',
            ]

        invalid_lists = [
            '1,'
            '1,"1"',
            '1,2,3,5.5:6,7',
            '1.2,5.5:6.1,7.2',
            '"1", "2", "3","4":"10"',
            '1, True',
            ]

        for statement in (where_statement, loop_statement):
            for list in valid_lists:
                parse_view_spec( statement.substitute(list=list) )
            for list in invalid_lists:
                self.assertRaises(ParseException,
                                  parse_view_spec,
                                  statement.substitute(list=list))


if __name__ == "__main__":
    run_testsuites( globals().values() )
