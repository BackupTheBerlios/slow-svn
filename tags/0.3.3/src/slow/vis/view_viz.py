import os, re, random, math, operator
from itertools import imap, chain, repeat

def build_colour_table():
    "Build a list of colours with decreasing colour distance"
    colours = ["0.0,1.0,0.8"]
    power_step = 1.0
    for power in xrange(7): # 1094 entries should be enough
        power_step *= 2.0
        colours.extend( "%.3f,1.0,0.8" % (step/power_step)
                        for step in xrange(1,int(power_step),2) )
    return colours

COLOUR_TABLE = build_colour_table()


class ViewGraph(object):
    def __init__(self, node_views_tuples, **kwargs):
        self._build_graph(node_views_tuples, **kwargs)
        # FIXME: return

    @classmethod
    def write_files(cls, node_views_tuples, program='dot', fname='test', **kwargs):
        view_graph = cls(node_views_tuples, **kwargs)
        view_graph.graph.write_dot(fname, prog=program)
        view_graph.graph.write_ps (fname, prog=program, size="6,6")

    def _build_graph(self, node_views_tuples, **kwargs):
        graph_name = kwargs.get('graph_name') or 'Views'
        self.graph = graph = Dot(graph_name=graph_name, ordering='out', **kwargs)

        for (node_name, views) in node_views_tuples:
            graph.add_node( self.build_node(str(node_name)) )

        def random_colour():
            choice  = random.choice
            while True:
                yield choice(COLOUR_TABLE)

        # never ending story...
        next_colour = chain(COLOUR_TABLE,
                            imap(random.choice, repeat(COLOUR_TABLE))).next
        colour_map = {}

        build_edges_from_views = self.build_edges_from_views
        for node, views in node_views_tuples:
            build_edges_from_views(str(node), views,
                                   colour_map, next_colour)

    def rebuild_edges_from_views(self, node_name, views):
        vnode = self.graph.node_dict[node_name]
        self.graph.remove_edges_of_node(vnode)
        self.build_edges_from_views(node_name, views)

    def build_edges_from_views(self, node_name, views,
                               colour_map, next_colour):
        build_edges = self.build_edges
        graph       = self.graph

        def build_bucket_edges(bucket_iterator, view_name, node_name):
            for weight, (var_values, nodelist) in enumerate(bucket_iterator):
                weight = 100 // (weight+1)
                colour_key = (view_name,) + var_values
                try:
                    colour = colour_map[colour_key]
                except KeyError:
                    colour = colour_map[colour_key] = next_colour()
                build_edges(graph, node_name, nodelist,
                            color=colour, weight=weight)

        for view in views:
            build_bucket_edges(view.iterBuckets(), view.name, node_name)

    def build_edges(self, graph, local_node, nodes, **kwargs):
        for node in nodes:
            edge = self.build_edge(local_node, str(node), **kwargs)
            graph.add_edge(edge)

    def build_edge(self, from_node_name, to_node_name, **kwargs):
        return Edge(from_node_name, to_node_name, **kwargs)

    def build_node(self, node_name):
        return Node(node_name)


class DotLayoutParser(object):
    re_graphsize = re.compile('^\s*graph\s*\[.*bb="([0-9]+),([0-9]+),([0-9]+),([0-9]+)".*\]')
    re_node      = re.compile('^\s*"([^"]+)"\s*\[([^\]]+)\]')
    re_edge      = re.compile('^\s*"([^"]+)"\s*(<?->?)\s*"([^"]+)"\s*\[([^\]]+)\]')
    re_options   = re.compile('(\w+)\s*=\s*(?:(?:"([^"]*)")|(?:\w+))')

    _searched_options = frozenset( ('pos', 'width', 'height') )

    @staticmethod
    def convert(item):
        try: return int(item)
        except: pass
        try: return float(item)
        except: pass
        return item

    @classmethod
    def parse_options(cls, options):
        result = {}
        convert = cls.convert
        for opt, value in cls.re_options.findall(options):
            if opt not in cls._searched_options:
                continue
            parts = tuple( tuple(convert(e) for e in part.split(','))
                           for part in value.split(' ') )
            try:
                while len(parts) == 1:
                    parts = parts[0]
            except TypeError:
                pass
            result[opt] = parts
        return result

    @classmethod
    def parse(cls, dot_code):
        graphsize = None
        nodes = {}
        edges = {}
        for line in dot_code:
            p_graphsize = cls.re_graphsize.match(line)
            if p_graphsize:
                graphsize = map(int, p_graphsize.groups())
                continue
            p_node = cls.re_node.match(line)
            if p_node:
                node_name, options = p_node.groups()
                nodes[node_name] = cls.parse_options(options)
                continue
            p_edge = cls.re_edge.match(line)
            if p_edge:
                edge_from, direction, edge_to, options = p_edge.groups()
                edges[ (edge_from, edge_to) ] = cls.parse_options(options)
                continue
        return (graphsize, nodes, edges)


