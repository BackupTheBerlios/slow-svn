try:
    #raise ImportError
    import psyco
    from psyco.classes import *
    psyco.full()
    #psyco.profile()
    print "Using psyco."
except:
    pass

import random, math
from itertools import *
from string import Template

from twisted.internet import defer, reactor
from pg import DatabaseError

from stupidio import StupidIO, StupidScheduler
from harvesters import BidirectionalGossipHarvester
from viewspec import StatementParser, ViewSpecification
from views import ViewRegistry
from sqldb import (SQLNodeDB, SQLDBNode, SQLNodeView,
                   STATIC_ATTRIBUTE, VOLATILE_ATTRIBUTE,
                   clean_up, db_connect)

from vis import view_snapshot
import Image

#HOST='localhost'
HOST='krakau.dvs1.informatik.tu-darmstadt.de'
#HOST='hannover.dvs1.informatik.tu-darmstadt.de'

class HarvesterTest(object):
    def __init__(self, db_connection, build_graphs=True):
        self.io = StupidIO()
        self.id_attributes = {'id':(STATIC_ATTRIBUTE, int), 'addr':(STATIC_ATTRIBUTE, str)}
        self.node_env = {}
        self.db_connection = db_connection
        self.build_graphs  = build_graphs

        self.id_only_view_spec = StatementParser.parse('''
        CREATE VIEW id_only
        AS SELECT node.id
        FROM parent
        FOREACH BUCKET
        ;
        ''')

    @staticmethod
    def build_id_only_node_name(node):
        return "node[id=%r]" % node.id

    @staticmethod
    def _unpack_list(node_tuples):
        return [ item[1] for item in node_tuples ]

    def _create_nodes(self, count):
        node_identifier = ('addr',)
        connection      = self.db_connection
        attribute_types = self.id_attributes
        create_node     = self._create_node

        def build_node_filter(l_id):
            return (lambda node: node.id != l_id)

        deferred = defer.DeferredList(
            [ create_node(local_id, connection,
                          attribute_types=attribute_types,
                          node_filter=build_node_filter(local_id),
                          node_identifier_attributes=node_identifier )
              for local_id in xrange(count) ]
            )

        deferred.addCallback(self._unpack_list)
        return deferred

    def _create_node(self, id, *args, **kwargs):
        db_name = 'db%010d' % id
        db = SQLNodeDB(db_name, *args, **kwargs)

        addr = '127.0.0.1:%05d' % (id%65536)
        self.node_env[addr] = {
            'db':db,
            'vr':ViewRegistry(db),
            'io':self.io.create_node()
            }

        deferred = db.connect()

        def create_local_node(_):
            return db.create_local_node(id=id, addr=addr)
        
        deferred.addCallback(create_local_node)
        return deferred


    def run_circle(self, node_count):
        deferred = self._create_nodes(node_count)
        deferred.addCallback(self.run_circle_with_nodes)

    def run_circle_with_nodes(self, nodes):
        max_id = len(nodes) - 1
        n_count=6

        view_def = Template('''
        CREATE VIEW circle_neighbours
        AS SELECT node.id, node.addr
        RANKED lowest(n_count, min(abs(local.id - node.id),
                               $max_id - abs(local.id - node.id)))
        FROM db
        WITH local, n_count
        ;
        ''').substitute(max_id=max_id)

        # FIXME: twisted ...

        view_spec = StatementParser.parse(view_def)

        for node in nodes:
            node_env = self.node_env[node.addr]

            spec = ViewSpecification(view_spec,
                                     new_name='circle_neighbours_%010x' % node.id,
                                     new_parents=(node_env['db'].name,))
            view = NodeView(spec, node_env['vr'],
                            local=node, n_count=n_count)

            node_env['spec'] = spec
            node_env['view'] = view

        for node in nodes:
            node_env = self.node_env[node.addr]

            harvester = BidirectionalGossipHarvester(
                node_env['io'], node,
                node_env['db'], node_env['vr'], SQLNodeView,
                (node_env['spec'], node_env['view'])
                )

            node_env['harvester'] = harvester

        def is_correct(node):
            distances = sum( min(abs(nid - view_node.id), max_id - abs(nid - view_node.id))
                             for view_node in node._view )
            return distances <= (n_count ** 2) / 2 # FIXME ...

        def is_complete(node):
            return len(self.node_env[node.addr]['view']) < n_count

        self.run_harvesting(nodes)


    def run_chord(self, node_count):
        deferred = self._create_nodes(node_count)
        deferred.addCallback(self.run_chord_with_nodes)
        return deferred

    def run_chord_with_nodes(self, nodes):
        log_nodes = int(math.log(len(nodes), 2))
        max_id    = len(nodes) - 1
        n_count=6

        def chord_dist(n1, n2):
            dist = n2 - n1
            if dist < 0:
                dist += max_id + 1
            return dist

        sql_chord_dist = """
        CREATE FUNCTION %%s(integer, integer) RETURNS integer AS '
          SELECT CASE WHEN ($2-$1) < 0 THEN %s + ($2-$1) ELSE ($2-$1) END
        ' LANGUAGE SQL STRICT;
        """ % (max_id+1)

        for node_env in self.node_env.itervalues():
            node_db = node_env['db']
            node_db.create_function('dist', sql_chord_dist)

        func_def = {'dist' : chord_dist}

        view_def = Template('''
        CREATE VIEW circle_neighbours
        AS SELECT node.id, node.addr
        RANKED highest(i+1, dist(local.id, node.id))
        FROM db
        WITH local
        HAVING dist(local.id, node.id) in (2^i : 2^(i+1))
        FOREACH i IN (0:$log_nodes)
        ;
        ''').substitute(log_nodes=log_nodes)

        view_spec = StatementParser.parse(view_def)

        deferreds = []
        for node in nodes:
            node_env = self.node_env[node.addr]
            node_db  = node_env['db']
            view_reg = node_env['vr']
            spec = ViewSpecification(view_spec, func_def,
                                     new_name='circle_neighbours_%010x' % node.id,
                                     new_parents=(node_db.name,))
            node_env['spec'] = spec

            deferred = node_db.create_view(spec, view_reg)
            deferreds.append(deferred)

        def is_correct(node):
            node_env = self.node_env[node.addr]
            view = node_env['view']
            deferred = view.iterBuckets()

            nid = node.id
            def bucket_test(buckets):
                for (i,), bucket in buckets:
                    if len(bucket) == 0:
                        return False
                    id_range = xrange(2**i, 2**(i+1))
                    for neighbour in bucket:
                        if chord_dist(nid, neighbour.id) not in id_range:
                            return False
                return True

            deferred.addCallback(bucket_test)
            return deferred

        def is_complete(node):
            node_env = self.node_env[node.addr]
            view = node_env['view']
            deferred = view.iterBuckets()

            def bucket_test(buckets):
                bucket_count = 0
                for (i,), bucket in buckets:
                    bucket_count += 1
                    if len(bucket) < i:
                        return False
                return bucket_count > 0

            deferred.addCallback(bucket_test)
            return deferred

        deferred_list = defer.DeferredList(deferreds)
        deferred_list.addCallback(self._unpack_list)
        deferred_list.addCallback(self.build_harvesters, nodes, is_correct, is_complete)
        return deferred_list

    def build_harvesters(self, views, nodes, is_correct, is_complete):
        for view, node in zip(views, nodes):
            node_env = self.node_env[node.addr]
            node_db  = node_env['db']
            view_reg = node_env['vr']

            harvester = BidirectionalGossipHarvester(
                node_env['io'], node, node_db, view_reg,
                SQLNodeView, (node_env['spec'], view)
                )

            node_env['harvester'] = harvester
            node_env['view'] = view

        if self.build_graphs:
            deferreds = []
            for node in nodes:
                node_env = self.node_env[node.addr]
                node_db  = node_env['db']
                spec = ViewSpecification(self.id_only_view_spec,
                                         new_name="idov%08x" % node.id,
                                         new_parents=(node_env['view'].name,)
                                         )

                deferred = node_db.create_view(spec, node_env['vr'])

                def set_id_only_view(view, node_env):
                    node_env['id_only_view'] = view

                deferred.addCallback(set_id_only_view, node_env)
                deferreds.append(deferred)

            deferred_list = defer.DeferredList(deferreds)

            build_id_only_node_name = self.build_id_only_node_name
            def build_graph(_):
                return view_snapshot.ViewCircleSnapshot(
                    [ (build_id_only_node_name(node),
                       (self.node_env[node.addr]['id_only_view'],))
                      for node in nodes] )

            deferred_list.addCallback(build_graph)
        else:
            deferred_list = defer.succeed(None)

        deferred_list.addCallback(
            self.run_harvesting, nodes, is_correct, is_complete)

    def rebuild_graph(self, _, graph, node, node_env):
        return graph.rebuild_edges_from_views(
            self.build_id_only_node_name(node),
            (node_env['id_only_view'],) )

    def build_image(self, _, graph, image_counter):
        image = graph.snapshot().resize( (700,700), Image.BICUBIC )
        image.save('img/test%010d.gif' % image_counter, 'GIF')

    def run_harvesting(self, graph, nodes, is_correct, is_complete):
        self.image_counter = 0

        choose1 = random.choice
        def node_action(node):
            deferred = is_complete(node)

            node_env  = self.node_env[node.addr]
            view      = node_env['view']
            harvester = node_env['harvester']
            def find_source(complete):
                if complete:
                    deferred = view.iterNodes()
                    deferred.addCallback(tuple)
                else:
                    deferred = defer.succeed(nodes)
                return deferred

            deferred.addCallback(find_source)

            def send_specs(nodes):
                recipient = choose1(nodes)
                while recipient is node:
                    recipient = choose1(nodes)

                recipient_env = self.node_env[recipient.addr]
                deferred = harvester.send_specs(recipient_env['io'])

                if self.build_graphs:
                    deferred.addCallback(self.rebuild_graph, graph, node,      node_env)
                    deferred.addCallback(self.rebuild_graph, graph, recipient, recipient_env)
                    deferred.addCallback(self.build_image, graph, self.image_counter)
                    self.image_counter += 1

                return deferred

            deferred.addCallback(send_specs)
            return deferred

        def run_iteration(_):
            dlist = defer.DeferredList([ node_action(node) for node in nodes ])
            dlist.addCallback(run_iteration)
            return dlist

        return run_iteration(None)


if __name__ == "__main__":
    if HOST == 'localhost':
        username    = 'me'
        max_connect =  4
        node_count  = 32
    else:
        username    = 'behnel'
        max_connect = 8
        node_count  = 128

    db_pool = db_connect(host=HOST, user=username, password='pg',
                         max_connect=max_connect)

    deferred = clean_up(db_pool)

    test = HarvesterTest(db_pool, build_graphs=False)

    def run_test(_):
        test.run_chord(node_count)

    def show_error(value):
        print
        print "ERROR:", value
        print

    deferred.addCallback(run_test)
    deferred.addErrback(show_error)

    reactor.run()
