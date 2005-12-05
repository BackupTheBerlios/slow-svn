from qt import (Qt, QWidget, QComboBox, QListBox,
                QIconViewItem, QPopupMenu, SIGNAL, PYSIGNAL)
from qt_utils import qstrpy, pyqstr, qt_signal_signature

from itertools import *

from genstatedialog      import EDSMStateDialog
from gentransitiondialog import EDSMTransitionDialog
from gentimerdialog import EDSMTimerDialog
from custom_widgets import EDSMIconView

from lxml.etree import ElementTree
from slow.xslt import STYLESHEETS

from popupmenu import MenuProvider
from slow.model.edsm_model import (
    EDSMState, EDSMTransition, buildTransition, buildState, buildSubgraph, buildEmptyModel)


class AbstractEDSMDialog(object):
    def __init__(self, parent=None, name=None, modal=0, fl=0):
        super(AbstractEDSMDialog, self).__init__(parent, name, modal, fl)
        self._edsm_editor = parent
        self.identifier_validator = parent.identifier_validator
        self.class_name_validator = parent.class_name_validator
        if hasattr(self, 'class_name'):
            self.class_name.setValidator(self.class_name_validator)

        self.field_dict = dict(
            (attr_name, (getattr(self, fieldname), getattr(self, '%s_textlabel' % fieldname)))
            for (attr_name, fieldname) in self.FIELD_MAP
            if hasattr(self, fieldname)
            )

        self.code_field_dict = dict(
            (attr_name, (getattr(self, fieldname), getattr(self, '%s_textlabel' % fieldname)))
            for (attr_name, fieldname) in self.CODE_FIELD_MAP
            if hasattr(self, fieldname)
            )

        self._code_dict = {}
        self._selected_language = None

    FIELD_MAP = (
        ('readable_name', 'object_name'),
        ('message_type',  'message_type'),
        ('from_queue',    'from_queue'),
        ('to_queue',      'to_queue'),
        ('output_queues', 'output_queues'),
        ('input_queues',  'input_queues'),
        )

    CODE_FIELD_MAP = (
        ('language',   'language_name'),
        ('code',       'init_code'),
        ('class_name', 'class_name')
        )

    def _active_fields(self):
        if isinstance(self.FIELDS, dict):
            return set(self.FIELDS[self._model.type_name])
        else:
            return set(self.FIELDS)

    def activate_fields(self):
        model = self._model
        field_names = self._active_fields()

        for field, label in chain(self.field_dict.itervalues(),
                                  self.code_field_dict.itervalues()):
            if field.name() in field_names:
                field.show()
                label.show()
            else:
                field.hide()
                label.hide()

    def collect_values(self, model_attribute, values):
        "Call *before* setModel()"
        try:
            field, label = self.field_dict[model_attribute]
        except KeyError:
            field, label = self.code_field_dict[model_attribute]

        if not isinstance(field, QComboBox):
            raise ValueError, "Only QComboBox fields are supported."

        field.clear()
        for value in values:
            field.insertItem(pyqstr(value))

    def setModel(self, dialog_model):
        self._model = dialog_model

        self.activate_fields()

        self._code_dict.clear()
        self._selected_language = None

        for attrname, (field, label) in self.field_dict.iteritems():
            try:
                value = getattr(dialog_model, attrname)
            except AttributeError:
                continue
            if isinstance(field, QComboBox):
                field.setCurrentText(value)
            elif isinstance(field, QListBox):
                field.clear()
                for line in sorted(value):
                    field.insertItem(pyqstr(line))
            else:
                field.setText(value)

        for queue_type in ('to', 'from'):
            try:
                field    = getattr(self, "%s_queue" % queue_type)
                state    = getattr(dialog_model, "%s_state" % queue_type)
                selected = getattr(dialog_model, "%s_queue" % queue_type, None)
                queues   = getattr(state, queue_type == 'to'
                                   and 'input_queues'
                                   or  'output_queues')
            except AttributeError:
                continue
            field.clear()
            for i, queue in enumerate(sorted(queues)):
                field.insertItem(pyqstr(queue))
            if selected:
                field.setCurrentText(selected)

        if hasattr(self, 'class_name'):
            self.class_name.setCurrentItem(-1)
        if hasattr(self, 'language_name'):
            self.language_name.setCurrentItem(-1)
        if hasattr(self, 'init_code'):
            self.init_code.clear()

        if hasattr(dialog_model, 'codes'):
            field = self.language_name
            lower_values = set(qstrpy(s).lower() for s in field)
            for code in dialog_model.codes:
                language = code.language
                if language and language not in lower_values:
                    field.insertItem(pyqstr(language.capitalize()))

            codes = dialog_model.codes
            self._code_dict.update( (c.language, c.code) for c in codes if c.language )

            for code in codes:
                if code.class_name:
                    self.class_name.setCurrentText(pyqstr(code.class_name))
                    break

            if codes:
                code = codes[0]
                for language in self.language_name:
                    if qstrpy(language).lower() == code.language:
                        self._selected_language = code.language
                        self.language_name.setCurrentText(language)
                        self.init_code.setText(pyqstr(code.code or ''))
                        break

    def accept(self):
        model = self._model
        field_names = self._active_fields()

        if 'language_name' in field_names and self._selected_language:
            self._code_dict[self._selected_language] = qstrpy( self.init_code.text() )

        class_name = None
        if 'class_name' in field_names:
            value = self.class_name.currentText()
            validator = self.class_name_validator
            if validator.validate(value, 0)[0] == validator.Acceptable:
                if value not in self.class_name:
                    self.class_name.insertItem(value)
                class_name = qstrpy(value)
            else:
                self.class_name.setFocus()
                return

        for attrname, fieldname in self.FIELD_MAP:
            try:
                field = getattr(self, fieldname)
            except AttributeError:
                continue
            if field.isHidden():
                continue

            if isinstance(field, QListBox):
                values = [ qstrpy(field.text(i))
                           for i in range(field.count()) ]
                setattr(model, attrname, values)
            else:
                if isinstance(field, QComboBox):
                    value = field.currentText()
                else:
                    value = field.text()
                setattr(model, attrname, qstrpy(value))

        if hasattr(model, 'codes'):
            del model.codes
            for language, code in self._code_dict.iteritems():
                if not code.strip():
                    continue
                model.setCode(language, code, class_name)

            if class_name and not model.codes:
                model.setCode('python', None, class_name)

        self.GUI_CLASS.accept(self)
        self._edsm_editor.edsm_model_updated(model)

    def language_name_activated(self, language):
        if self._selected_language:
            self._code_dict[self._selected_language] = qstrpy( self.init_code.text() )

        language = qstrpy(language).lower()
        self._selected_language = language
        try:
            code = pyqstr( self._code_dict[language] )
        except KeyError:
            self.init_code.clear()
        else:
            self.init_code.setText(code)

    def _append_to_list(self, listbox, line):
        qline = pyqstr(line)
        for i in range(listbox.count()):
            if qline == listbox.text(i):
                return
        listbox.insertItem(qline)

    def add_input_queue_button_clicked(self):
        name = qstrpy(self.queue_name.text()).strip()
        if name:
            self._append_to_list(self.input_queues, name)
    def add_output_queue_button_clicked(self):
        name = qstrpy(self.queue_name.text()).strip()
        if name:
            self._append_to_list(self.output_queues, name)

    def _remove_selected(self, listbox):
        selected = []
        for i in range(listbox.count()):
            if listbox.isSelected(i):
                selected.append(listbox.item(i))
        for item in selected:
            listbox.takeItem(item)

    def remove_input_queue_button_clicked(self):
        self._remove_selected(self.input_queues)
    def remove_output_queue_button_clicked(self):
        self._remove_selected(self.output_queues)


