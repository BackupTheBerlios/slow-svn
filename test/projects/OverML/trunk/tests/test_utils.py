#!/usr/bin/env python

import unittest
from tests import build_testsuite

from utils import *


class composeTestCase(unittest.TestCase):
    def testCompose(self):
        def f(v):   return v*3
        def g(v):   return v+3
        def h(a,b): return b,a

        cf = compose(f,g)
        self.assertEqual(cf(5), (5+3)*3)

        import math
        cf = compose(math.sin, pow)
        self.assertEqual(cf(5,2), math.sin(pow(5,2)))

        cf = compose(h,h)
        self.assertEqual(h(5,2),  (2,5))
        self.assertEqual(cf(5,2), (5,2))


if __name__ == "__main__":
    suite = build_testsuite( globals().values() )
    unittest.TextTestRunner(verbosity=2).run(suite)
