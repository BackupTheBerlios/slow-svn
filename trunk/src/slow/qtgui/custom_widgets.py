import re, os
#from itertools import *

import qt
from itertools import *
import operator, math
from qt_utils import ProcessManager, py_signal_signature, qstrpy, pyqstr


class SelectiveCustomWidget(object):
    """Base class for custom widgets that select their application by
    widget name."""
    def __new__(cls, parent, name, *args):
        use_class = True
        if hasattr(cls, '_INCLUDED_WIDGET_NAMES'):
            use_class = name in cls._INCLUDED_WIDGET_NAMES
        if hasattr(cls, '_EXCLUDED_WIDGET_NAMES'):
            use_class = use_class and not name in cls._EXCLUDED_WIDGET_NAMES

        if hasattr(cls, '_TYPE_MAPPING'):
            try:
                cls = cls._TYPE_MAPPING[name]
            except KeyError:
                pass

        if use_class:
            return super(SelectiveCustomWidget, cls).__new__(cls, parent, name, *args)
        else:
            mro = iter( type.mro(cls) )
            while mro.next() != cls:
                pass
            superclass = mro.next()
            while not issubclass(superclass, qt.QWidget):
                superclass = mro.next()
            return superclass(parent, name, *args)


class ArrowPainter(qt.QPainter):
    START_PEN = qt.QPen(qt.Qt.yellow, 2)
    def drawArrow(self, p_from, p_to, pen=None):
        vector = p_to - p_from
        #angle  = math.atan(vector.y() / vector.x())
        #print angle
        split = p_from + vector/3

        old_pen = self.pen()
        if not old_pen:
            self.save()

        self.setPen(self.START_PEN)
        self.drawLine(p_from, split)
        if pen:
            self.setPen(pen)
        self.drawLine(split, p_to)

        if old_pen:
            self.setPen(old_pen)
        else:
            self.restore()


class DotWriter(object):
    def __init__(self, parent, prog='dot', format='svg', name=None):
        self.graph_name = name
        self.parent = parent
        self.prog   = prog
        self.format = format

    def init_colours(self, colours_by_type):
        self.colours_by_type = colours_by_type

    def generate_for_callback(self, call_back, edsm_model, **kwargs):
        dot_out = ProcessManager(
            self.parent, call_back, self.prog, '-T%s' % self.format)
        self.write_dot(dot_out, edsm_model, **kwargs)
        dot_out.close()

    def generate(self, edsm_model, **kwargs):
        dot_out, data_in = os.popen2('%s -T%s' % (self.prog, self.format), 'rw')
        self.write_dot(dot_out, edsm_model, **kwargs)
        dot_out.close()
        return data_in.read()

    def write_dot(self, f, edsm_model, name=None, **kwargs):
        if name is None:
            name = self.graph_name or 'edsm_graph'

        f.write('digraph %s {\n' % name)
        self.write_graph(f, edsm_model, **kwargs)
        f.write('}')

    def write_graph(self, f, edsm_model, **kwargs):
        write = f.write
        write( u''.join(
            u'%s = "%s"\n' % item for item in kwargs.iteritems()
            ).encode('utf-8') )

        dispatch = {
            'subgraph' : self.subgraph_to_dot,
            'state'    : self.state_to_dot
            }
        for state_or_subgraph in edsm_model.states:
            dispatch[state_or_subgraph.type_name]( f, state_or_subgraph )

        write( u'\n'.join(
            u"%s\n" % c for c in imap(self.connection_to_dot, edsm_model.transitions)
            ).encode('utf-8') )

    class Attributes(list):
        def __init__(self, **kwargs):
            list.__init__(self)
            self.extend(kwargs.iteritems())
        def add(self, **kwargs):
            self.extend(kwargs.iteritems())
        def __repr__(self):
            return u', '.join(u'%s = "%s"' % item for item in self)

    def attributes(self, **attributes):
        return u', '.join(u'%s = "%s"' % attr
                         for attr in attributes.iteritems())

    def split_name(self, name, pos=20):
        length = 0
        line = []
        lines = [line]
        for part in name.split():
            l = len(part)
            length += l
            if length <= pos:
                line.append(part)
            else:
                line = [part]
                lines.append(line)
                length = l
        return u'\\n'.join(u' '.join(line) for line in lines)

    def connection_to_dot(self, connection):
        colour = self.colours_by_type[connection.type_name]
        attributes = self.Attributes(color=colour,
                                     fontcolor='gray', fontsize='6')

        cname = connection.readable_name
        if cname:
            if len(cname) > 12:
                cname = self.split_name(cname, 12)
            attributes.add(label=cname)
        from_queue = connection.from_queue
        if from_queue and from_queue != 'output':
            attributes.add(taillabel=from_queue,
                           labelfontcolor='black')
        to_queue = connection.to_queue
        if to_queue and to_queue != 'input':
            attributes.add(headlabel=to_queue,
                           labelfontcolor='black')

        return u'"%s" -> "%s" [%s]' % (
            connection.from_state.id,
            connection.to_state.id,
            attributes
            )

    def state_to_dot(self, f, state):
        node_name = self.split_name(state.readable_name, 15)
        attributes = self.Attributes(fontsize='8', label=node_name)

        name = state.name
        if name == 'start':
            attributes.add(shape=u'box')

        f.write((u'"%s" [%s]\n' % (state.id, attributes)).encode('utf-8'))

    def subgraph_to_dot(self, f, subgraph):
        graph_name = self.split_name(subgraph.readable_name, 15)

        write = f.write
        write(('subgraph cluster_%s {\n' % subgraph.id).encode('utf-8'))
        self.write_graph(f, subgraph, fontsize='8', label=graph_name)
        write('}\n')


