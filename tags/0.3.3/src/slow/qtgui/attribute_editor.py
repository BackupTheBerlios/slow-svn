import sys, logging, math
from itertools import *

import qt
from qttable import QComboTableItem

from qt_utils import pyqstr, qstrpy, FlagMaintainerListItem
from custom_widgets import IterableListView

from lxml import etree

from slow.model import sqldata_model
from slow.model.attribute_model import buildTypes, buildAttribute, buildAttributes, DB_NAMESPACE_URI
from slow.model.sqldata_model   import SIMPLE_TYPES, ALL_TYPES, SQL_NAMESPACE_URI

class AttributeListItem(FlagMaintainerListItem):
    pass

class AttributeDragObject(qt.QTextDrag):
    MIME_SUBTYPE = 'attribute-name'
    def __init__(self, text, source):
        qt.QTextDrag.__init__(self, text, source)
        self.setSubtype(self.MIME_SUBTYPE)

class DraggableAttributeListView(IterableListView):
    def dragObject(self):
        return AttributeDragObject( self.currentItem().text(0), self )

    def resizeEvent(self, event):
        IterableListView.resizeEvent(self, event)

        width = event.size().width() - self.lineWidth()
        col_width = (width * 3) / 5
        self.setColumnWidth(0, col_width)
        self.setColumnWidth(1, width - col_width)


