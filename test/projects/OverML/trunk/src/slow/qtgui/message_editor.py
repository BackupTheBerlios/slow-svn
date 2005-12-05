from itertools import *
import qt

from qt_utils import qaction, qstrpy, pyqstr, FlagMaintainerAction

from lxml import etree

from slow.xslt  import STYLESHEETS
from slow.model import message_hierarchy_model
from slow.model.message_hierarchy_model import buildMessageElement, MSG_NAMESPACE_URI

from attribute_editor import AttributeDragObject
from custom_widgets import IterableListView
from popupmenu import MenuProvider

AVAILABLE_PROTOCOLS = ('TCP', 'UDP')

class DraggableMessageListView(IterableListView):
    def setAcceptDrops(self, accepts):
        IterableListView.setAcceptDrops(self, accepts)
        self.viewport().setAcceptDrops(accepts)

    def dragObject(self):
        return qt.QTextDrag( self.currentItem().text(0), self )

    def resizeEvent(self, event):
        IterableListView.resizeEvent(self, event)

        width = event.size().width() - self.lineWidth()
        col_width = (width * 3) / 5
        self.setColumnWidth(0, col_width)
        self.setColumnWidth(1, width - col_width)

class TextDialog(qt.QDialog):
    def __init__(self, parent, name, title):
        qt.QDialog.__init__(self, parent, name)
        browser = qt.QTextEdit(self, 'xml')
        browser.setReadOnly(True)
        browser.setWordWrap(browser.NoWrap)
        browser.setTextFormat(browser.PlainText)
        browser.setPointSize(12)
        browser.setFamily('Monospace')

        layout = qt.QVBoxLayout(self, 1, 1, "DialogLayout")
        layout.setResizeMode(qt.QLayout.FreeResize)
        layout.addWidget(browser)

        self.setCaption(title)
        self.setMinimumSize(qt.QSize(150,100))
        self.setText = browser.setText


class AddItemPopupAction(qt.QAction):
    ACTIVATE_SIGNAL = qt.SIGNAL('activated()')
    def __init__(self, editor, title, item_parent, item_class,
                 type_name=None, item_name=None):
        qt.QAction.__init__(self, editor, 'popup entry')
        self.setMenuText(title)
        self.setIconSet( qt.QIconSet(item_class.PIXMAP) )

        model_type    = item_class.MODEL_TYPE
        readable_name = item_class.READABLE_NAME

        def action_method():
            model = buildMessageElement(
                item_parent.model,
                model_type,
                type_name=type_name or model_type,
                readable_name=item_name or readable_name)
            item_class(editor, item_parent, model)
            item_parent.setOpen(True)

        self.__action_method = action_method

        qt.QObject.connect(self, self.ACTIVATE_SIGNAL, action_method)

class ShowMessagePopupAction(qt.QAction):
    ACTIVATE_SIGNAL = qt.SIGNAL('activated()')
    def __init__(self, editor, title, item):
        qt.QAction.__init__(self, editor, 'popup entry')
        self.setMenuText(title)
        #self.setIconSet( qt.QIconSet(item.PIXMAP) )

        def action_method():
            message_builder = STYLESHEETS['message_builder']
            indent          = STYLESHEETS.get('indent')
            xslt_result = message_builder.apply(etree.ElementTree(item.model))
            if indent:
                xslt_result = indent.apply(xslt_result)
                xml = indent.tostring(xslt_result)
            else:
                xml = message_builder.tostring(xslt_result)

            dialog = TextDialog(editor, 'message',
                                self.tr("Message '%1'").arg(item.type_name))
            dialog.setText(xml)
            dialog.resize(qt.QSize(550,300))
            dialog.show()

        self.__action_method = action_method

        qt.QObject.connect(self, self.ACTIVATE_SIGNAL, action_method)


