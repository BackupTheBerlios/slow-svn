#!/usr/bin/env python

try:
    #raise ImportError
    from psyco.classes import *
except:
    pass

import sys, unittest, copy, math, time
from itertools import *
from string import Template
from tests import run_testsuites

from specparser import ParseException, StatementParser
from viewspec   import ViewSpecification, parse_view_spec
from slow.pyexec.pydb.views import NodeView, ViewRegistry
from slow.pyexec.pydb.db    import NodeDB, DBNode

################################################################################

DRAW_GRAPHS = False
#DRAW_GRAPHS = True

SHOW_VISUAL3D = False
#SHOW_VISUAL3D = True

ACTIVE_TESTS = [
    'testViewCreation',
    'testViewVariables',
    'testViewCircle',
    'testLocalViewCircle',
    'testViewChord',
    'testViewKademlia',
    'testView2BitPastry',
    'testViewDeBruijn',
    ]

################################################################################

if DRAW_GRAPHS:
    from view_viz import ViewGraph
if SHOW_VISUAL3D:
    from dot_visual import VisualViewGraph

def on_off(f):
    name = f.__name__
    if name in ACTIVE_TESTS:
        return f
    else:
        def dummy(*args, **kwargs):
            pass
        dummy.__doc__ = "Deactivated test '%s'" % name
        return dummy


class ViewTestCase(unittest.TestCase):
    NODE_COUNT = 40 # number of nodes to test

    def setUp(self):
        self.db      = NodeDB('db')
        self.viewreg = ViewRegistry(self.db)

    @on_off
    def testViewCreation(self):
        "Test: creating views"

        view_def = '''
        CREATE VIEW view_name
        AS SELECT node.a1 = node.a3 - node.a1,
                  node.a2 = node.a1 + node.a2,
                  node.a3 = 2 * node.a5 + node.a3,
                  node.a5,
                  node.a_new = 75
        RANKED lowest(2*5, node.a3*(node.a5^2)+1)
        FROM db
        '''

        where_clause = '''
        WHERE node.a3
           or (1+2*round(node.a1,2) = .1E5+4.E-4)
           or node.a1 == 1 and node.a2 == "test"
           or 1+node.a1 <> 4
        '''

        create       = view_def + ';'
        create_where = view_def + where_clause + ';'

        attr_names = [ 'a%s' % i for i in range(1,10) ]

        db = self.db
        for i in range(9):
            db.addAttribute(attr_names[i], int)

        for a5 in range(-100,100):
            node = DBNode(db)
            for i in range(9):
                setattr(node, attr_names[i], i+1)
            node.a5 = a5
            db.addNode(node)

        sview0 = NodeView( parse_view_spec(create.replace('view_name', 'sview0')), self.viewreg )
        self.assertEqual(2*5, len(sview0.getBucket()))

        sview1 = NodeView( parse_view_spec(create_where.replace('view_name', 'sview1')), self.viewreg )
        self.assertEqual(2*5, len(sview1.getBucket()))

        sview0_bucket = sview0.getBucket()
        for node in sview1.getBucket():
            self.assert_(node in sview0_bucket)

        create_subview = create_where.replace('FROM db', 'FROM sview0')
        sview2 = NodeView( parse_view_spec(create_subview.replace('view_name', 'sview2')), self.viewreg )
        self.assertEqual(2*5, len(sview2.getBucket()))

        create_mergeview = create_where.replace('2*5','2*10').replace('FROM db', 'FROM sview0, sview1')
        sview3 = NodeView( parse_view_spec(create_mergeview.replace('view_name', 'sview3')), self.viewreg )

        # both parent nodes are equal, merging them should filter duplicates
        self.assertEqual(2*5, len(sview3.getBucket()))

##         # merging parents without DISTINCT adds duplicates
##         create_mergeview_dup = create_mergeview.replace('DISTINCT','')
##         sview3_dup = NodeView( parse_view_spec(create_mergeview_dup.replace('view_name', 'sview3_dup')), self.viewreg )