class AttributeEditor(object):
    __FLAG_NAMES = ('static', 'transferable', 'identifier')
    def __init__(self):
        self.__setup_child_calls()
        self.__init_models()
        self.__init_type_selectors()
        self.__init_text_verifiers()
        self.__init_views()

    def __setup_child_calls(self):
        try:
            self.__setStatus = self.setStatus
        except AttributeError:
            def dummy(*args):
                pass
            self.__setStatus = dummy

        try:
            self.__tr = self.tr
        except AttributeError:
            def dummy(self, arg):
                return arg
            self.__tr = dummy

    def __init_models(self):
        self.__custom_data_types = buildTypes()
        self._attribute_descriptions = buildAttributes()

    def __init_type_selectors(self):
        length_attrs = self.__LENGTH_ATTRIBUTES = dict(chain(
            [ ('decimal', 'bits'), ('text', 'maxlength') ],
            ((name, 'maxval') for name in ('smallint', 'integer', 'bigint')),
            ((name, 'length') for name in ('char', 'array', 'bytea'))
            ))

        length_frame = self.attribute_type_length_frame
        configurators = self.TYPE_CONFIGURATORS = {
            'array'     : [ self.attribute_type_subtype_frame   ],
            'composite' : [ self.attribute_type_composite_table ]
            }

        for name in length_attrs.iterkeys():
            try:
                configs = configurators[name]
                configs.append(length_frame)
            except KeyError:
                configurators[name] = [length_frame]

    def __init_text_verifiers(self):
        validator = self.identifier_validator
        for field in (self.node_attribute_name, self.type_name_field):
            field.setValidator(validator)

    def __init_views(self):
        self.attribute_type_range_frame.hide() # not currently used
        self.set_available_type_names()

        self.attribute_type_select.clear()
        all_types = self._all_type_names()
        self.attribute_type_select.insertStrList(sorted(all_types))

        type_names = qt.QStringList(u'')
        for name in SIMPLE_TYPES:
            type_names.append(name)

        table = self.attribute_type_composite_table
        #table.verticalHeader().hide()
        #table.setLeftMargin(0)

        #table.setColumnStretchable(0, True)
        table.setColumnStretchable(1, True)

        table.setNumRows(25)
        for i in range(25):
            table.setText(i, 0, u'')
            table.setItem(i, 1, QComboTableItem(table, type_names))
            table.setRowStretchable(i, True)
            table.adjustRow(i)

    def _all_type_names(self):
        return frozenset(chain(ALL_TYPES, self.__custom_data_types.type_names))

    def reset_datatype_descriptions(self, types_model):
        self.__custom_data_types = types_model
        self.set_available_type_names()

    def set_available_type_names(self, type_names=None):
        if type_names is None:
            type_names = sorted(self._all_type_names())
        else:
            type_names.sort()

        self.node_attribute_type.clear()
        self.node_attribute_type.insertStrList(type_names)

        simple_type_names = qt.QStringList()
        for type_name in type_names:
            if type_name not in ('composite', 'array'):
                simple_type_names.append(type_name)

        self.attribute_type_subtype_select.clear()
        self.attribute_type_subtype_select.insertStringList(simple_type_names)

        simple_type_names.sort()
        simple_type_names.prepend( u'' )

        table = self.attribute_type_composite_table
        for row in range(table.numRows()):
            combobox = table.item(row, 1)
            combobox.setStringList(simple_type_names)

    class HighlightedFirstColumnListItem(AttributeListItem):
        TEXT_COLOUR = qt.Qt.red.light(120)
        BG_COLOUR   = qt.Qt.white.dark(110)
        def paintCell(self, painter, colour_group, column, width, align):
            if column == 0:
                font = painter.font()
                font.setBold(True)
                colour_group = qt.QColorGroup(colour_group)
                colour_group.setColor(colour_group.Base, self.BG_COLOUR)
                colour_group.setColor(colour_group.Text, self.TEXT_COLOUR)
            FlagMaintainerListItem.paintCell(
                self, painter, colour_group, column, width, align )

    def _build_attribute_list_item(self, attribute):
        item = self.HighlightedFirstColumnListItem(
            self.node_attribute_list, attribute, 'selected',
            attribute.name, attribute.type_name )
        item.setDragEnabled(True)
        item.setOpen(True)

        for flag_name in self.__FLAG_NAMES:
            child = FlagMaintainerListItem(item, attribute, flag_name)
            child.setSelectable(False)

    def reset_attribute_descriptions(self, attributes):
        self._attribute_descriptions = attributes
        attribute_list = self.node_attribute_list
        attribute_list.clear()

        build_item = self._build_attribute_list_item
        for attribute in attributes:
            build_item(attribute)

    def attribute_model(self):
        return self._attribute_descriptions

    def add_or_replace_node_attribute_clicked(self):
        a_name = qstrpy(self.node_attribute_name.text())
        if not a_name:
            self.node_attribute_name.setFocus()
            return
        a_type = qstrpy(self.node_attribute_type.currentText())
        if not a_type:
            self.node_attribute_type.setFocus()
            return

        attribute = buildAttribute(self._attribute_descriptions, a_name, a_type)

        attribute_list = self.node_attribute_list
        list_item = attribute_list.findItem(a_name, 0)
        if list_item:
            list_item.setText(1, a_type)
        else:
            self._build_attribute_list_item(attribute)

    def node_attribute_list_selectionChanged(self):
        selected_attribute = self.node_attribute_list.selectedItem()
        if selected_attribute:
            self.node_attribute_name.setText(selected_attribute.text(0))
            attr_type = selected_attribute.text(1)
            self.node_attribute_type.setCurrentText(attr_type)
            self.node_attribute_type_activated(attr_type)

        self.remove_node_attribute.setEnabled( bool(selected_attribute) )

    def remove_node_attribute_clicked(self):
        selected_attribute = self.node_attribute_list.selectedItem()
        if selected_attribute:
            name = qstrpy( selected_attribute.text() )
            self._attribute_descriptions.delAttribute(name)
            self.node_attribute_list.takeItem(selected_attribute)

    def attribute_type_add_or_replace_clicked(self):
        model = self.copy_type_to_model()
        if model:
            self.set_available_type_names()
            name = model.type_name
            self.node_attribute_type.setCurrentText(name)
            self.type_name_field_textChanged(name)

    def node_attribute_type_activated(self, name):
        name = qstrpy(name)
        if name in ALL_TYPES:
            return
        model = self.__custom_data_types.getType(name)
        base_type = model.base_type

        self.type_name_field.setText(name)
        self.attribute_type_select.setCurrentText(base_type)
        self.copy_type_from_model(base_type, model)

    def attribute_type_remove_clicked(self):
        name = qstrpy(self.type_name_field.text())
        if name in ALL_TYPES:
            self.__setStatus(self.tr("Cannot remove builtin type."))
        elif name in [ a.type_name for a in self._attribute_descriptions.itervalues() ]:
            self.__setStatus(self.tr("Cannot remove types used in attributes."))
        else:
            self.__custom_data_types.delType(name)
            type_list = self.node_attribute_type
            get_text = type_list.text
            for row in range(type_list.count()):
                if get_text(row) == name:
                    type_list.removeItem(row)
                    break
            self.type_name_field_textChanged(name)

    def node_attribute_name_textChanged(self, name):
        self.add_or_replace_node_attribute.setEnabled( bool(name) )

    def type_name_field_textChanged(self, name):
        name = str(name)
        self.attribute_type_add_or_replace.setEnabled( bool(name) )
        self.attribute_type_remove.setEnabled(self.__custom_data_types.getType(name) is not None)

    def attribute_type_select_activated(self, entry):
        self.copy_type_from_model(str(entry))

    def copy_type_to_model(self):
        all_types = self._all_type_names()
        type_name = qstrpy(self.type_name_field.text()).strip()
        if not type_name:
            self.__setStatus(self.__tr('Missing type name'))
            self.type_name_field.setFocus()
            return None

        def tag_name(element_type):
            if element_type in ALL_TYPES:
                namespace = SQL_NAMESPACE_URI
            else:
                namespace = DB_NAMESPACE_URI
            return u"{%s}%s" % (namespace, element_type)

        base_type = qstrpy(self.attribute_type_select.currentText())

        child_type = None
        if self.attribute_type_subtype_frame.isEnabled():
            child_type = qstrpy(self.attribute_type_subtype_select.currentText())

        value_dict = {u'type_name' : type_name}
        if self.attribute_type_length_frame.isEnabled():
            if self.attribute_type_length_checkbox.isChecked():
                attribute = self.__LENGTH_ATTRIBUTES[base_type]
                value = self.attribute_type_length.value()
                if attribute == 'maxval':
                    value = 1 << value
                value_dict[attribute] = unicode(value)

        self.__custom_data_types.delType(type_name)
        model = etree.SubElement(self.__custom_data_types, tag_name(base_type), value_dict)

        composite_table = self.attribute_type_composite_table
        if child_type:
            etree.SubElement(model, tag_name(child_type))
        elif composite_table.isEnabled():
            for row in xrange(composite_table.numRows()):
                cname = qstrpy( composite_table.text(row, 0) )
                ctype = qstrpy( composite_table.item(row, 1).currentText() )
                if cname and ctype:
                    if ctype == type_name or ctype not in all_types:
                        self.__setStatus(self.__tr('Invalid type selected: %1').arg(ctype))
                        composite_table.setFocus()
                        composite_table.selectRow(row)
                        return
                    etree.SubElement(model, tag_name(ctype), access_name=cname)

        self.__setStatus()
        return model

    def copy_type_from_model(self, attribute_type, model=None):
        if model is None:
            model = etree.SubElement(self.__custom_data_types, attribute_type)

        # clean up
        self.attribute_type_range_checkbox.setEnabled(True)
        self.attribute_type_length_checkbox.setEnabled(True)

        # set up
        configurators = self.TYPE_CONFIGURATORS.get(attribute_type, ())
        for item in frozenset(chain(*self.TYPE_CONFIGURATORS.values())):
            item.setEnabled(item in configurators)

        # special treatment of range types
        #range_min = self.attribute_type_min_range
        #range_max = self.attribute_type_max_range

        if attribute_type in (u'array', u'composite'):
            if self.attribute_type_subtype_frame.isEnabled():
                subtype = len(model) and model[0].base_type or u''
                self.attribute_type_subtype_select.setCurrentText(subtype)
            elif self.attribute_type_composite_table.isEnabled():
                table = self.attribute_type_composite_table
                for row, child in izip(range(table.numRows()),
                                       chain(model, repeat(None))):
                    if child:
                        name = child.access_name
                        base_type = child.base_type
                    else:
                        name = base_type = u''
                    table.setText(row, 0, name)
                    combobox = table.item(row, 1)
                    combobox.setCurrentItem(base_type)

        if not self.attribute_type_length_frame.isEnabled():
            return

        try:
            attribute = self.__LENGTH_ATTRIBUTES[attribute_type]
        except KeyError:
            return

        get_option = model.get
        spinbox = self.attribute_type_length
        try:
            max_bits = model.BIT_PRECISION[attribute_type]
        except (AttributeError, KeyError):
            max_bits = 256
        spinbox.setMaxValue(max_bits)

        bits = False
        value = -1
        if attribute == 'bits':
            bits  = True
            value = get_option('bits', 0)
        elif attribute == 'maxval':
            bits  = True
            value = get_option('maxval', -1)
            if value >= 0:
                log = math.log
                value = int(round( log(value) / log(2) ))
        elif attribute.endswith('length'):
            value = get_option(attribute, -1)

        value = int(value)
        if value < 0:
            value = 0
        spinbox.setValue(value)

        if bits:
            spinbox.setSuffix( u' %s' % self.tr('bits') )
        else:
            spinbox.setSuffix( u'' )