class MListViewItem(qt.QListViewItem, MenuProvider):
    ORDER = 9
    ALLOWS_DELETE = True
    READABLE_NAME = MODEL_TYPE = PIXMAP = None # provided by subclasses !!
    REF_TYPE = REF_MODEL_TYPE = None
    FLAG_NAMES = ()
    MIME_SUBTYPE = 'field-item'
    def __init__(self, editor, parent, model, popup_checkable=False, *args):
        self.editor = editor
        self.model_root = self.editor.message_model
        self.tr = editor.tr

        self.__model = model
        coltext1 = self._get_coltext1()
        coltext2 = self._get_coltext2()

        sibling = self.find_predecessor(parent)
        if sibling:
            qt.QListViewItem.__init__(self, parent, sibling, coltext1, coltext2, *args)
        else:
            qt.QListViewItem.__init__(self, parent, coltext1, coltext2, *args)

        MenuProvider.__init__(self, editor, title=coltext1,
                              checkable=popup_checkable or bool(self.FLAG_NAMES))

        self.setPixmap(0, self.PIXMAP)
        self._enable_renaming()
        self._enable_drag()

    def _get_coltext1(self):
        try:
            return self.__model.readable_name
        except AttributeError:
            return self.READABLE_NAME

    def _set_coltext1(self, text):
        self.__model.readable_name = text

    def _get_coltext2(self):
        try:
            return self.__model.access_name
        except AttributeError:
            try:
                return self.__model.type_name
            except AttributeError:
                return ''

    def _set_coltext2(self, text):
        if self._check_accessname(text):
            self.__model.access_name = text

    def _enable_renaming(self):
        self.setRenameEnabled(0, True)
        self.setRenameEnabled(1, True)

    def _enable_drag(self):
        self.setDragEnabled(True)

    def _check_typename(self, name):
        parent = self.__model.getparent()
        if parent and hasattr(parent, 'type_names'):
            if name in parent.type_names:
                self.editor.setStatus(self.tr("Name '%1' already in use.").arg(name))
                return False
        return True

    def _check_accessname(self, name):
        parent = self.__model.getparent()
        if parent and hasattr(parent, 'access_names'):
            if name in parent.access_names:
                self.editor.setStatus(self.tr("Name '%1' already in use.").arg(name))
                return False
        return True

    def new_reference(self, new_parent):
        if self.REF_MODEL_TYPE and self.REF_ITEM_CLASS:
            ref_item_class = self.REF_ITEM_CLASS
            type_name = self.__model.type_name
            ref_model = buildMessageElement(
                new_parent.model, self.REF_MODEL_TYPE,
                type_name=type_name,
                access_name=self.build_access_name(type_name, new_parent.model),
                readable_name = ">"+ref_item_class.READABLE_NAME)
            return ref_item_class(self.editor, new_parent, ref_model)
        else:
            return None

    def build_access_name(self, type_name, new_parent_model):
        used_names = frozenset(new_parent_model.access_names)
        for number in count():
            access_name = "%s%d" % (type_name, number)
            if access_name not in used_names:
                return access_name

    @property
    def type_name(self):
        return self.__model.type_name

    @property
    def name(self):
        return self.__model.readable_name

    @property
    def access_name(self):
        return self.__model.access_name

    @property
    def model(self):
        return self.__model

    def setText(self, column, text):
        text = qstrpy(text).strip()
        model = self.__model
        if column == 0:
            self._set_coltext1(text)
        else:
            self._set_coltext2(text)

        qt.QListViewItem.setText(self, column, text)

##         if text and not model.readable_name:
##             self.setText(0, pyqstr(text.capitalize().replace('_', ' ')))

    def iterchildren(self):
        child = self.firstChild()
        while child:
            yield child
            child = child.nextSibling()

    def hasParent(self, item):
        if item == self:
            return False
        elif item == self.listView():
            return True

        parent = self.parent()
        while parent:
            if item == parent:
                return True
            parent = parent.parent()
        return False

    def find_predecessor(self, parent):
        sibling = parent.firstChild()
        my_order = self.ORDER
        after = None
        while sibling and sibling.ORDER <= my_order:
            if sibling != self:
                after = sibling
            sibling = sibling.nextSibling()
        return after

    def lastItem(self):
        last = None
        for child in self.iterchildren():
            last = child
        return last
    lastChild = lastItem

    def _populate_popup_menu(self, menu):
        if self.FLAG_NAMES:
            menu.insertSeparator()
            self._build_flag_menu_area(menu, self.editor, self.model,
                                       self.FLAG_NAMES, True)
        if self.ALLOWS_DELETE:
            menu.insertSeparator()
            self.menu_delete.setIconSet(self.editor.delete_icon)
            self.menu_delete.addTo(menu)

    @qaction('Delete', parent_attribute='editor')
    def menu_delete(self):
        model = self.__model
        model_parent = model.getparent()
        model_parent.remove(model)

        parent = self.parent()
        if parent is None:
            parent = self.listView()
        parent.takeItem(self)


