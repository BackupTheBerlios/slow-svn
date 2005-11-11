from itertools import *
from qt import *

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
        return QTextDrag( self.currentItem().text(0), self )

    def resizeEvent(self, event):
        IterableListView.resizeEvent(self, event)

        width = event.size().width() - self.lineWidth()
        col_width = (width * 3) / 5
        self.setColumnWidth(0, col_width)
        self.setColumnWidth(1, width - col_width)

class TextDialog(QDialog):
    def __init__(self, parent, name, title):
        QDialog.__init__(self, parent, name)
        browser = QTextEdit(self, 'xml')
        browser.setReadOnly(True)
        browser.setWordWrap(browser.NoWrap)
        browser.setTextFormat(Qt.PlainText)
        browser.setPointSize(12)
        browser.setFamily('monospace')

        layout = QVBoxLayout(self, 1, 1, "DialogLayout")
        layout.setResizeMode(QLayout.FreeResize)
        layout.addWidget(browser)

        self.setCaption(title)
        self.setMinimumSize(QSize(150,100))
        self.setText = browser.setText


class AddItemPopupAction(QAction):
    ACTIVATE_SIGNAL = SIGNAL('activated()')
    def __init__(self, editor, title, item_parent, item_class,
                 type_name=None, item_name=None):
        QAction.__init__(self, editor, 'popup entry')
        self.setMenuText(title)
        self.setIconSet( QIconSet(item_class.PIXMAP) )

        model_type    = item_class.MODEL_TYPE
        readable_type = item_class.READABLE_NAME

        def action_method():
            model = buildMessageElement(
                item_parent.model,
                model_type,
                type_name=type_name or model_type,
                readable_type=item_name or readable_type)
            item_class(editor, item_parent, model)
            item_parent.setOpen(True)

        self.__action_method = action_method

        QObject.connect(self, self.ACTIVATE_SIGNAL, action_method)

class ShowMessagePopupAction(QAction):
    ACTIVATE_SIGNAL = SIGNAL('activated()')
    def __init__(self, editor, title, item):
        QAction.__init__(self, editor, 'popup entry')
        self.setMenuText(title)
        #self.setIconSet( QIconSet(item.PIXMAP) )

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
                                self.tr("Message '%1'").arg(item.access_name))
            dialog.setText(xml)
            dialog.resize(QSize(550,300))
            dialog.show()

        self.__action_method = action_method

        QObject.connect(self, self.ACTIVATE_SIGNAL, action_method)


class MListViewItem(QListViewItem, MenuProvider):
    ORDER = 9
    ALLOWS_DELETE = True
    READABLE_NAME = MODEL_TYPE  = PIXMAP = None # provided by subclasses !!
    REF_TYPE = REF_MODEL_TYPE = None
    FLAG_NAMES = ()
    MIME_SUBTYPE = 'field-item'
    def __init__(self, editor, parent, model, popup_checkable=False, *args):
        self.editor = editor
        self.model_root = self.editor.message_model
        self.tr = editor.tr

        self.__model = model

        readable_name = getattr(model, 'readable_name', self.READABLE_NAME)
        access_name   = getattr(model, 'access_name', None) or ''

        sibling = self.find_predecessor(parent)
        if sibling:
            QListViewItem.__init__(self, parent, sibling, readable_name, access_name, *args)
        else:
            QListViewItem.__init__(self, parent, readable_name, access_name, *args)

        MenuProvider.__init__(self, editor, title=readable_name,
                              checkable=popup_checkable or bool(self.FLAG_NAMES))

        self.setPixmap(0, self.PIXMAP)
        self.setRenameEnabled(1, True)
        self.setDragEnabled(True)

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
            model.readable_name = text
        elif model.access_name != text:
            parent = model.getparent()
            if parent and hasattr(parent, 'access_names'):
                if text in parent.access_names:
                    self.editor.setStatus(self.tr("Name '%1' already in use.").arg(text))
                    return
            model.access_name = text

        QListViewItem.setText(self, column, text)

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
                                       self.FLAG_NAMES)
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
            (tr('Add Header'),    HeaderItem),
            (tr('Add Message'),   MessageItem),
            )

        def dummy(self):
            pass
        ContainerListViewItem.__setupClassMenuEntries = dummy

    ATTRIBUTE_MIME_TYPE = 'text/%s;charset=UTF-8' % AttributeDragObject.MIME_SUBTYPE
    FIELD_MIME_TYPE     = 'text/%s;charset=UTF-8' % MListViewItem.MIME_SUBTYPE

    def acceptDrop(self, data):
        return QTextDrag.canDecode(data)
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
        listview = self.listView()
        source = data.source()
        if source == listview:
            item = source.currentItem()
            if item != self and self._accepts_child_class(item.__class__):
                if not self.hasParent(item):
                    reference = False
                    parent = item.parent()
                    while hasattr(parent, 'parent'):
                        if isinstance(parent, ContainersItem):
                            reference = True
                            break
                        parent = parent.parent()

                    if reference:
                        self.insertItem( item.new_reference(self) )
                    else:
                        self.moveChild(item)
                    self.setOpen(True)
            return
        elif not self._accepts_child_class(ContentItem):
            return

        # broken:

##         if data.provides(self.ATTRIBUTE_MIME_TYPE):
##             mime_type = self.ATTRIBUTE_MIME_TYPE
##         elif data.provides(self.FIELD_MIME_TYPE):
##             listview = self.listView()
##             source = data.source()
##             if source == listview:
##                 print source.currentItem().text(0)
##             mime_type = self.FIELD_MIME_TYPE
##         else:
##             print data.source(), 'IGNORE'
##             data.ignore()
##             return

##         type_name = unicode(str(data.encodedData(mime_type)), 'UTF-8')
##         model = ContentModel(type_name)
##         ContentItem(self.editor, self, model)
##         self.setOpen(True)

    def _accepts_child_class(self, child_class):
        return True

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

    def _accepts_child_class(self, child_class):
        return child_class not in (MessageItem, HeaderItem)

class HeaderItem(ContainerListViewItem):
    ORDER = 2
    MIME_SUBTYPE = 'item-header'
    MODEL_TYPE = "header"

class MessageItem(ContainerListViewItem):
    ORDER = 3
    MIME_SUBTYPE = 'item-message'
    MODEL_TYPE = "message"

    PROTOCOLS_PIXMAP = PROTOCOLS_NAME = None

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
        menu         = QPopupMenu(parent, 'protocols')

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
        menu.insertItem( QIconSet(self.PROTOCOLS_PIXMAP),
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


class TopLevelItem(ContainerListViewItem):
    ALLOWS_DELETE = False
    def __init__(self, *args, **kwargs):
        ContainerListViewItem.__init__(self, *args, **kwargs)
        self.FLAG_NAMES = ()
        self.setDragEnabled(False)

    def _accepts_child_class(self, child_class):
        return child_class == self.CHILD_CLASS

class MessagesItem(TopLevelItem):
    CHILD_CLASS = HeaderItem

class ContainersItem(TopLevelItem):
    CHILD_CLASS = ContainerItem


class MessageEditor(MenuProvider):
    __TOP_LEVEL_CLASSES = (MessagesItem, ContainersItem)
    __ITEM_CLASSES = (HeaderItem, MessageItem, ContainerItem,
                      ViewDataItem, ContentItem)
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
        print event
        pass

    def __recursive_from_model(self, parent, model, messages):
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