class AbstractTransitionDialog(AbstractEDSMDialog):
    def setTransition(self, transition):
        self.transition = transition
        self.setCaption(transition.description)
        self.setModel(transition._model)

class TransitionDialog(AbstractTransitionDialog, EDSMTransitionDialog):
    GUI_CLASS = EDSMTransitionDialog
    FIELDS = {
        'message'     : ['object_name', 'message_type', 'to_queue'],
        'event'       : ['object_name', 'event_type',   'to_queue'],
        'outputchain' : ['object_name', 'from_queue',   'to_queue'],
        'transition'  : ['object_name']
        }
    def setTransition(self, transition):
        super(TransitionDialog, self).setTransition(transition)
        self.implementation_groupbox.hide()

class StateDialog(AbstractEDSMDialog, EDSMStateDialog):
    GUI_CLASS = EDSMStateDialog
    FIELDS = ('object_name', 'class_name', 'language_name', 'init_code',
              'output_queues', 'input_queues')
    def setState(self, state):
        self.state = state
        self.setModel(state._model)


class TimerDialog(AbstractTransitionDialog, EDSMTimerDialog):
    GUI_CLASS = EDSMTimerDialog
    UNITS = (1, 1000, 60000)
    FIELDS = {'timer' : ['object_name', 'timer_delay', 'timer_delay_unit']}
    def setTransition(self, transition):
        super(TimerDialog, self).setTransition(transition)
        model = self._model
        timer_delay = model.timer_delay
        for i, unit in enumerate(self.UNITS):
            if timer_delay % unit == 0:
                timer_unit = (i, unit)

        self.timer_delay.setValue( timer_delay / timer_unit[1] )
        self.timer_delay_unit.setCurrentItem( timer_unit[0] )

    def accept(self):
        model = self._model
        model.timer_delay = self.timer_delay.value() * self.UNITS[self.timer_delay_unit.currentItem()]
        super(TimerDialog, self).accept()