class ContainerListViewItem(MListViewItem):
    def __init__(self, *args, **kwargs):
        super(ContainerListViewItem, self).__init__(*args, **kwargs)
        self.__setupClassMenuEntries()
        self.setDropEnabled(True)

    def __setupClassMenuEntries(self):
        tr  = self.editor.tr
        cls = self.__class__

        ContainerListViewItem.MENU_ENTRIES = (
            (tr('Add Content'),   ContentItem),
            (tr('Add View Data'), ViewDataItem),
            (tr('Add Container'), ContainerItem),
            (tr('Add Container'), PredefContainerItem),
            (tr('Add Header'),    HeaderItem),
            (tr('Add Message'),   MessageItem),
            )

        def dummy(self):
            pass
        ContainerListViewItem.__setupClassMenuEntries = dummy

    ATTRIBUTE_MIME_TYPE = 'text/%s;charset=UTF-8' % AttributeDragObject.MIME_SUBTYPE
    FIELD_MIME_TYPE     = 'text/%s;charset=UTF-8' % MListViewItem.MIME_SUBTYPE

    def acceptDrop(self, data):
        return qt.QTextDrag.canDecode(data)
        print list(takewhile(bool, imap(data.format, count())))
        return data.provides(self.ATTRIBUTE_MIME_TYPE) or \
               data.provides(self.FIELD_MIME_TYPE)

    def moveChild(self, item):
        parent = item.parent() or self.listView()
        parent.takeItem(item)

        sibling = item.find_predecessor(self)
        self.insertItem(item)
        if sibling:
            item.moveItem(sibling)

    def dropped(self, data):
        source = data.source()
        if source is None:
            return
        listview = self.listView()
        if source == listview:
            item = source.currentItem()
            if item == self or self.hasParent(item):
                self.setStatus(self.tr('Drop aborted, invalid target.'))
                return
            if isinstance(item, PredefContainerItem) and self._accepts_child_class(ContainerItem):
                self.insertItem( item.new_reference(self) )
                self.setOpen(True)
            elif self._accepts_child_class(item.__class__):
                self.moveChild(item)
                self.setOpen(True)
        elif source.name() == 'node_attribute_list':
            model = self.model
            item = source.currentItem()
            if hasattr(item, 'text'):
                name = qstrpy( item.text() )
                if not name:
                    return
                access_name = self.build_access_name(name, model)
                new_model = buildMessageElement(model, 'attribute',
                                                readable_name=qstrpy(self.tr('Attribute')),
                                                type_name=name,
                                                access_name=access_name)
                item = AttributeContentItem(self.editor, self, new_model)
                self.setOpen(True)
        else:
            self.setStatus('DROP from %s' % source.name())

    def _accepts_child_class(self, child_class):
        return child_class is not PredefContainerItem

    def _populate_popup_menu(self, menu):
        menu.insertSeparator()
        for text, item_class in self.MENU_ENTRIES:
            if self._accepts_child_class(item_class):
                action = AddItemPopupAction(self.editor, text,
                                            self, item_class)
                action.addTo(menu)

        super(ContainerListViewItem, self)._populate_popup_menu(menu)


class ContentItem(MListViewItem):
    ORDER = 1
    MIME_SUBTYPE = 'item-content'
    MODEL_TYPE = "content"

    def _get_coltext1(self):
        return self.model.type_name
    def _set_coltext1(self, text):
        self.model.type_name = text

class AttributeContentItem(MListViewItem):
    ORDER = 1
    MIME_SUBTYPE = 'item-attribute'
    MODEL_TYPE = "attribute"

    def _get_coltext1(self):
        return self.model.type_name
    def _set_coltext1(self, text):
        if self._check_typename(text):
            self.model.type_name = text

class ViewDataItem(MListViewItem):
    ORDER = 1
    MIME_SUBTYPE = 'item-viewdata'
    MODEL_TYPE = "viewdata"
    def __init__(self, editor, *args):
        self.FLAG_NAMES = (
            ('structured', editor.tr('bucket structure')),
            ('bucket',     editor.tr('single bucket')),
            ('list',       editor.tr('node list')),
            )
        MListViewItem.__init__(self, editor, popup_checkable=True, *args)

    def _get_coltext1(self):
        return self.model.type_name
    def _set_coltext1(self, text):
        if self._check_typename(text):
            self.model.type_name = text

    def _get_coltext2(self):
        return self.model.access_name
    def _set_coltext2(self, text):
        if self._check_accessname(text):
            self.model.access_name = text

    @property
    def structured(self):
        return self.model.structured

