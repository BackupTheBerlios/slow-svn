import logging
from itertools import *

from qt import QListViewItem

from qt_utils import pyqstr, qstrpy, FlagMaintainerListItem
from slow.model import slosl_model
from mathml.termparser  import InfixTermParser, ParseException, term_parsers, cached
from mathml.termbuilder import InfixTermBuilder, tree_converters
import pyparsing

str_to_mathdom = slosl_model.MathDOM.fromString


class SloslForeachListParser(InfixTermParser):
    def _parse_list(self, s,p,t):
        return [ (u'list',)  + tuple(t) ]
    def _parse_colon_interval(self, s,p,t):
        return self._parse_interval(s,p, ('[', t[0], t[1], ')'))

    def p_list(self, p_item):
        p_list = pyparsing.delimitedList(p_item)
        p_list.setParseAction(self._parse_list)
        return p_list

    @cached
    def p_foreach_list(self):
        item = self.p_arithmetic_exp()
        p_colon_interval = item + pyparsing.Suppress(':') + item
        p_colon_interval.setParseAction(self._parse_colon_interval)
        p_values = self.p_list(item) | self.p_arithmetic_interval(item) | p_colon_interval
        return (pyparsing.Suppress('(') + p_values + pyparsing.Suppress(')')) | p_values

term_parsers.register_converter('slosl_foreach_list',
                                SloslForeachListParser().p_foreach_list())


class SloslForeachListSerializer(InfixTermBuilder):
    def _handle_list(self, operator, operands, status):
        assert operator == u'list'
        return [ u'%s' % u','.join(operands) ]

tree_converters.register_converter('slosl_foreach_list',
                                   SloslForeachListSerializer())


