__all__ = ('DotVisual')

from visual import *
from dot import *
from view_viz import ViewGraph, Edge, Node

NODE_RADIUS = 40
EDGE_RADIUS =  2
NODE_COLOUR = (0.8, 0.8, 0.8)


class VisualEdge(Edge):
    def remove(self):
        if hasattr(self, 'edge_arrow'):
            self.edge_arrow.visible = False
            del self.edge_arrow

class VisualNode(Node):
    def remove(self):
        if hasattr(self, 'node_sphere'):
            self.node_sphere.visible = False
            del self.node_sphere
        if hasattr(self, 'node_label'):
            self.node_label.visible = False
            del self.node_label

class VisualViewGraph(ViewGraph):
    def __init__(self, node_views_tuples, program='dot', **kwargs):
        self.placement_done = False
        ViewGraph.__init__(self, node_views_tuples, **kwargs)

        graph = self.graph
        graph.place_all(prog=program)

        self.placement_done = True

        self.display = new_display = display(title=graph.name, width=600, height=600)
        new_display.background = (0.3, 0.3, 0.3)
        new_display.select()
        new_display.exit = 0

        size = graph.graphsize
        self.offset = vector( (size[2] - size[0]) // 2, (size[3] - size[1]) // 2 )

        self.graph = graph
        for node in graph.nodes:
            self.create_visual_node(node)
        for edge in graph.edges:
            try: weight = edge.get('weight')
            except KeyError: weight = None
            self.create_visual_edge(edge, weight)

    def build_edge(self, local_node_name, node_name, **kwargs):
        edge = VisualEdge(local_node_name, node_name, **kwargs)
        if self.placement_done:
            self.create_visual_edge(edge, kwargs.get('weight'))
        return edge

    def build_node(self, node_name):
        return VisualNode(node_name)

    def create_visual_node(self, node):
        pos = vector(node.get('pos')) - self.offset
        node.node_label = label(pos=pos, text=node.name, box=0, line=0, opacity=0,
                                space=NODE_RADIUS, height=7, xoffset=-30, yoffset=0)

        node.node_sphere = cylinder(pos=pos, axis=(0,0,1000),
                                    radius=NODE_RADIUS, color=NODE_COLOUR)

    def create_visual_edge(self, edge, height=None):
        if height:
            offset = self.offset - vector(0, 0, height) * 10
        else:
            offset = self.offset
        nodes = self.graph.node_dict
        start_node = nodes[edge.from_node]
        end_node   = nodes[edge.to_node]

        start_pos = vector( start_node.get('pos') )
        end_pos   = vector(   end_node.get('pos') )
        arrow_vec = ( end_pos - start_pos )

        colour = color.hsv_to_rgb( tuple(map(float, edge.get('color').split(','))) )
        edge.edge_arrow  = arrow(pos=start_pos-offset, axis=arrow_vec, shaftwidth=EDGE_RADIUS, color=colour)