class EDSMEditorItem(MenuProvider):
    def __init__(self, iconview, editor, popup_title=None):
        self._iconview, self._edsm_editor = iconview, editor
        self.tr = self._edsm_editor.tr
        MenuProvider.__init__(self, iconview, popup_title)

    def _build_popup_title(self, title):
        try:
            class_name = self._model.class_name
            if class_name:
                title = '%s (%s)' % (title, class_name)
        except AttributeError:
            pass
        return super(EDSMEditorItem, self)._build_popup_title(title)


class EDSMIconViewIcon(EDSMEditorItem, QIconViewItem):
    MODIFIABLE    = True
    FLAG_NAMES    = ()
    __FIXED_NAMES = set()
    def __init__(self, iconview, editor, model, *args, **kwargs):
        if not self.MODIFIABLE:
            self.__FIXED_NAMES.add(model.name)

        self._model = model
        EDSMEditorItem.__init__(self, iconview, editor, model.readable_name)
        QIconViewItem.__init__(self, iconview, model.readable_name, *args)

    @property
    def name(self):
        return qstrpy(self.text())

    @property
    def internal_name(self):
        return self._model.name

    @property
    def item_id(self):
        return self._model.id

    def set_model(self, model):
        self._model = model
        self.reset_popup_menu()

    def setText(self, name):
        pyname = qstrpy(name)
        if pyname in self.__FIXED_NAMES:
            return
        self._model.readable_name = pyname
        QIconViewItem.setText(self, name)
        self.set_popup_title(name)
        self._edsm_editor.edsm_model_updated(self._model)

    def update_model(self):
        name = self._model.readable_name
        QIconViewItem.setText(self, name)
        self.set_popup_title(name)
        self._edsm_editor.edsm_model_updated(self._model)

    def menu_delete(self):
        self._edsm_editor.edsm_delete_state(self)

    def add_connection(self, from_state, model):
        iconview = self._iconview
        connection = ConnectionItem(iconview, self._edsm_editor,
                                    from_state, self, model)
        iconview.add_connection(connection)

    def dropped(self, drop_event, drag_items):
        if not self.dropEnabled():
            return

        active_mode = self._edsm_editor.active_edsm_mode()
        if active_mode != 'transition':
            return

        source = self._iconview.currentItem()
        source_model = source._model
        dest_model   = self._model

        def find_ancestors(model):
            parents = []
            while model is not None and model.type_name != 'edsm':
                model = model.getparent()
                parents.append(model)
            if parents and model is None:
                parents.pop()
            return parents

        source_parents = find_ancestors(source_model)
        dest_parents   = find_ancestors(dest_model)

        closest_parent = None
        for source_parent, dest_parent in izip(reversed(source_parents), reversed(dest_parents)):
            if source_parent != dest_parent:
                break
            elif source_parent.type_name in ('edsm', 'subgraph'):
                closest_parent = source_parent

        if closest_parent is None:
            closest_parent = self._model
        transitions = closest_parent.transitions
        transition_type = self._edsm_editor.active_transition_type()
        model = buildTransition(transitions, transition_type)

        model.from_state = source._model
        model.to_state   = self._model
        self.add_connection(source, model)

        self._edsm_editor.edsm_model_updated(model)