##         self.assertEqual(2*10, len(sview3_dup.getBucket()))

        # verify that nodes only appear once
        nodes = []
        for node in sview3.getBucket():
            self.assert_(node not in nodes)
            nodes.append(node)

        # retry inheriting from all known views
        for i in range(10):
            list_of_known_views = ','.join(view_name for view_name in self.viewreg)
            create_mergeview = create_where.replace('2*5', '2*20').replace('FROM db', 'FROM '+list_of_known_views)
            sview4 = NodeView( parse_view_spec(create_mergeview.replace('view_name', 'sview%02d'%i)), self.viewreg )

        # verify that nodes only appear once
        nodes = []
        for node in sview3.getBucket():
            self.assert_(node not in nodes)
            nodes.append(node)

        nodes_a5 = set()
        for node in sview4.getBucket():
            self.assert_(node.a5 not in nodes_a5)
            nodes_a5.add(node.a5)


    @on_off
    def testViewVariables(self):
        "Test: variable usage in views"

        view_def = '''
        CREATE VIEW view_name
        AS SELECT node.a1 = (node.a3 - node.a1) * var_a,
                  node.a2 = node.a1 + node.a2,
                  node.a3 = 2 * node.a5 + node.a3,
                  node.a5,
                  node.a_new = var_a
        RANKED lowest(var_a*2, var_a*node.a3*(node.a5^2)+1)
        FROM db
        WITH var_a = 5
        '''

        where_clause = '''
        WHERE node.a3
           or (1+2*round(node.a1,2) = .1E5+4.E-4)
           or node.a1 == 1 and node.a2 == "test"
           or 1+node.a1 <> 4
        '''

        create       = view_def + ';'
        create_where = view_def + where_clause + ';'

        attr_names = [ 'a%s' % i for i in range(1,10) ]

        db = self.db
        for i in range(9):
            db.addAttribute(attr_names[i], int)

        for a5 in range(-100,100):
            node = DBNode(db)
            for i in range(9):
                setattr(node, attr_names[i], i+1)
            node.a5 = a5
            db.addNode(node)


        sview0 = NodeView( parse_view_spec(create.replace('view_name', 'sview0')), self.viewreg )

        self.assertEqual(len(sview0.getBucket()), len(sview0))

        some_node = sview0.getBucket()[0]
        a1_of_some_node = some_node.a1

        self.assertEqual(2*5, len(sview0))
        sview0.setVariable('var_a', 8)
        self.assertEqual(2*8, len(sview0))

        some_node = sview0.getBucket()[0]
        self.assertNotEqual(a1_of_some_node, some_node.a1)

        sview1 = NodeView( parse_view_spec(create_where.replace('view_name', 'sview1')), self.viewreg )

        self.assertEqual(2* 5, len(sview1))
        sview1.setVariable('var_a', 16)
        self.assertEqual(2*16, len(sview1))
        self.assertEqual(2* 8, len(sview0))

        create_subview = create_where.replace('FROM db', 'FROM sview0')
        sview2 = NodeView( parse_view_spec(create_subview.replace('view_name', 'sview2')), self.viewreg )

        sview2.setVariable('var_a', 1000)
        self.assertEqual(2*8,  len(sview0))
        self.assertEqual(2*8,  len(sview2))
        self.assertEqual(2*16, len(sview1))


    @on_off
    def testViewCircle(self):
        """Test: ring topology
        Each node has one or more neighbours in each direction.
        """

        node_count = self.NODE_COUNT

        db = self.db
        db.addAttribute('id', int)
        nodes = [ DBNode(db, id=n) for n in range(node_count) ]

        self.db.addNodes(nodes)

        circle_view_def = Template('''
        CREATE VIEW circle_neighbours_${id}_$cmp
        AS SELECT node.id
        RANKED lowest(ncount, dist($id, node.id))
        FROM db
        WITH ncount=1
        WHERE abs(node.id - $id) <= $maxid / 2  and     node.id $cmp $id
           or abs(node.id - $id) >  $maxid / 2  and not node.id $cmp $id
        ;
        ''')

        def ring_dist(n1, n2):
            return min(abs(n1 - n2), max_id - abs(n1 - n2))

        func_def = {'dist':ring_dist}
        max_id   = node_count

        viewreg = self.viewreg
        for node in nodes:
            view_spec_lt = circle_view_def.substitute(maxid=max_id, id=node.id, cmp='lt')
            view_spec_gt = circle_view_def.substitute(maxid=max_id, id=node.id, cmp='gt')

            spec_lt = parse_view_spec(view_spec_lt, func_def)
            spec_gt = parse_view_spec(view_spec_gt, func_def)

            node._lt = NodeView(spec_lt, viewreg)
            node._gt = NodeView(spec_gt, viewreg)

        for ncount in (1,4):
            for node in nodes:
                node._lt.setVariable('ncount', ncount)
                node._gt.setVariable('ncount', ncount)

            for node in nodes:
                self.assertEqual(ncount, len(node._lt.getBucket()))
                self.assertEqual(ncount, len(node._gt.getBucket()))

            # test if nodes know their neighbours
            node_count = len(nodes)
            neighbour_iterators = [ islice(niter, i, node_count+i)
                                    for (i, niter) in enumerate(tee(chain(nodes,nodes,nodes), ncount+1)) ]

            for neighbours in izip(*neighbour_iterators):
                node = neighbours[0]
                for neighbour in neighbours[1:]:
                    self.assert_(neighbour     in node._gt.getBucket())
                    self.assert_(neighbour not in node._lt.getBucket())
                    self.assert_(node      not in neighbour._gt.getBucket())
                    self.assert_(node          in neighbour._lt.getBucket())

            if DRAW_GRAPHS:
                ViewGraph.write_files( [ (node, (node._lt, node._gt))
                                         for node in nodes ],
                                       program='circo', fname='circle%02d'%ncount )

            if SHOW_VISUAL3D:
                VisualViewGraph( [ (node, (node._lt, node._gt))
                                   for node in nodes ],
                                 program='circo', graph_name='Circle%02d'%ncount )

            self.viewreg.unregister_all()


    @on_off
    def testLocalViewCircle(self):
        """Test: ring topology with local object
        Each node has one or more neighbours in each direction.
        """

        node_count = self.NODE_COUNT

        db = self.db
        db.addAttribute('id', int)
        nodes = [ DBNode(db, id=n) for n in range(node_count) ]

        self.db.addNodes(nodes)

        circle_view_def = Template('''
        CREATE VIEW circle_neighbours_$cmp
        AS SELECT node.id
        RANKED lowest(ncount, dist(local.id, node.id))
        FROM db
        WITH ncount=1, local
        WHERE abs(node.id - local.id) <= $maxid / 2  and     node.id $cmp local.id
           or abs(node.id - local.id) >  $maxid / 2  and not node.id $cmp local.id
        ;
        ''')

        def ring_dist(n1, n2):
            return min(abs(n1 - n2), max_id - abs(n1 - n2))

        func_def = {'dist':ring_dist}
        max_id   = node_count

        view_spec_lt = StatementParser.parse(
            circle_view_def.substitute(maxid=max_id, cmp='lt') )
        view_spec_gt = StatementParser.parse(
            circle_view_def.substitute(maxid=max_id, cmp='gt') )

        viewreg = self.viewreg
        for node in nodes:
            local_id = "%010d" % node.id
            spec_lt = ViewSpecification(view_spec_lt, func_def,
                                        view_spec_lt.view_name + local_id)
            spec_gt = ViewSpecification(view_spec_gt, func_def,
                                        view_spec_gt.view_name + local_id)

            node._lt = NodeView(spec_lt, viewreg, local=node)
            node._gt = NodeView(spec_gt, viewreg, local=node)

        for ncount in (1,10,7,4,7):
            for node in nodes:
                node._lt.setVariable('ncount', ncount)
                node._gt.setVariable('ncount', ncount)

            for node in nodes:
                self.assertEqual( ncount, len(node._lt.getBucket()) )
                self.assertEqual( ncount, len(node._gt.getBucket()) )

            # test if nodes know their neighbours
            node_count = len(nodes)
            neighbour_iterators = [ islice(niter, i, node_count+i)
                                    for (i, niter) in enumerate(tee(chain(nodes,nodes,nodes), ncount+1)) ]

            for neighbours in izip(*neighbour_iterators):
                node = neighbours[0]
                for neighbour in neighbours[1:]:
                    self.assert_(neighbour     in node._gt.getBucket())
                    self.assert_(neighbour not in node._lt.getBucket())
                    self.assert_(node      not in neighbour._gt.getBucket())
                    self.assert_(node          in neighbour._lt.getBucket())

            if DRAW_GRAPHS:
                ViewGraph.write_files( [ (node, (node._lt, node._gt))
                                         for node in nodes ],
                                       program='circo', fname='circle%02d'%ncount )

            if SHOW_VISUAL3D:
                VisualViewGraph( [ (node, (node._lt, node._gt))
                                   for node in nodes ],
                                 program='circo', graph_name='Circle%02d'%ncount )

            self.viewreg.unregister_all()


    @on_off
    def testViewChord(self):
        "Test: chord finger table"
        node_count = self.NODE_COUNT

        db = self.db
        db.addAttribute('id', int)
        nodes = [ DBNode(db, id=n) for n in range(node_count) ]

        self.db.addNodes(nodes)

        # specify
        log_nodes = int(math.log(node_count, 2))
        max_id    = node_count-1
        def chord_dist(n1, n2):
            dist = n2 - n1
            if dist < 0:
                dist += max_id + 1
            return dist

        func_def = {'dist':chord_dist}

        finger_view_def = Template('''
        CREATE VIEW circle_neighbours
        AS SELECT node.id, node.dist=i
        RANKED highest(i+1, dist(local.id, node.id))
        FROM db
        WITH local
        HAVING dist(local.id, node.id) in (2^i : 2^(i+1))
        FOREACH i IN (0:$log_nodes)
        ;
        ''')

        # create
        view_spec = StatementParser.parse(
            finger_view_def.substitute(log_nodes=log_nodes) )

        viewreg   = self.viewreg
        for node in nodes:
            local_id = "%010d" % node.id
            spec = ViewSpecification(view_spec, func_def,
                                     view_spec.view_name + local_id)
            node._fingertable = NodeView(spec, viewreg, local=node)

        # verify
        for node in nodes:
            for i in range(log_nodes):
                n_node = node._fingertable.getBucket(i)[0]
                self.assert_(len(node._fingertable.getBucket(  i   )) > 0)
                self.assert_(len(node._fingertable.getBucket( (i,) )) > 0)

        if DRAW_GRAPHS:
            ViewGraph.write_files( [ (node, (node._fingertable,))
                                     for node in nodes ],
                                   program='circo', fname='chord',
                                   root=str(nodes[0]), rankdir='BT'
                                   )

        if SHOW_VISUAL3D:
            VisualViewGraph( [ (node, (node._fingertable,))
                               for node in nodes ],
                             program='circo', graph_name='Chord' )

    @on_off
    def testViewKademlia(self):
        "Test: kademlia metric"
        node_count = self.NODE_COUNT*2

        db = self.db
        db.addAttribute('id', int)
        nodes = [ DBNode(db, id=n) for n in range(node_count) ]

        self.db.addNodes(nodes)

        # specify
        log_nodes = int(math.log(node_count, 2))
        max_id    = node_count-1

        func_def = {}

        finger_view_def = Template('''
        CREATE VIEW xor_neighbours
        AS SELECT node.id
        RANKED furthest(n_count, local.id, local.id # node.id)
        FROM db
        WITH local, n_count=2
        HAVING local.id # node.id in (2^i : 2^(i+1))
        FOREACH i IN (0:$log_nodes)
        ;
        ''')

        # create
        view_spec = StatementParser.parse(
            finger_view_def.substitute(log_nodes=log_nodes+1) )

        viewreg   = self.viewreg
        for node in nodes:
            local_id = "%010d" % node.id
            spec = ViewSpecification(view_spec, func_def,
                                     view_spec.view_name + local_id)
            node._fingertable = NodeView(spec, viewreg, local=node)

