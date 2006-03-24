from itertools import *
#from qt import *
import qt

def qstrpy(qstring):
    return unicode(str(qstring.utf8()), 'utf-8')

def pyqstr(ustring):
    return qt.QString.fromUtf8( ustring.encode('utf-8') )


############################################################
## Decorators
############################################################

class qaction(object):
    ACTIVATED = qt.SIGNAL('activated()')
    def __init__(self, menu_text=None, accel=None, parent_attribute=None,
                 iconset=None, pixmap=None,
                 iconset_attribute=None, pixmap_attribute=None):
        self.menu_text, self.accel = menu_text, accel
        self.parent_attribute = parent_attribute
        self.iconset, self.iconset_attribute = iconset, iconset_attribute
        self.pixmap,  self.pixmap_attribute  = pixmap,  pixmap_attribute

    def __call__(self, method):
        self.name   = method.func_name
        self.method = method
        return self

    def __get__(self, instance, _):
        if instance is None:
            return self

        if self.parent_attribute:
            parent = getattr(instance, self.parent_attribute, instance)
        else:
            parent = instance

        action = qt.QAction(parent, self.name)
        if self.menu_text:
            menu_text = self.menu_text
            for source in (instance, parent):
                try:
                    menu_text = source.tr(menu_text)
                    break
                except AttributeError:
                    pass
            action.setMenuText(menu_text)

        if self.pixmap_attribute:
            pixmap = getattr(instance, self.pixmap_attribute, self.pixmap)
        else:
            pixmap = self.pixmap

        if pixmap:
            iconset = qt.QIconSet(pixmap)
        elif self.iconset_attribute:
            iconset = getattr(instance, self.iconset_attribute, self.iconset)
        else:
            iconset = self.iconset

        if iconset:
            action.setIconSet(iconset)
        if self.accel:
            action.setAccel(self.accel)

        method = self.method
        def call_method():
            method(instance)

        self.call_method = call_method
        qt.QObject.connect(action, self.ACTIVATED, call_method)

        setattr(instance, self.name, action)
        return action


def qt_signal_signature(signature, signal_class=qt.SIGNAL):
    split_pos = signature.find('(')
    signal_name, args = signature[:split_pos], signature[split_pos:]
    def set_slot_sig(method):
        method.slot_signature = signature
        method.signal_name = signal_name
        function = getattr(method, 'im_func', method)

        method.signal = signal_class(signal_name+args)
        method.slot   = qt.SLOT(function.func_name+args)
        return method
    return set_slot_sig

def py_signal_signature(signature):
    return qt_signal_signature(signature, qt.PYSIGNAL)


############################################################
## Utility classes
############################################################

class ListViewIterator(object):
    def __init__(self, listview_or_item):
        if isinstance(listview_or_item, qt.QListView):
            self.item = listview_or_item.firstChild()
            self.column_nos = range(listview_or_item.columns())
        else:
            self.item = listview_or_item
            self.column_nos = range(listview_or_item.listView().columns())

    def __iter__(self):
        return self
    def next(self):
        if not self.item:
            raise StopIteration
        current = self.item
        self.item = self.item.nextSibling()
        return map(qstrpy, imap(current.text, self.column_nos))


class FlagMaintainerListItem(qt.QCheckListItem):
    def __init__(self, parent, flag_object, flag_name, name=None, *args):
        if name is None:
            name = flag_name
        self.flag_object, self.flag_name = flag_object, flag_name
        qt.QCheckListItem.__init__(self, parent, name, qt.QCheckListItem.CheckBox)
        for column, text in izip(count(1), args):
            self.setText(column, text)
        self.updateStatus()

    def updateStatus(self):
        self.setOn( getattr(self.flag_object, self.flag_name) )

    def stateChange(self, status):
        setattr(self.flag_object, self.flag_name, status)


class FlagMaintainerAction(qt.QAction):
    def __init__(self, parent, flag_object, flag_name, menu_name=None):
        qt.QAction.__init__(self, parent, flag_name)
        if menu_name:
            self.setMenuText(menu_name)
        self.setToggleAction(True)
        self.flag_object, self.flag_name = flag_object, flag_name
        self.updateStatus()

    def updateStatus(self):
        qt.QAction.setOn(self, getattr(self.flag_object, self.flag_name))

    def setOn(self, on):
        setattr(self.flag_object, self.flag_name, on)
        qt.QAction.setOn(self, on)


class ProcessManager(qt.QProcess):
    __STDOUT_READY_SIGNAL   = qt.SIGNAL('readyReadStdout()')
    __PROCESS_EXITED_SIGNAL = qt.SIGNAL('processExited()')
    __STDIN_WRITTEN_SIGNAL  = qt.SIGNAL('wroteToStdin()')
    def __init__(self, parent, call_back, *args):
        qt.QProcess.__init__(self, parent)

        self.call_back = call_back
        for arg in args:
            self.addArgument(arg)

        self.output_data = []
        self.input_data  = []
        qt.QObject.connect(self, self.__STDOUT_READY_SIGNAL,   self.read)
        qt.QObject.connect(self, self.__PROCESS_EXITED_SIGNAL, self.exited)

        self.start()

    def write(self, data):
        self.input_data.append(data)

    def close(self):
        data = ''.join(self.input_data)
        del self.input_data[:]
        if data:
            qt.QObject.connect(self, self.__STDIN_WRITTEN_SIGNAL, self.closeStdin)
            self.writeToStdin(data)

    def closeStdin(self):
        qt.QObject.disconnect(self, self.__STDIN_WRITTEN_SIGNAL, self.closeStdin)
        qt.QProcess.closeStdin(self)

    def read(self):
        data = str( self.readStdout() )
        if data:
            self.output_data.append(data)

    def exited(self):
        qt.QObject.disconnect(self, self.__STDOUT_READY_SIGNAL,   self.read)
        qt.QObject.disconnect(self, self.__PROCESS_EXITED_SIGNAL, self.exited)

        self.read()
        data = ''.join(self.output_data)
        del self.output_data[:]
        self.call_back(data)