class IconViewSubgraphIcon(EDSMIconViewIcon):
    def _populate_popup_menu(self, menu):
        tr = self.tr
        menu.insertSeparator()
        menu.insertItem(self._edsm_editor.delete_icon,
                        tr('delete'), self.menu_delete)


class IconViewStateIcon(EDSMIconViewIcon):
    def _populate_popup_menu(self, menu):
        tr = self.tr
        if self.FLAG_NAMES:
            menu.insertSeparator()
            self._build_flag_menu_area(menu, self._edsm_editor, self._model,
                                       self.FLAG_NAMES, False)
        menu.insertSeparator()
        menu.insertItem(tr('edit'), self.menu_edit)
        if self.MODIFIABLE:
            menu.insertSeparator()
            menu.insertItem(self._edsm_editor.delete_icon,
                            tr('delete'), self.menu_delete)

    def menu_edit(self):
        self._edsm_editor.edsm_edit_state(self)


class ConnectionItem(EDSMEditorItem):
    CONNECTION_COLOURS = dict(
        izip(sorted(EDSMTransition.VALID_TYPES),
            chain((Qt.black, Qt.blue, Qt.red, Qt.green, Qt.magenta),
                  repeat(Qt.black)))
        )

    def __init__(self, iconview, editor, from_state, to_state, model):
        self._model = model
        EDSMEditorItem.__init__(self, iconview, editor, '')
        self.from_state, self.to_state = from_state, to_state
        self.__hash = hash( (from_state, to_state, model.type) )
        self.type_name = self.tr(self._model.type_name)

    def __hash__(self):
        return self.__hash

    def iconView(self):
        "For compatibility with QIconViewItems."
        return self._iconview

    @property
    def type(self):
        return self._model.type

    @property
    def internal_name(self):
        return self._model.name

    @property
    def name(self):
        return self._model.readable_name

    @property
    def colour(self):
        return self.CONNECTION_COLOURS[self._model.type]

    def menu_delete(self):
        self._edsm_editor.edsm_delete_connection(self)

    def menu_edit(self):
        self._edsm_editor.edsm_edit_connection(self)

    @property
    def description(self):
        model = self._model
        return '%s: %s -> %s' % (self.tr(model.TYPENAMES[model.type]),
                                 model.from_state.readable_name,
                                 model.to_state.readable_name)

    def popup_menu(self):
        self.set_popup_title(self.description)
        return super(ConnectionItem, self).popup_menu()

    def _populate_popup_menu(self, menu):
        tr = self.tr
        if self._model.type != EDSMTransition.TYPE_TRANSITION:
            menu.insertItem(tr('edit'), self.menu_edit)
            menu.insertSeparator()
        menu.insertItem(self._edsm_editor.delete_icon,
                        tr('delete'), self.menu_delete)