class DotGraphWidget(qt.QWidget):
    RE_VIEWBOX = re.compile('<svg[^>]+viewBox\s*=\s*"([^"]*)"')
    def __init__(self, *args):
        self._picture = qt.QPicture()
        self._paint_rect = None
        self._graph_generator = DotWriter(self, format='svg')
        self.init_colours = self._graph_generator.init_colours
        qt.QWidget.__init__(self, *args)

        self.rebuild_running = False
        self.reschedule = False
        self._editor = None
        self._use_splines = 'false'

    def set_editor(self, editor):
        self._editor = editor

    def set_splines(self, splines_on):
        self._use_splines = splines_on and 'true' or 'false'

    @py_signal_signature("rebuild_graph()")
    def rebuild_graph(self):
        if self.rebuild_running:
            self.reschedule = True
            return

        if not self._editor:
            return

        self._graph_generator.generate_for_callback(
            self.set_image_data, self._editor.edsm_model,
            splines=self._use_splines
            )

        self.rebuild_running = True

    def set_image_data(self, image_data):
        self.rebuild_running = False

        if self.reschedule:
            self.reschedule = False
            self.rebuild_graph()

        if not image_data:
            return

        self._paint_rect = None
        for match in self.RE_VIEWBOX.finditer(image_data):
            try:
                self._paint_rect = map(float, match.group(1).split())
                if len(self._paint_rect) != 4:
                    self._paint_rect = None
            except ValueError:
                pass
            break

        image_buffer = qt.QDataStream(qt.QByteArray(image_data), qt.IO_ReadOnly)
        self._picture.load(image_buffer.device(), 'svg')
        self.update()

    def paintEvent(self, event):
        painter  = qt.QPainter(self)
        own_rect = self.rect()

        painter.drawLine(own_rect.topLeft(), own_rect.topRight())
        painter.drawLine(own_rect.topLeft(), own_rect.bottomLeft())

        if self._picture:
            rect = self._paint_rect
            if rect:
                painter.translate(rect[0], rect[1])
                painter.scale(own_rect.width() / rect[2], own_rect.height() / rect[3])
            self._picture.play(painter)
        else:
            painter.drawLine(own_rect.topLeft(),  own_rect.bottomRight())
            painter.drawLine(own_rect.topRight(), own_rect.bottomLeft())

    def mousePressEvent(self, event):
        self.rebuild_graph()


class IterableListView(SelectiveCustomWidget, qt.QListView):
    def iterColumnItems(self):
        next_item = self.firstChild()
        while next_item:
            yield next_item
            next_item = next_item.nextSibling()

    def iterSelectedItems(self):
        return (item for item in self.iterColumnItems()
                if item.isSelected())

    def iterColumns(self):
        column_numbers = range(self.columns())
        for item in self.iterColumnItems():
            yield map(qstrpy, map(item.text, column_numbers))

    __iter__ = iterColumns


class IterableComboBox(SelectiveCustomWidget, qt.QComboBox):
    def __iter__(self):
        text = self.text
        count = self.count
        i = 0
        while i < count():
            yield text(i)
            i += 1

    def __contains__(self, qstring):
        text = self.text
        for i in range(self.count()):
            if qstring == text(i):
                return True
        return False


