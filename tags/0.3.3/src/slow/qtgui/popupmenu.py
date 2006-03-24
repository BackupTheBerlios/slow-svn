from qt import Qt, QLabel, QPopupMenu, QActionGroup
from qt_utils import FlagMaintainerAction

class MenuProvider(object):
    POPUP_TITLE_TEMPLATE = u'<b>%s</b>'
    def __init__(self, parent=None, title=None,
                 title_template=POPUP_TITLE_TEMPLATE,
                 checkable=False):
        self.__title     = title
        self.__parent    = parent or self
        self.__template  = title_template
        self.__checkable = checkable

    def _build_popup_title(self, title):
        return self.__template % title

    def _populate_popup_menu(self, menu):
        pass

    def _build_flag_menu_area(self, menu, editor, model, flag_list, exclusive=True):
        if len(flag_list) == 1:
            group  = None
            parent = editor
        else:
            parent = group = QActionGroup(editor)
            group.setExclusive(bool(exclusive))

        actions = [
            FlagMaintainerAction(parent, model, flag_name, translation)
            for flag_name, translation in flag_list
            ]

        if len(actions) == 1:
            actions[0].addTo(menu)
        else:
            group.addTo(menu)

    def _build_popup_menu(self, title=None):
        self._popup_menu = menu = QPopupMenu(self.__parent)
        menu.setCheckable( self.__checkable )
        if title is None:
            title = self.__title
        if title is not None:
            title_label = self.__title_item = QLabel(self._build_popup_title(title), menu)
            title_label.setAlignment(Qt.AlignHCenter)
            menu.insertItem(title_label)

        self._populate_popup_menu(menu)

    def get_popup_title(self):
        return self.__title

    def set_popup_title(self, title):
        self.__title = title
        try:
            title_item = self.__title_item
        except AttributeError:
            if title:
                self._build_popup_menu(title)
            return

        title_item.setText(self._build_popup_title(title))

    def reset_popup_menu(self):
        try: del self._popup_menu
        except AttributeError:
            pass

    def popup_menu(self):
        try:
            return self._popup_menu
        except AttributeError:
            self._build_popup_menu()
            return self._popup_menu

    def show_popup_menu(self, pos):
        menu = self.popup_menu()
        if menu:
            menu.popup(pos)