##         # verify
##         for node in nodes:
##             for i in range(log_nodes):
##                 print len(node._fingertable.getBucket(i)),
##                 #n_node = node._fingertable.getBucket(i)[0]
##                 #self.assert_(len(node._fingertable.getBucket(  i   )) > 0)
##                 #self.assert_(len(node._fingertable.getBucket( (i,) )) > 0)

        if DRAW_GRAPHS:
            ViewGraph.write_files( [ (node, (node._fingertable,))
                                     for node in nodes ],
                                   program='fdp', fname='xor',
                                   root=str(nodes[0]), rankdir='RL',
                                   ratio="0.6"
                                   )

        if SHOW_VISUAL3D:
            VisualViewGraph( [ (node, (node._fingertable,))
                               for node in nodes ],
                             program='fdp', graph_name='Kademlia' )

    @on_off
    def testView2BitPastry(self):
        "Test: Extremely slow 2-bit Pastry routing table"
        node_count = self.NODE_COUNT
        log_nodes = int(math.ceil(math.log(node_count, 2)))

        max_digit = 4

        def id_str(id):
            return ''.join( str((id >> bits) & 3)
                            for bits in range(log_nodes, -1, -2) )

        max_prefix = len(id_str(node_count))
        max_id     = node_count-1

        db = self.db
        db.addAttribute('nid', int)
        db.addAttribute('id',  str)
        nodes = [ DBNode(db, id=id_str(n), nid=n) for n in range(node_count) ]

        self.db.addNodes(nodes)

        def ring_dist(n1, n2):
            return min(abs(n1 - n2), max_id - abs(n1 - n2))

        def pastry_prefix_len(n1, n2):
            p_len = 0
            while p_len < max_prefix and n1[p_len] == n2[p_len]:
                p_len += 1
            return p_len

        def digit_at_pos(n, p_len):
            return int(n[ min(p_len, len(n)-1) ], max_digit)

        func_def = {
            'prefix_len'   : pastry_prefix_len,
            'digit_at_pos' : digit_at_pos,
            'ring_dist'    : ring_dist
            }

        rt_view_def = Template('''
        CREATE VIEW pastry_rows
        AS SELECT node.id, node.nid
        RANKED highest(1, ring_dist(local.nid, node.nid))
        FROM db
        WITH local
        HAVING digit_at_pos(node.id, prefix) == digit
           and prefix_len(local.id, node.id) == prefix
        FOREACH digit IN (0:$max_digit)
        FOREACH prefix in (0:$max_prefix)
        ;
        ''')

        view_spec = StatementParser.parse(
            rt_view_def.substitute(max_prefix=max_prefix, max_digit=max_digit)
            )

        viewreg = self.viewreg
        for node in nodes:
            spec = ViewSpecification(view_spec, func_def,
                                     view_spec.view_name + node.id)

            node._rt = NodeView(spec, viewreg, local=node)

        for node in nodes:
            rt = node._rt
            self.assert_(len(rt) > 0)
            for row in range(max_prefix):
                for col in range(max_digit):
                    for neighbour in rt.getBucket(row, col):
                        self.assertEqual(digit_at_pos(neighbour.id, row),
                                         col)

        if DRAW_GRAPHS:
            ViewGraph.write_files( [ (node, (node._rt,))
                                     for node in nodes ],
                                   program='circo', fname='pastry',
                                   root=str(nodes[0]), rankdir='BT'
                                   )

        if SHOW_VISUAL3D:
            VisualViewGraph( [ (node, (node._rt,))
                               for node in nodes ],
                             program='circo', graph_name='Pastry' )

    @on_off
    def testViewDeBruijn(self):
        "Test: complete 2-bit de-Bruijn Graph"
        node_count = 64 # self.NODE_COUNT
        max_digit = 4

        log_nodes = int(math.ceil(math.log(node_count, max_digit)))
        max_id    = max_digit ** log_nodes

        def id_str(id):
            return ''.join( str((id // (max_digit ** divider)) % max_digit)
                            for divider in range(log_nodes-1, -1, -1) )

        db = self.db
        db.addAttribute('id',  int)
        db.addAttribute('sid', str)
        nodes = [ DBNode(db, sid=id_str(n), id=n) for n in range(node_count) ]

        self.db.addNodes(nodes)

        de_bruijn_view_def = Template('''
        CREATE VIEW de_bruijn
        AS SELECT node.id, node.sid
        FROM db
        WITH local
        HAVING node.id == (local.id * $max_digit) % $max_id + digit
        FOREACH digit IN (0:$max_digit)
        ;
        ''')

        view_spec = StatementParser.parse(
            de_bruijn_view_def.substitute(max_digit=max_digit, max_id=max_id)
            )

        viewreg = self.viewreg
        for node in nodes:
            local_id = "%010d" % node.id
            spec = ViewSpecification(view_spec,
                                     new_name=view_spec.view_name + local_id)

            node._debruijn = NodeView(spec, viewreg, local=node)

        for node in nodes:
            rt = node._debruijn
            self.assert_(len(rt) > 0)
            for digit in range(max_digit):
                for neighbour in rt.getBucket(digit):
                    self.assertEqual(str(digit), neighbour.sid[-1])
                    self.assertEqual(neighbour.sid[:-1], node.sid[1:])

        if DRAW_GRAPHS:
            ViewGraph.write_files( [ (node, (node._debruijn,))
                                     for node in nodes ],
                                   program='fdp', fname='de-bruijn',
                                   root=str(nodes[0]), rankdir='BT'
                                   )

        if SHOW_VISUAL3D:
            VisualViewGraph( [ (node, (node._debruijn,))
                               for node in nodes ],
                             program='fdp', root=str(nodes[0]),
                             rankdir='BT', graph_name='de-Bruijn'
                             )


if __name__ == "__main__":
    run_testsuites( globals().values() )