class ContainerItem(ContainerListViewItem):
    ORDER = 1
    MIME_SUBTYPE = 'item-container'
    MODEL_TYPE = "container"
    def __init__(self, editor, *args):
        self.FLAG_NAMES = (
            ('list', editor.tr('list')),
            )
        MListViewItem.__init__(self, editor, popup_checkable=True, *args)

    def _get_coltext2(self):
        return self.model.access_name

    def _set_coltext2(self, text):
        if self._check_accessname(text):
            self.model.access_name = text

    def _enable_renaming(self):
        self.setRenameEnabled(0, False)
        self.setRenameEnabled(1, True)

    def _accepts_child_class(self, child_class):
        return child_class not in (MessageItem, HeaderItem, PredefContainerItem)

class PredefContainerItem(ContainerItem):
    def _get_coltext2(self):
        return self.model.type_name

    def _set_coltext2(self, text):
        if self._check_typename(text):
            self.model.type_name = text

class HeaderItem(ContainerListViewItem):
    ORDER = 2
    MIME_SUBTYPE = 'item-header'
    MODEL_TYPE = "header"

class MessageItem(ContainerListViewItem):
    ORDER = 3
    MIME_SUBTYPE = 'item-message'
    MODEL_TYPE = "message"

    PROTOCOLS_PIXMAP = PROTOCOLS_NAME = None

    def _get_coltext2(self):
        return self.model.type_name
    def _set_coltext2(self, text):
        if self._check_typename(text):
            self.model.type_name = text

    def _enable_renaming(self):
        self.setRenameEnabled(0, False)
        self.setRenameEnabled(1, True)

    class ProtocolSet(object):
        __slots__ = AVAILABLE_PROTOCOLS
        PROTOCOLS = AVAILABLE_PROTOCOLS
        def __init__(self):
            for protocol in self.PROTOCOLS:
                setattr(self, protocol, False)

        def add(self, protocol):
            if protocol in self.PROTOCOLS:
                setattr(self, protocol, True)

        def to_set(self):
            return frozenset(
                protocol for protocol in self.PROTOCOLS
                if getattr(self, protocol) )

    def __init__(self, *args, **kwargs):
        super(MessageItem, self).__init__(*args, **kwargs)
        self.__protocol_set = self.ProtocolSet()

    def add_protocol(self, protocol):
        self.__protocol_set.add(protocol)

    def protocols(self):
        return self.__protocol_set.to_set()

    def protocol_menu(self):
        parent       = self.editor
        menu         = qt.QPopupMenu(parent, 'protocols')

        protocol_set = self.__protocol_set
        supported    = protocol_set.to_set()

        for protocol in protocol_set.PROTOCOLS:
            action = FlagMaintainerAction(
                parent, protocol_set, protocol, protocol )
            action.addTo(menu)
            action.setOn( protocol in supported )
        return menu

    def _populate_popup_menu(self, menu):
        menu.insertSeparator()
        menu.insertItem( qt.QIconSet(self.PROTOCOLS_PIXMAP),
                         self.PROTOCOLS_NAME,
                         self.protocol_menu() )
        if 'message_builder' in STYLESHEETS:
            action = ShowMessagePopupAction(
                self.editor, self.tr('Show XML'), self)
            action.addTo(menu)
        super(MessageItem, self)._populate_popup_menu(menu)


class ContainerRefItem(MListViewItem):
    ORDER        = ContainerItem.ORDER
    MIME_SUBTYPE = ContainerItem.MIME_SUBTYPE
    MODEL_TYPE   = "container-ref"

    def _get_coltext1(self):
        return self.model.type_name
    def _set_coltext1(self, text):
        if self._check_typename(text):
            self.model.type_name = text

    def _get_coltext2(self):
        return self.model.access_name
    def _set_coltext2(self, text):
        if self._check_accessname(text):
            self.model.access_name = text

class TopLevelItem(ContainerListViewItem):
    ALLOWS_DELETE = False
    def __init__(self, *args, **kwargs):
        ContainerListViewItem.__init__(self, *args, **kwargs)
        self.FLAG_NAMES = ()

    def _get_coltext2(self):
        return ''
    def _set_coltext2(self, text):
        pass

    def _enable_drag(self):
        self.setDragEnabled(False)

    def _enable_renaming(self):
        self.setRenameEnabled(0, False)
        self.setRenameEnabled(1, False)

    def _accepts_child_class(self, child_class):
        return child_class == self.CHILD_CLASS