class EDSMEditor(EDSMEditorItem):
    TOOL_BUTTONS     = ('edit', 'state', 'subgraph', 'transition')
    TRANSITION_TYPES = ('message', 'timer', 'event', 'outputchain', 'transition')

    STATIC_STATES = ('start',)
    SUBGRAPH_STATIC_STATES = ('entry', 'exit')

    def __init__(self):
        editor, iconview = self, self.edsm_iconview
        EDSMEditorItem.__init__(self, iconview, editor)

        # remove intermediate widget from tab 0
        tab_label = self.edsm_tabs.label(0)
        self.edsm_tabs.removePage(self.edsm_tabs.page(0))
        self.edsm_tabs.addTab(iconview, tab_label)

        self.transition_dialog = TransitionDialog(self, modal=True)
        self.timer_dialog      = TimerDialog(self, modal=True)
        self.state_dialog      = StateDialog(self, modal=True)

        self.EDSM_CLICK_FUNCTIONS = {
            'state'    : self._put_state_icon,
            'subgraph' : self._put_state_icon,
            #'message' : self._put_state_message
            }

        self.__popup_menu_showing = False

        self.__init_icons()
        self.__init_model()
        self.__init_dot()
        self.__init_tools()

    def __init_tools(self):
        self._edsm_transition_type = self.TRANSITION_TYPES[0]
        self.edsm_transition_type.setCurrentItem(0)

        self._edsm_last_button = None
        self.edsm_tool_button_toggled(True)

        tool_buttons = self.edsm_tools_buttongroup
        types = EDSMTransition.TYPES_BY_NAME
        self.TOOL_BUTTONS_BY_TYPE = dict(
            (types[transition_name], tool_buttons.find(button_id))
            for button_id, transition_name in islice(enumerate(self.TOOL_BUTTONS), 3, None)
            )

        colours = ConnectionItem.CONNECTION_COLOURS
        for transition_type, button in self.TOOL_BUTTONS_BY_TYPE.iteritems():
            button.setPaletteForegroundColor(colours[transition_type])

    def __init_icons(self):
        editor, main_iconview = self._edsm_editor, self._iconview
        icons   = self._icons   = {}
        pixmaps = self._pixmaps = {}
        for name in frozenset(chain(('state', 'subgraph'), self.STATIC_STATES, self.SUBGRAPH_STATIC_STATES)):
            icon = icons[name] = main_iconview.findItem(name)
            pixmaps[name] = icon.pixmap()
            main_iconview.takeItem(icon)

        tr = self.tr
        state_pixmap    = pixmaps['state']
        subgraph_pixmap = pixmaps['subgraph']

        class StateIcon(IconViewStateIcon):
            FLAG_NAMES = ( ('inherit_context', tr('inherit context')),
                           ('long_running',    tr('long running'))
                           )
            def __init__(self, iconview, model):
                IconViewStateIcon.__init__(self, iconview, editor,
                                           model, state_pixmap)
                self.setRenameEnabled(True)

        class SubgraphIcon(IconViewSubgraphIcon):
            def __init__(self, iconview, model):
                IconViewSubgraphIcon.__init__(self, iconview, editor,
                                              model, subgraph_pixmap)
                self.setRenameEnabled(True)

        self.StateIcon    = StateIcon
        self.SubgraphIcon = SubgraphIcon

    def __reset_iconview(self, iconview, subgraph_model, static_state_names):
        editor = self._edsm_editor
        tr = self.tr
        pixmaps = self._pixmaps
        default_pixmap = pixmaps['state']
        class SpecialStateIcon(IconViewStateIcon):
            MODIFIABLE=False
            def __init__(self, model):
                pixmap = pixmaps.get(model.name, default_pixmap)
                IconViewStateIcon.__init__(self, iconview, editor,
                                           model, pixmap)
                self.setRenameEnabled(False)

        iconview.reset_connections()
        static_items = {}
        y_pos = 10
        for state_name in static_state_names:
            readable_name = qstrpy( tr(state_name) )
            model = subgraph_model.getStateByName(state_name)
            if model is None:
                model = buildState(subgraph_model.states,
                                   state_name, readable_name)
            elif not model.readable_name:
                model.readable_name = readable_name

            item = SpecialStateIcon(model)
            item.move(10, y_pos)
            static_items[state_name] = item
            y_pos += 50

        iconview.reset_static_states(static_items)

        self.state_nr = 0

    def __init_dot(self):
        if hasattr(self, 'edsm_dot_graph'):
            self.edsm_dot_graph.set_editor(self)
            self.edsm_dot_graph.set_splines(True)
            type_names = EDSMTransition.TYPENAMES
            colours = dict( (type_names[key], str(qcolour.name()))
                            for key, qcolour in ConnectionItem.CONNECTION_COLOURS.iteritems() )
            self.edsm_dot_graph.init_colours(colours)
            self.connect(self, self.__GRAPH_CHANGED_SIGNAL, self.edsm_dot_graph.rebuild_graph)

    def __init_model(self):
        self.__edsm_model = buildEmptyModel()
        self.clear_iconviews()
        self.__reset_iconview(self._iconview, self.__edsm_model, self.STATIC_STATES)

    @property
    def edsm_model(self):
        return self.__edsm_model

    def current_iconview(self):
        return self.edsm_tabs.currentPage()

    def iconviews(self, start=0):
        return map(self.edsm_tabs.page, range(start, self.edsm_tabs.count()))

    def iconviewById(self, view_id):
        get_page = self.edsm_tabs.page
        for i in range(self.edsm_tabs.count()):
            iconview = get_page(i)
            if iconview.name() == view_id:
                return iconview
        return None

    def _store_gui_data(self, gui_data):
        for iconview in self.iconviews():
            item = iconview.firstItem()
            while item:
                gui_data.setPos(item.item_id, item.x(), item.y())
                item = item.nextItem()
        super(EDSMEditor, self)._store_gui_data(gui_data)

    def reset_edsm(self, edsm_model, icon_positions={}):
        self.__edsm_model = edsm_model
        self.clear_iconviews()
        self._build_iconview(edsm_model, self._iconview, self.STATIC_STATES, icon_positions)
        self.emit_graph_changed()

    def clear_iconviews(self):
        iconview = self._iconview

        discard_iconview = self.edsm_tabs.removePage
        for tab in self.iconviews():
            for state_item in tab.states: # keep iconview from deleting icons
                if tab is not iconview or state_item.MODIFIABLE:
                    tab.takeItem(state_item)
            if tab is not iconview:
                discard_iconview(tab)

    def _build_iconview(self, model, iconview, static_states, icon_positions={}):
        self.__reset_iconview(iconview, model, static_states)

        items_by_model_id = {}
        class_names = set()
        for state_model in model.states:
            type_name = state_model.type_name
            name = state_model.name
            if name in static_states:
                state_item = iconview.static_items[name]
                state_item.set_model(state_model)
            elif type_name == 'state':
                state_item = self.StateIcon(iconview, state_model)
            elif type_name == 'subgraph':
                state_item = self.SubgraphIcon(iconview, state_model)
                self.add_iconview_tab(name, state_model, icon_positions)
            else:
                raise TypeError, "Invalid state type '%s'." % type_name
            try:
                x,y = icon_positions[state_model.id]
                state_item.move(x,y)
            except KeyError:
                pass
            if hasattr(state_model, 'code'):
                class_name = state_model.code.class_name
                if class_name:
                    class_names.add(class_name)
            items_by_model_id[state_model.id] = state_item

        def find_item_for_model(model):
            while model.type_name != 'edsm':
                try:
                    return items_by_model_id[ model.id ]
                except (KeyError, AttributeError):
                    model = model.getparent()
            return None

        for transition_model in model.transitions:
            source_item = find_item_for_model(transition_model.from_state)
            dest_item   = find_item_for_model(transition_model.to_state)
            if source_item and dest_item:
                dest_item.add_connection(source_item, transition_model)

        class_combobox = self.state_dialog.class_name
        class_combobox.clear()
        for class_name in sorted(class_names):
            class_combobox.insertItem(class_name)

        iconview.update()

    def add_iconview_tab(self, name, model, icon_positions={}):
        if model.type_name == 'subgraph':
            static_states = self.SUBGRAPH_STATIC_STATES
        else:
            static_states = self.STATIC_STATES

        child_iconview = EDSMIconView(self.edsm_tabs, model.id)
        self.connect(child_iconview, SIGNAL("contextMenuRequested(QIconViewItem*,const QPoint&)"),
                     self.edsm_iconview_contextMenuRequested)
        self.connect(child_iconview,SIGNAL("doubleClicked(QIconViewItem*)"),
                     self.edsm_edit_state)
        self.connect(child_iconview,SIGNAL("itemRenamed(QIconViewItem*)"),
                     child_iconview.updateContents)
        self._build_iconview(model, child_iconview, static_states, icon_positions)
        self.edsm_tabs.addTab(child_iconview, model.readable_name or name)

        active_mode = self.active_edsm_mode()
        self.__connect_iconview_click(active_mode, active_mode)

    def edsm_delete_state(self, state):
        iconview = state.iconView()
        if iconview:
            iconview.takeItem(state)
        model = state._model
        if isinstance(state, IconViewSubgraphIcon):
            iconview_name = model.id
            for iconview in self.iconviews(1):
                if iconview.name() == iconview_name:
                    iconview.clear()
                    self.edsm_tabs.removePage(iconview)
        model.discard()
        self.emit_graph_changed()

    def edsm_delete_connection(self, connection):
        iconview = connection.iconView()
        if iconview:
            iconview.remove_connection(connection)
        connection._model.discard()
        self.emit_graph_changed()

    def edsm_edit_state(self, state):
        if not state:
            return
        languages = self.preferences.languages
        dialog = self.state_dialog
        dialog.collect_values('language', languages)
        dialog.setState(state)
        dialog.show()

    def find_message_paths(self, messages):
        paths = set()
        def recursive_find(model, path):
            for child in model:
                try: access_name = child.access_name
                except AttributeError:
                    access_name = None

                if access_name:
                    if child.type_name in ('header', 'container'):
                        paths.add('//' + access_name)
                    path.append(access_name)
                    paths.add( '/'.join(path) )
                    recursive_find(child, path)
                    path.pop()
                else:
                    recursive_find(child, path)

        for message in messages:
            path = '/' + message.type_name
            paths.add(path)
            recursive_find(message, [path])
        return paths

    def edsm_edit_connection(self, connection):
        if connection.type == EDSMTransition.TYPE_TIMER:
            dialog = self.timer_dialog
        else:
            dialog = self.transition_dialog

        if connection.type == EDSMTransition.TYPE_MESSAGE:
            messages = STYLESHEETS['message_builder'].apply(ElementTree(self.message_model))
            paths = self.find_message_paths(messages.getroot())
            paths.add(u'')
            dialog.collect_values('message_type', sorted(paths))

        dialog.setTransition(connection)
        dialog.show()

    def edsm_model_updated(self, model):
        if model.type_name == 'subgraph':
            iconview = self.iconviewById(model.id)
            if iconview:
                self.edsm_tabs.setTabLabel(iconview, model.readable_name or model.name)
        self.emit_graph_changed()

    __GRAPH_CHANGED_SIGNAL = PYSIGNAL('graphChanged()')
    def emit_graph_changed(self):
        if self.preferences.auto_update_edsm_graph:
            self.emit(self.__GRAPH_CHANGED_SIGNAL, ())

    @qt_signal_signature("mouseButtonPressed(int, QIconViewItem*, const QPoint&)")
    def _put_state_icon(self, button, other_item, position):
        if self.__popup_menu_showing:
            self.__popup_menu_showing = False
            return
        if other_item or button != 1:
            return

        type_name = self.active_edsm_mode()
        if type_name == 'state':
            item_class  = self.StateIcon
            build_model = buildState
        elif type_name == 'subgraph':
            item_class = self.SubgraphIcon
            build_model = buildSubgraph
        else:
            return

        iconview = self.current_iconview()
        if iconview is self._iconview:
            subgraph = self.__edsm_model
        else:
            iconview_id = iconview.name()
            subgraph = self.__edsm_model.getSubgraph(iconview_id)
            if not subgraph:
                return

        name, state_no = self.make_name_unique(type_name)
        readable_name = u'%s %02d' % (self.tr(type_name), state_no)

        model = build_model(subgraph, name, readable_name)
        item  = item_class(iconview, model)

        position = iconview.globalToContents(position)
        item.move( position.x() - item.width()/2,
                   position.y() - item.height()/2 )

        if type_name == 'subgraph':
            self.add_iconview_tab(name, model)

        iconview.setCurrentItem(item)

        self.emit_graph_changed()

    def active_edsm_mode(self):
        return self._edsm_last_button

    def active_transition_type(self):
        return self.TRANSITION_TYPES[ self.edsm_transition_type.currentItem() ]

    def make_name_unique(self, prefix):
        known_names = self.__edsm_model.used_names
        new_state_no = -1
        name = prefix
        for state_no in xrange(1, len(known_names)+1):
            name = '%s%06d' % (prefix, state_no)
            if name not in known_names:
                new_state_no = state_no
                break
        return name, new_state_no

    def find_items_at(self, global_pos, default_item=None):
        iconview = self.current_iconview()
        contents_pos = iconview.globalToContents(global_pos)

        active_button = self._edsm_last_button
        item = None
        if active_button == 'state':
            item = iconview.findItem(contents_pos)

        if item:
            return (item,)

        transition_type = self.active_transition_type()
        preferred_type = EDSMTransition.TYPES_BY_NAME.get(transition_type)
        items = iconview.connections_at(contents_pos, preferred_type)

        if items:
            return items
        elif default_item:
            return (default_item,)
        else:
            return ()

    def edsm_tool_button_toggled(self, on):
        if not on:
            return

        last_button = self._edsm_last_button
        selected = self.edsm_tools_buttongroup.selectedId()
        button = self._edsm_last_button = self.TOOL_BUTTONS[selected]

        self.__connect_iconview_click(last_button, button)

    def __connect_iconview_click(self, old_mode, new_mode):
        click_functions = self.EDSM_CLICK_FUNCTIONS
        def dummy(iconview):
            pass
        try_disconnect = connect = dummy
        try:
            f = click_functions[old_mode]
            def try_disconnect(iconview):
                try: self.disconnect(iconview, f.signal, f)
                except RuntimeError: # stupid, stupid PyQt
                    pass
        except KeyError:
            pass
        try:
            f = click_functions[new_mode]
            def connect(iconview):
                self.connect(iconview, f.signal, f)
        except KeyError:
            pass

        icons_movable = new_mode in ('edit', 'state', 'subgraph')
        for iconview in self.iconviews():
            iconview.setItemsMovable(icons_movable)
            try_disconnect(iconview)
            connect(iconview)

    def edsm_iconview_contextMenuRequested(self, item, pos):
        popup_items = self.find_items_at(pos, item)

        if not popup_items:
            self._iconview.clearSelection()
            self.edsm_tools_buttongroup.setButton(0)
            return

        has_icon = False
        for item in popup_items:
            if isinstance(item, QIconViewItem):
                has_icon = True
                break

        if not has_icon:
            self._iconview.clearSelection()

        if len(popup_items) == 1:
            popup_items[0].show_popup_menu(pos)
        else:
            default_title = self.tr('Item')
            popup_menu = QPopupMenu(self)
            popup_menu.setCheckable(False)
            for item in popup_items:
                title = item.name
                if not title:
                    title = getattr(item, 'type_name', default_title)
                popup_menu.insertItem(title, item.popup_menu())
            popup_menu.popup(pos)

        self.__popup_menu_showing = True
