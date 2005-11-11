from itertools import *
from math import pi, cos, sin, sqrt
import colorsys

import Image, ImageDraw

try:
    from psyco.classes import *
except ImportError:
    pass

try:
    from optimize import bind_all
except:
    def bind_all(*args, **kwargs):
        pass

from view_viz import ViewGraph


class ViewCircleSnapshot(ViewGraph):
    def __init__(self, node_views_tuples, **kwargs):
        self.__spread_nodes = self.__silent
        ViewGraph.__init__(self, node_views_tuples, **kwargs)
        self.positions = {}
        self.__spread_nodes = self._spread_nodes
        self.__spread_nodes(None)

    def build_edges_from_views(self, node_name, views):
        deferred = super(ViewCircleSnapshot,self).build_edges_from_views(node_name, views)
        deferred.addCallback(self.__spread_nodes)
        return deferred

    def __silent(self, _):
        pass

    def _spread_nodes(self, _):
        nodes = self.graph.nodes
        node_count = float(len(nodes))
        pi_div_2 = pi/2
        pi_mul_2 = pi*2

        max_name_len = max( len(node.name) for node in nodes )
        name_width = max_name_len * 8
        radius = sqrt(node_count) * name_width

        self.name_width = name_width
        size = int(2 * radius + name_width)
        self.image_size = (size, size)

        def decluster(angle, cos_val):
            if angle == 0:
                return 0
            elif angle > pi:
                return -cos_val
            else:
                return cos_val

        self.positions = pos = {}
        middle = size / 2
        for i, node in enumerate(nodes):
            angle = (pi_mul_2 * i) / node_count
            sin_val = sin(angle)
            cos_val = cos(angle)
            pos[node.name] = (
                middle + radius*sin_val + name_width//2 * decluster(angle, cos_val**8),
                middle - radius*cos_val
                )

    def snapshot(self):
        graph = self.graph

        white = (255,255,255)
        black = (  0,  0,  0)

        edge_dict = {}
        for edge in graph.edges:
            try:
                edge_dict[edge.from_node].append(edge)
            except KeyError:
                edge_dict[edge.from_node] = [edge]

        image = Image.new("RGB", self.image_size, white)
        draw  = ImageDraw.Draw(image)

        def convert_colour_string(edge_colour):
            hsv = map(float, edge_colour.split(','))
            rbg = tuple( int(round(c*256)) for c in hsv_to_rgb(*hsv) )
            return rbg

        hsv_to_rgb = colorsys.hsv_to_rgb
        positions = self.positions
        for node in graph.nodes:
            from_node_name = node.name
            if from_node_name not in edge_dict:
                continue

            from_pos = positions[from_node_name]
            for edge in edge_dict[from_node_name]:
                to_node_name = edge.to_node

                colour = convert_colour_string(edge.get('color'))
                draw.line([from_pos, positions[to_node_name]], fill=colour)

        for node in graph.nodes:
            node_name = node.name

            pos       = positions[node_name]
            text_size = draw.textsize(node_name)
            half_text_size = (text_size[0] / 2, text_size[1] / 2)

            ellipse_pos = (pos[0] - half_text_size[0],
                           pos[1] -      text_size[1],
                           pos[0] + half_text_size[0],
                           pos[1] +      text_size[1])
            draw.ellipse(ellipse_pos, fill=white, outline=black)

            text_pos = (pos[0] - half_text_size[0], pos[1] - half_text_size[1])
            draw.text(text_pos, node_name, fill=black)

        del draw
        return image

import sys
bind_all(sys.modules[__name__])
