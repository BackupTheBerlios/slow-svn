try:
    from psyco.classes import *
except:
    pass

from itertools import *

from twisted.internet import defer

from views import ViewRegistry

class Harvester(object):
    def __init__(self, db, view_registry, view_class, *view_specs):
        self._view_specs    = set(item[0] for item in view_specs)
        self._views         = set(item[1] for item in view_specs)
        self._db            = db
        self._view_registry = view_registry
        self._view_class    = view_class

    def add_viewspec(self, spec):
        self._view_specs.add(spec)

    def remove_viewspec(self, spec):
        self._view_specs.remove(spec)


class BidirectionalGossipHarvester(Harvester):
    MSG_SPECS = 1
    MSG_NODES = 2

    def __init__(self, io, local_node, *args):
        Harvester.__init__(self, *args)
        self.io = io
        self.local_node = local_node
        io.subscribe(self.MSG_SPECS, self.receive_specs)
        io.subscribe(self.MSG_NODES, self.receive_nodes)

    def send_specs(self, to_node):
        dlist = defer.gatherResults([ view.iterNodes()
                                      for view in self._views ])

        def send(node_iterators):
            nodes = set(chain(*node_iterators))
            nodes.add(self.local_node)
            self.io.send(self.MSG_SPECS, to_node, (self._view_specs, nodes))
        dlist.addCallback(send)
        return dlist

    def send_nodes(self, to_node, nodes):
        self.io.send(self.MSG_NODES, to_node, nodes)

    def receive_specs(self, msg_type, from_node, (view_specs, nodes)):
        node_matches = set( (self.local_node,) )
        deferreds = map(self._db.select_nodes, view_specs)
        for deferred in deferreds:
            deferred.addCallback(node_matches.update)

        def send_back(_):
            self.send_nodes(from_node, node_matches)
        def add_nodes(_):
            self._db.add_nodes(nodes)

        dlist = defer.DeferredList(deferreds, consumeErrors=True)
        dlist.addCallback(add_nodes)
        dlist.addCallback(send_back)

        return dlist

    def receive_nodes(self, msg_type, from_node, nodes):
        return self._db.add_nodes(nodes)