class EDSMIconView(SelectiveCustomWidget, qt.QIconView):
    def __init__(self, *args):
        self.connections = set()
        self.static_items = {}
        qt.QIconView.__init__(self, *args)
        self.setAutoArrange(False)

        self.__max_dist       = 30
        self.__max_close_dist = 4

    def getMaxDist(self):
        return self.__max_dist
    def setMaxDist(self, max_dist):
        self.__max_dist = max_dist
    max_dist = property(getMaxDist, setMaxDist)

    def getMaxCloseDist(self):
        return self.__max_close_dist
    def setMaxCloseDist(self, max_close_dist):
        self.__max_close_dist = max_close_dist
    max_close_dist = property(getMaxCloseDist, setMaxCloseDist)

    @property
    def states(self):
        return tuple(self.iterstates())

    def iterstates(self):
        next_item = self.firstItem()
        while next_item:
            yield next_item
            next_item = next_item.nextItem()

    def iterconnections(self, m_type=None):
        if m_type:
            return (connection for connection in self.connections
                    if connection.type == m_type)
        else:
            return iter(self.connections)

    def reset_connections(self):
        self.connections = set()

    def reset_static_states(self, static_items):
        self.static_items = static_items

    def clear(self):
        for item in self.states:
            self.takeItem(item)

    def viewportPaintEvent(self, event):
        qt.QIconView.viewportPaintEvent(self, event)

        painter = ArrowPainter(self.viewport())
        black = qt.Qt.black
        for connection in self.connections:
            source, dest = connection.from_state, connection.to_state
            pen = connection.colour

            p_from = self.contentsToViewport(source.pixmapRect(False).center())
            p_to   = self.contentsToViewport(dest.pixmapRect(False).center())
            painter.drawArrow(p_from, p_to, pen)

    def contentsDropEvent(self, event):
        self.viewport().update()
        qt.QIconView.contentsDropEvent(self, event)

    def add_connection(self, connection):
        self.connections.add(connection)
        self.viewport().update()

    def remove_connection(self, connection):
        self.connections.discard(connection)
        self.viewport().update()

    def __scal_prod(self, p1, p2):
        return float(p1.x()*p2.x() + p1.y()*p2.y())

    def __scal_sqr(self, p):
        return float(p.x()**2 + p.y()**2)

    def globalToContents(self, pos):
        return self.viewportToContents(self.mapFromGlobal(pos))

    def contentsToGlobal(self, pos):
        return self.mapToGlobal(self.contentsToViewport(pos))

    def connections_at(self, pos, prefer_type=None, restrict_type=None):
        if restrict_type is None:
            connections = self.connections
        else:
            connections = (c for c in self.connections
                           if c.type == restrict_type)

        sqrt = math.sqrt
        scal_prod = self.__scal_prod
        scal_sqr  = self.__scal_sqr
        candidates = []
        for i, connection in enumerate(connections):
            p_from = connection.from_state.pixmapRect(False).center()
            p_to   = connection.to_state.pixmapRect(False).center()
            # d(g:f->t, P) = | f - p + (t-f) * [ ((t-f)*(p-f))/(t-f)^2 ] |
            conn_vector   = p_to - p_from
            source_vector = pos  - p_from
            length_factor = scal_prod(conn_vector, source_vector) / scal_sqr(conn_vector)
            if length_factor >= 0 and length_factor <= 1:
                dist_vector = conn_vector * (length_factor * 100) - source_vector * 100
                dist = sqrt( dist_vector.x()**2 + dist_vector.y()**2 ) / 100
                source_dist = source_vector.manhattanLength()
                candidates.append( (dist, source_dist, i, connection) )

        candidates.sort()

        if not candidates or candidates[0][0] > self.__max_dist:
            return ()
        elif len(candidates) == 1:
            return (candidates[0][-1],)

        # if there's more than one, sort by distance to its source
        max_dist = candidates[0][0] + self.__max_close_dist
        close_connections = [
            c[-1] for c in sorted( \
                takewhile((lambda c: c[0] <= max_dist), candidates),
                key=operator.itemgetter(1) # source_dist
                )
            ]

        # take the closest item
        # use the preferred type if there is one
        if prefer_type is not None:
            best_connections = [ c for c in close_connections
                                 if connection.type == prefer_type ]
            if best_connections:
                return best_connections

        return close_connections

    def update(self):
        self.viewport().update()
        qt.QIconView.update(self)

    def takeItem(self, item):
        remove = []
        for connection in self.connections:
            if item in (connection.from_state, connection.to_state):
                remove.append(connection)
        for del_item in remove:
            self.connections.discard(del_item)

        self.viewport().update()
        qt.QIconView.takeItem(self, item)