class SLOSLEditor(object):
    VALID_FUNCTIONS = ('lowest', 'highest', 'closest', 'furthest')
    def __init__(self):
        self.__setup_child_calls()
        self.__init_visible_widgets()
        self.__init_text_verifiers()

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

    def __init_visible_widgets(self):
        self.slosl_rank_compare.hide()

    def __init_text_verifiers(self):
        identifier_validator = self.identifier_validator
        for field in (self.slosl_view_name, self.slosl_foreach_varname):
            field.setValidator(identifier_validator)

        #self.slosl_attribute_select
        #self.slosl_with

        self.slosl_from.setValidator(self.identifier_list_validator)

    def __new_model(self):
        self.__model = slosl_model.buildStatement(self.__slosl_models)
        self.__current_foreach_entry = None

    def slosl_model(self):
        return self.__slosl_models

    def _add_model_to_list(self, model):
        listview = self.slosl_view_list
        item = listview.findItem(model.name, 0)
        if not item:
            FlagMaintainerListItem(listview, model, 'selected', model.name)

    def reset_statements(self, statements=None):
        self.slosl_view_list.clear()

        if statements is None:
            statements = slosl_model.buildStatements()

        self.__slosl_models = statements
        for model in statements:
            self._add_model_to_list(model)

        self.__new_model()
        self.copy_slosl_from_model()

    def copy_slosl_from_model(self, model=None):
        self.__current_foreach_entry = None

        if model is None:
            model = self.__model

        def build_term(node, term_type='infix'):
            if hasattr(node, 'serialize'):
                return unicode( node.serialize(term_type) )
            else:
                return u''

        def build_qterm(node, term_type='infix'):
            return pyqstr( build_term(node, term_type) )

        def build_assign(t):
            name = unicode(t[0])
            if t[1]:
                return u"%s=%s" % (name, build_term(t[1]))
            else:
                return name

        self.slosl_view_name.setText(pyqstr(model.name))
        self.slosl_attribute_select.setText(pyqstr(
            '\n'.join(imap(build_assign, model.selects)) ))

        self.slosl_from.setText( ', '.join(imap(str, model.parents)) )
        self.slosl_with.setText(pyqstr( u', '.join(imap(build_assign, model.withs)) ))

        ranked = model.ranked
        self.slosl_rank_function.setCurrentText(ranked.function)
        self.slosl_rank_function_activated()

        params = ranked.parameters
        if len(params):
            self.slosl_rank_count.setText(params[0] and build_qterm(params[0]) or '1')
            self.slosl_rank_expression.setText(params[1] and build_qterm(params[1]) or '')
            if len(params) > 2 and params[2]:
                compare = build_qterm(params[2])
            else:
                compare = ''
            self.slosl_rank_compare.setText(compare)
        else:
            self.slosl_rank_count.setText('1')
            self.slosl_rank_expression.setText('')
            self.slosl_rank_compare.setText('')

        for attribute in ('where', 'having'):
            value = getattr(model, attribute)
            if value:
                expression = build_qterm(value)
            else:
                expression = ''
            getattr(self, 'slosl_%s' % attribute).setText(expression)

        foreach_list = self.slosl_foreach_list
        foreach_list.clear()
        foreachs = model.foreachs
        for variable_name, variable_declaration in foreachs:
            QListViewItem(foreach_list, variable_name,
                          build_qterm(variable_declaration,
                                      'slosl_foreach_list'))

        self.slosl_foreach_values.clear()
        self.slosl_foreach_varname.clear()
        self.slosl_copy_buckets_checkbox.setChecked(model.bucket)
        self.slosl_disable_having(model.bucket or len(foreachs) == 0)

    def copy_slosl_to_model(self, model=None):
        if model is None:
            model = self.__model

        def to_term(term_str, term_type='infix_term'):
            term = str_to_mathdom(term_str, term_type)
            return term.getroot()

        current_field = None
        try:
            old_name = str(model.view)

            current_field = self.slosl_view_name
            model.view = qstrpy(self.slosl_view_name.text()).strip()

            current_field = self.slosl_from
            parents = filter(None, (name.strip()
                                    for name in qstrpy(self.slosl_from.text()).split(',')))
            if parents:
                model.parents = parents
            else:
                self.__setStatus("Parent view names missing.")
                return self.slosl_from

            current_field = self.slosl_attribute_select
            attributes = qstrpy(self.slosl_attribute_select.text()).strip()
            del model.selects
            add = model.setSelect
            for attribute in attributes.split('\n'):
                try:
                    name, value = attribute.split('=', 1)
                except ValueError:
                    name, value = attribute.split('.', 1)[-1], attribute
                add(name, to_term(value))

            current_field = self.slosl_rank_expression
            ranking_function_name = qstrpy(self.slosl_rank_function.currentText()).strip()
            if ranking_function_name:
                ranked = model.ranked
                ranked.function = ranking_function_name
                for i, field in islice(
                    enumerate( (self.slosl_rank_count,
                                self.slosl_rank_expression,
                                self.slosl_rank_compare)
                               ),
                    ranked.function_parameter_count()
                    ):
                    ranked.setParameter(i, to_term(qstrpy(field.text())))
            else:
                del model.ranked

            current_field = self.slosl_with
            with = qstrpy(self.slosl_with.text()).strip()
            del model.withs
            if with:
                add = model.setWith
                for option in with.split(','):
                    try:
                        name, term = option.split('=', 1)
                        name, term = name.strip(), to_term(term)
                    except ValueError:
                        name, term = option, None
                    add(name, term)

            current_field = self.slosl_where
            term = self.slosl_where.text()
            if term:
                model.where = to_term(term, 'infix_bool')
            else:
                del model.where

            current_field = self.slosl_having
            text = qstrpy(self.slosl_having.text()).strip()
            if text and self.slosl_foreach_list.childCount() > 0:
                model.having = to_term(text, 'infix_bool')
            else:
                del model.having

            current_field = self.slosl_foreach_list
            del model.foreachs
            add = model.setForeach
            for name, term in self.slosl_foreach_list.iterColumns():
                term = to_term(term, 'slosl_foreach_list')
                if term:
                    add(name, term)

            current_field = self.slosl_copy_buckets_checkbox
            model.bucket = self.slosl_copy_buckets_checkbox.isChecked()

        except Exception, e:
            # to allow error handling, set status and return failed field
            self.__setStatus(e)
            return current_field

        if not model.validate():
            self.__setStatus("Statement validation failed.")
            return None

        if model.getparent() is None:
            self.__slosl_models.setStatement(model.name, model)

        name = model.name
        listview = self.slosl_view_list
        if old_name != name:
            old_item = listview.findItem(old_name, 0)
            if old_item:
                listview.takeItem(old_item)
            self._add_model_to_list(model)

        self.__setStatus()
        return None

    def slosl_view_list_selectionChanged(self):
        item = self.slosl_view_list.selectedItem()
        if item:
            model = self.__model = self.__slosl_models.getStatement( str(item.text(0)) )
            self.copy_slosl_from_model(model)

    def slosl_disable_buttons(self, disable=True):
        if disable:
            self.slosl_foreach_list_button_frame.setEnabled(False)
        else:
            self.slosl_enable_buttons()

    def slosl_enable_buttons(self):
        item = self.slosl_foreach_list.selectedItem()
        self.slosl_foreach_list_button_frame.setEnabled(bool(item))
        if item:
            self.slosl_foreach_up_button.setEnabled(bool(item.itemAbove()))
            self.slosl_foreach_down_button.setEnabled(bool(item.itemBelow()))

    def slosl_apply_button_clicked(self):
        failed_widget = self.copy_slosl_to_model(self.__model)
        if failed_widget:
            failed_widget.setFocus()

    def slosl_add_button_clicked(self):
        self.__new_model()
        failed_widget = self.copy_slosl_to_model(self.__model)
        if failed_widget:
            failed_widget.setFocus()

    def slosl_delete_button_clicked(self):
        item = self.slosl_view_list.selectedItem()
        if not item:
            return
        self.slosl_view_list.takeItem(item)

        name = str(item.text(0))
        self.__slosl_models.delStatement(name)

    def slosl_foreach_remove_button_clicked(self):
        itemlist = self.slosl_foreach_list
        item = itemlist.selectedItem()
        if item:
            name = qstrpy(item.text(0))
            itemlist.clearSelection()
            itemlist.takeItem(item)
            self.__model.delForeach(name)

    def slosl_foreach_list_selectionChanged(self):
        self.slosl_enable_buttons()
        item = self.slosl_foreach_list.selectedItem()
        if item:
            self.__current_foreach_entry = name = qstrpy(item.text(0))
            entry = self.__model.getForeach(name)
            declaration = entry and entry.serialize('slosl_foreach_list') or ""
            # FIXME: bug, handle inconsistent view/model somewhere??
            self.slosl_foreach_varname.setText(name)
            self.slosl_foreach_values.setText(declaration)

    def slosl_foreach_apply_button_clicked(self):
        name        = qstrpy(self.slosl_foreach_varname.text()).strip()
        declaration = qstrpy(self.slosl_foreach_values.text()).strip()

        try:
            tree = str_to_mathdom(declaration, 'slosl_foreach_list')
        except ParseException, e:
            self.slosl_foreach_varname.setFocus()
            self.slosl_foreach_varname.selectAll()
            self.__setStatus(e)
            return

        self.__model.setForeach(name, tree.getroot())

        item = self.slosl_foreach_list.findItem(name, 0)
        if self.__current_foreach_entry and not item:
            item = self.slosl_foreach_list.findItem(self.__current_foreach_entry, 0)
        if item:
            item.setText(0, name)
            item.setText(1, declaration)
            self.slosl_foreach_list.setSelected(item, True)
        else:
            item = QListViewItem(self.slosl_foreach_list,
                                 name, declaration)

        self.__current_foreach_entry = name
        self.slosl_disable_having(False)

    def slosl_rank_function_activated(self, item_pos=None):
        if item_pos is None:
            item_pos = self.slosl_rank_function.currentItem()

        functions = self.VALID_FUNCTIONS
        if item_pos >= 1 and item_pos <= len(functions):
            function_name = functions[item_pos-1]
        else:
            function_name = None
        if function_name in ('closest', 'furthest'):
            self.slosl_rank_compare.show()
        else:
            self.slosl_rank_compare.hide()