class Dot(object):
    def __init__(self, graph_name, **kwargs):
        self.name = graph_name
        self.args = kwargs
        self.nodes = []
        self.node_dict = {}
        self.edges = []
        self.edge_dict = {}

    def add_node(self, node):
        if node.name not in self.node_dict:
            self.nodes.append(node)
            self.node_dict[node.name] = node

    def add_edge(self, edge):
        edge_tuple = (edge.from_node, edge.to_node)
        if edge_tuple not in self.edge_dict:
            self.edges.append(edge)
            self.edge_dict[(edge.from_node,edge.to_node)] = edge

    def remove_edge(self, edge):
        edge.remove()
        self.edges.remove(edge)
        del self.edge_dict[(edge.from_node,edge.to_node)]

    def remove_edges_of_node(self, node):
        node_name = node.name
        old_edges = []
        edge_dict = self.edge_dict
        append = old_edges.append
        for i, edge in enumerate(self.edges):
            if edge.from_node == node_name:
                edge.remove()
                del edge_dict[(edge.from_node, edge.to_node)]
                append(i)

        edges = self.edges
        for pos in reversed(old_edges):
            del edges[pos]

    def remove_node(self, node):
        self.remove_edges_of_node(node)
        node.remove()
        self.nodes.remove(node)
        del self.node_dict[node.name]

    def edge_weight(self, edge):
        try:
            return edge.args['weight']
        except KeyError:
            return 0

    def generate_dot(self, f, **kwargs):
        f.write('digraph %s {\n' % self.name)
        for item in chain(self.args.iteritems(), kwargs.iteritems()):
            f.write('%s = "%s"\n' % item)
        for node in self.nodes:
            f.write("%r\n" % node)
        for edge in sorted(self.edges, key=self.edge_weight, reverse=True):
            f.write("%r\n" % edge)
        f.write('}')

    def _run_dot(self, prog, out_type, **kwargs):
        dot_out, dot_in = os.popen2('%s -T%s' % (prog, out_type), 'rw')
        self.generate_dot(dot_out, **kwargs)
        dot_out.close()
        return dot_in

    def write(self, out_type, filename, prog='dot', **kwargs):
        if filename[-len(out_type):] != out_type:
            filename += '.' + out_type
        output = self._run_dot(prog, out_type, **kwargs)
        f = open(filename, 'w')
        f.write(output.read())
        f.close()

    def tostring(self, out_type, prog='dot', **kwargs):
        output = self._run_dot(prog, out_type, **kwargs)
        return output.read()

    def place_all(self, prog='dot', **kwargs):
        dot_out, dot_in = os.popen2('%s -Tdot' % prog, 'rw')
        self.generate_dot(dot_out, **kwargs)
        dot_out.close()

        self.graphsize, node_attributes, edge_attributes = DotLayoutParser.parse(dot_in)
        dot_in.close()
        for name, attributes in node_attributes.iteritems():
            try:
                for attr, value in attributes.iteritems():
                    self.node_dict[name].set(attr, value)
            except KeyError:
                pass

        for edge_nodes, attributes in edge_attributes.iteritems():
            try:
                for attr, value in attributes.iteritems():
                    self.edge_dict[edge_nodes].set(attr, value)
            except KeyError:
                pass

    def __getattr__(self, attr):
        if attr.startswith('write_'):
            write = self.write
            return (lambda *args, **kwargs : write(attr[6:], *args, **kwargs))
        else:
            return super(Dot, self).__getattr__(attr)


class Node(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.args = kwargs

    def set(self, attr, value):
        self.args[attr] = value

    def get(self, attr):
        return self.args[attr]

    def remove(self):
        pass

    def __eq__(self, other):
        return other is not None and other.name == self.name

    def __repr__(self):
        return '"%s" [%s]' % (self.name, ', '.join('%s="%s"' % item
                                                   for item in self.args.iteritems()))

class Edge(object):
    def __init__(self, from_node, to_node, **kwargs):
        self.from_node, self.to_node = from_node, to_node
        self.args = kwargs

    def set(self, attr, value):
        self.args[attr] = value

    def get(self, attr):
        return self.args[attr]

    def remove(self):
        pass

    def __eq__(self, other):
        return (other is not None and
                other.from_node, other.to_node == self.from_node, self.to_node)

    def __repr__(self):
        return '"%s" -> "%s" [%s]' % (self.from_node, self.to_node,
                                      ', '.join('%s="%s"' % item
                                                for item in self.args.iteritems()))

