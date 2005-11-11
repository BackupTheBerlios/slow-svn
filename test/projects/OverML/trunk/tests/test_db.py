#!/usr/bin/env python

import unittest
from tests import build_testsuite

from db import *

class CountObserver(object):
    def __init__(self):
        self.call_count = 0
    def __call__(self, *args):
        self.call_count += 1

class Notifier(Subscriptable):
    def __call__(self, *args):
        self._notify(*args)


class SubscriptableTestCase(unittest.TestCase):
    def setUp(self):
        self.observers = [ CountObserver() for i in range(10) ]
        self.notifier  = Notifier()

    def tearDown(self):
        self.observers = None
        self.notifier  = None

    def callCounts(self):
        return [ o.call_count for o in self.observers ]

    def testSingleCallAll(self):
        for observer in self.observers:
            self.notifier.subscribe(observer)

        self.notifier()

        self.assertEqual([], [ o for o in self.observers if o.call_count < 1 ], "listener not called")
        self.assertEqual([], [ o for o in self.observers if o.call_count > 1 ], "listener called more than once")

    def testSingleCallHalf(self):
        for observer in self.observers[::2]:
            self.notifier.subscribe(observer)

        self.notifier()

        self.assertEqual(self.observers[::2], [ o for o in self.observers if o.call_count == 1 ], "inconsistent listeners")

    def testMultipleCallAll(self):
        for observer in self.observers:
            self.notifier.subscribe(observer)

        for i in range(10):
            self.notifier()

            self.assertEqual([], [ o for o in self.observers if o.call_count != i+1 ], "inconsistent listeners")

    def testMultipleSubscribe(self):
        for i in range(10):
            for observer in self.observers:
                self.notifier.subscribe(observer)

            self.notifier()

            self.assertEqual([], [ o for o in self.observers if o.call_count != i+1 ], "inconsistent listeners")

    def testMultipleUnsubscribe(self):
        for observer in self.observers:
            self.notifier.subscribe(observer)

        for i, observer in enumerate(self.observers):
            self.notifier()
            self.notifier.unsubscribe(observer)

            self.assertEqual(self.observers[i:], [ o for o in self.observers if o.call_count > i ], "inconsistent listeners")

        before = self.callCounts()
        self.notifier()
        after  = self.callCounts()

        self.assertEqual(before, after, "inconsistent listeners")


class NodeTestCase(unittest.TestCase):
    def get(self): return 1
    def set(self, value):
        if value != 1:
            raise ValueError

    def build_property(self):
        return SubscriptableProperty(self.get, self.set)

    def setUp(self):
        self.listener = CountObserver()

    def testNodes(self):
        common_property_object = self.build_property()

        nodes = []
        for i in range(10):
            property_object = self.build_property()
            nodes.append( Node({'bla':property_object, 'common_bla':common_property_object}) )

        for node in nodes:
            self.assertRaises(AttributeError, node._subscribe, 'nobla', self.listener)
            node._subscribe('bla', self.listener)

        for node in nodes:
            self.assertEquals(1, node.bla)
            self.assertRaises(ValueError, setattr, node, 'bla', 2)
            node.bla = 1

        self.assertEqual(self.listener.call_count, len(nodes), 'invalid call_count: %d' % self.listener.call_count)

        nodes[0]._subscribe('common_bla', self.listener)
        nodes[-1].common_bla = 1

        self.assertEqual(self.listener.call_count, len(nodes)+1, 'invalid call_count: %d' % self.listener.call_count)

    def testNodeCopies(self):
        property_object = self.build_property()

        node = Node({'bla':property_object})
        node._subscribe('bla', self.listener)

        for i in range(10):
            node = node._copy()

        node.bla = 1
        self.assertEqual(1, self.listener.call_count, 'invalid call_count: %d' % self.listener.call_count)


class TransformerTestCase(unittest.TestCase):
    @staticmethod
    def const_transform(value):  return 10

    @staticmethod
    def add10_transform(value):  return value+10

    @staticmethod
    def add50_transform(value):  return value+50

    class pback(object):
        def __init__(self, value): self.set(value)
        def set(self, value):      self.val = value
        def get(self):             return self.val

    def get(self): return 1
    def set(self, value):
        if value != 1:
            raise ValueError

    def testPropertyTransformer(self):

        value = self.pback(5)
        property_object = SubscriptableProperty(value.get, value.set)

        node1 = Node({'bla':property_object})

        self.assertEqual( 5, node1.bla)

        transform = PropertyTransformer(self.const_transform, None)
        transformed_property = transform(property_object)
        node2 = Node({'bla':transformed_property})

        self.assertEqual( 5, node1.bla)
        self.assertEqual(10, node2.bla)

        transform = PropertyTransformer(self.add10_transform, self.add50_transform)
        transformed_property = transform(property_object)

        node3 = Node({'bla':transformed_property})

        self.assertEqual( 5, node1.bla)
        self.assertEqual(10, node2.bla)
        self.assertEqual(15, node3.bla)

        transform = PropertyTransformer(self.add10_transform, self.add50_transform)
        transformed_property = transform(node2._getProperty('bla'))

        node4 = Node({'bla':transformed_property})

        self.assertEqual( 5, node1.bla)
        self.assertEqual(10, node2.bla)
        self.assertEqual(15, node3.bla)
        self.assertEqual(20, node4.bla)

        node4.bla = 1

        self.assertEqual(51, node1.bla)
        self.assertEqual(10, node2.bla)
        self.assertEqual(61, node3.bla)
        self.assertEqual(20, node4.bla)

        node3.bla = 2

        self.assertEqual(52, node1.bla)
        self.assertEqual(10, node2.bla)
        self.assertEqual(62, node3.bla)
        self.assertEqual(20, node4.bla)

        node2.bla = 3

        self.assertEqual( 3, node1.bla)
        self.assertEqual(10, node2.bla)
        self.assertEqual(13, node3.bla)
        self.assertEqual(20, node4.bla)

        node1.bla = 4

        self.assertEqual( 4, node1.bla)
        self.assertEqual(10, node2.bla)
        self.assertEqual(14, node3.bla)
        self.assertEqual(20, node4.bla)


    def testNodeTransformer(self):
        pass


if __name__ == "__main__":
    suite = build_testsuite( globals().values() )
    unittest.TextTestRunner(verbosity=2).run(suite)
