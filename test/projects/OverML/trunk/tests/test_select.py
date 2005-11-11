#!/usr/bin/env python

import unittest
from tests import build_testsuite

from select import *

class CreateTestCase(unittest.TestCase):
    def testCreateStatement(self):
        create1 = '''
        CREATE  \n VIEW bla(bla1, bla2, \n\nbla3)
        AS SELECT bla1(bla.test1,bla.test2, bla), bla2(bla.blubb)
        FROM oldbla
        '''

        create2 = create1 + 'WHERE some condition holds'

        statement1 = CreateStatement(create1)
        statement2 = CreateStatement(create2)

        self.assertEqual(statement1.view_name,    statement2.view_name)
        self.assertNotEqual(statement1.condition, statement2.condition)

        self.assertEqual(3, len(statement1.view_objects))
        self.assertEqual(3, len(statement2.view_objects))

        self.assertEqual(2, len(statement1.select_objects))

        create3 = '''
        CREATEVIEW bla(bla1, bla2, bla3)
        AS SELECT bla1(bla.test1,bla.test2,bla.test3), bla2(bla.blubb)
        FROM oldbla
        '''

        self.assertRaises(ParserError, CreateStatement, create3)


if __name__ == "__main__":
    suite = build_testsuite( globals().values() )
    unittest.TextTestRunner(verbosity=2).run(suite)