class MessagesItem(TopLevelItem):
    CHILD_CLASS = HeaderItem

class ContainersItem(TopLevelItem):
    CHILD_CLASS = PredefContainerItem


class MessageEditor(MenuProvider):
    __TOP_LEVEL_CLASSES = (MessagesItem, ContainersItem)
    __ITEM_CLASSES = (HeaderItem, MessageItem, ContainerItem,
                      ViewDataItem, ContentItem, AttributeContentItem)
    __ITEM_TYPE_DICT = dict(
        (cls.MODEL_TYPE, cls)
        for cls in chain(__ITEM_CLASSES, (ContainerRefItem,))
        )

    def __init__(self):
        MenuProvider.__init__(self)
        self.message_listview.setSorting(-1)
        self.__setup_icons()

    def __setup_icons(self):
        listview = self.message_listview

        item  = self.__orig_items = listview.firstChild()
        items = []
        while item:
            items.append(item)
            item = item.firstChild()

        MessageItem.PROTOCOLS_PIXMAP = items[0].pixmap(0)
        MessageItem.PROTOCOLS_NAME   = items[0].text(0)

        for item, item_class in izip(islice(items, 1, None),
                                     chain(self.__TOP_LEVEL_CLASSES, self.__ITEM_CLASSES)):
            pixmap = item_class.PIXMAP        = item.pixmap(0)
            name   = item_class.READABLE_NAME = qstrpy( item.text(0) )

            if item_class == ContainerItem:
                ContainerRefItem.PIXMAP        = pixmap
                ContainerRefItem.READABLE_NAME = name
                ContainerItem.REF_ITEM_CLASS   = ContainerRefItem
                ContainerItem.REF_MODEL_TYPE   = ContainerRefItem.MODEL_TYPE

        listview.takeItem(self.__orig_items) # remove icons from listview but keep reference

    def __reset_icons(self, root_model):
        listview = self.message_listview
        listview.clear()
        top_level_items = self.__top_level_items = []
        for item_class in reversed(self.__TOP_LEVEL_CLASSES):
            item  = item_class(self, listview, root_model)
            top_level_items.append(item)
            listview.insertItem(item)
            item.setOpen(True)

##     def _populate_popup_menu(self, menu):
##         tr = self.tr
##         for item_class, menu_text in ( (ContainerItem, tr('Add Container')),
##                                        (HeaderItem,    tr('Add Header')) ):
##             action = AddItemPopupAction(
##                 self, menu_text, self.message_listview, item_class )
##             action.addTo(menu)

    @property
    def message_model(self):
        return self.__model

    def message_listview_contextMenuRequested(self, item, point, column):
        if item == None:
            menu_provider = self
        elif isinstance(item, MenuProvider):
            menu_provider = item
        else:
            return

        menu_provider.show_popup_menu(point)

    def message_listview_dropped(self, event):
        dest = self.message_listview.itemAt( event.pos() )
        if dest is not None:
            dest.dropped(event)

    def __recursive_from_model(self, parent, model, messages):
        if isinstance(parent, ContainersItem):
            cls = PredefContainerItem
        else:
            model_type = model.tag.split('}', 1)[-1]
            cls = self.__ITEM_TYPE_DICT[model_type]
        if not parent._accepts_child_class(cls):
            raise ValueError, "invalid child class"

        item = cls(self, parent, model)
        item.setOpen(True)

        if isinstance(item, MessageItem):
            messages[item.type_name] = item

        for child in model:
            self.__recursive_from_model(item, child, messages)

    def reset_message_descriptions(self, models):
        self.__model = models
        self.__reset_icons(models)
        top_level_items = self.__top_level_items
        lower_map = dict( (p.lower(),p) for p in AVAILABLE_PROTOCOLS )
        messages = {}
        for model in models:
            model_type = model.tag.split('}', 1)[-1]
            parent = None
            for top_item in top_level_items:
                if model_type == top_item.CHILD_CLASS.MODEL_TYPE:
                    parent = top_item
                    break
            if parent:
                self.__recursive_from_model(parent, model, messages)
            elif model_type == 'protocol':
                protocol = model.type_name
                for child in model:
                    try:
                        message = messages[child.type_name]
                        message.add_protocol(lower_map[protocol])
                    except KeyError:
                        pass
