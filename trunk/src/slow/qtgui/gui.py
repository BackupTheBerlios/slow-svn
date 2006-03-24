# -*- coding: iso8859-15 -*-

try: from psyco.classes import *
except: pass

RUNNING_PSYCO = False

import os, os.path, logging
from itertools import *

import qt
from qt_utils import pyqstr, qstrpy, ListViewIterator

from genaboutdialog import AboutDialog
from gengui import OverlayDesignerMainWindow

from preference_dialog import PreferenceDialog
from edsm_editor       import EDSMEditor
from slosl_editor      import SLOSLEditor
from attribute_editor  import AttributeEditor
from message_editor    import MessageEditor
from test_editor       import TestEditor

from slow.xslt import STYLESHEETS
from slow.model.file_model       import buildFile
from slow.model.preference_model import buildPreferences

from lxml import etree

from mathml.termbuilder import tree_converters
from mathml.lmathdom    import MathDOM

VERSION = '1.0'

class RegExps(object):
    __SIMPLE_RE_DICT = {}

    RE_CLASS_NAME = __SIMPLE_RE_DICT['classname'] = \
                    '[A-Z][_a-zA-Z0-9]*'

    RE_IDENTIFIER = __SIMPLE_RE_DICT['identifier'] = \
                    '[a-z][_a-z0-9]*'

    RE_ASSIGNMENT = __SIMPLE_RE_DICT['assignment'] = \
                    '\s*%(identifier)s\s*(?:=\s*(?:[^\n]+)\s*)?' % __SIMPLE_RE_DICT

    RE_IDENTIFIER_LIST = '^\s*(?:%(identifier)s\s*)(?:,\s*(?:%(identifier)s)\s*)*$' % __SIMPLE_RE_DICT

    RE_CLASS_NAME_LIST = '^\s*(?:%(classname)s\s*)(?:,\s*(?:%(classname)s)\s*)*$' % __SIMPLE_RE_DICT


class IdentifierValidator(qt.QRegExpValidator):
    def __init__(self, parent, allow_list=False):
        if allow_list:
            regexp = RegExps.RE_IDENTIFIER_LIST
        else:
            regexp = RegExps.RE_IDENTIFIER
        qt.QRegExpValidator.__init__(self, qt.QRegExp(regexp), parent)

    def validate(self, text, pos):
        text.replace(0, len(text), text.lower().replace('-', '_'))
        return qt.QRegExpValidator.validate(self, text, pos)


class ClassNameValidator(qt.QRegExpValidator):
    def __init__(self, parent, allow_list=False):
        if allow_list:
            regexp = RegExps.RE_CLASS_NAME_LIST
        else:
            regexp = RegExps.RE_CLASS_NAME
        qt.QRegExpValidator.__init__(self, qt.QRegExp(regexp), parent)

    def validate(self, text, pos):
        if len(text) > 0:
            text.replace(0, 1, text[0].upper())
        text.replace('-', '_')
        return qt.QRegExpValidator.validate(self, text, pos)


class OverlayDesigner_aboutdialog(AboutDialog):
    def __init__(self, parent=None, name=None, modal=0, fl=0):
        AboutDialog.__init__(self, parent, name, modal, fl)
        title = self.title_label.text().replace('[VT]', VERSION)
        self.title_label.setText(title)
        if RUNNING_PSYCO:
            self.running_psyco_textLabel.show()
        else:
            self.running_psyco_textLabel.hide()

    def about_ok_button_clicked(self):
        self.close(False)


class MenuFunctions(object):
    PREF_FILENAME  = os.path.expanduser('~/.odconfig')
    TITLE_SPLITTER = ' -- '

    FILE_EXTENSION = '.xod'
    FILE_FILTER    = '*' + FILE_EXTENSION

    FLAT_FILE_EXTENSION = '.xof'
    FLAT_FILE_FILTER    = '*' + FLAT_FILE_EXTENSION

    def __init__(self):
        self.setCurrentFile(None)

    def setCurrentFile(self, filename, tree=None):
        if tree is None:
            tree = etree.ElementTree( buildFile() )
        self.current_tree = tree
        self.current_file = filename
        self.fileSaveAction.setEnabled( bool(filename) )

        caption = qstrpy( self.caption() ).split(self.TITLE_SPLITTER)[-1]
        if filename:
            basename = os.path.basename(filename)
            basename = os.path.splitext(basename)[0]
            if basename:
                caption = '%s%s%s' % (basename, self.TITLE_SPLITTER, caption)
        self.setCaption(caption)

    def setupModelFromTree(self, tree):
        root = tree.getroot()
        datatype_descr = root.types
        attr_descr     = root.attributes
        msg_descr      = root.message_hierarchy
        icon_positions = root.guidata.pos_dict
        statements     = root.statements
        edsm           = root.edsm
        test_code      = root.guidata.testcode_dict

        self.reset_datatype_descriptions(datatype_descr)
        self.reset_attribute_descriptions(attr_descr)
        self.reset_message_descriptions(msg_descr)
        self.reset_edsm(edsm, icon_positions)
        self.reset_statements(statements)
        self.reset_tests(test_code)

    def loadFile(self, filename):
        self.setStatus(self.tr("Loading file '%1'").arg(filename))
        try:
            tree = etree.ElementTree(file=filename)
        except Exception, e:
            self.setStatus(self.tr('Loading file failed:'), e)
            return
        try:
            self.setupModelFromTree(tree)
            self.setStatus(self.tr("File '%1' loaded.").arg(filename))
        except Exception, e:
            self.setStatus(self.tr('Loading file data failed:'), e)
            return

        self.setCurrentFile(filename, tree)

    def fileNew(self):
        self.setCurrentFile(None)
        self.setupModelFromTree(self.current_tree)

    def fileOpen(self):
        filename = qt.QFileDialog.getOpenFileName(
            qt.QString.null, self.FILE_FILTER, self,
            'open file dialog', self.tr('Open file ...'))
        filename = qstrpy(filename)
        if filename:
            self.loadFile(filename)

    def fileSave(self):
        if not self.current_file:
            self.fileSaveAs()
            return

        filename = self.current_file
        self.setStatus(self.tr('Writing file %1').arg(filename))

        self.__store_gui_data()

        root = self.current_tree.getroot()
        try:
            if hasattr(root, '_strip'):
                root._strip()
        except Exception, e:
            self.setStatus(self.tr('XML building failed:'), e)
            return

        try:
            if hasattr(root, 'validate'):
                assert root.validate()
        except Exception, e:
            self.setStatus(self.tr('XML validation failed:'), e)
            return

        if self.preferences.optimize_xml_size:
            indent_step = None
        else:
            indent_step = 2

        self.__backup_file(filename)

        try:
            self.current_tree.write(filename)
        except Exception, e:
            self.setStatus(self.tr('Saving File failed:'), e)
            return

        self.setStatus(self.tr("File '%1' saved.").arg(filename))

    def fileSaveAs(self):
        filename = qt.QFileDialog.getSaveFileName(
            None, self.FILE_FILTER, self,
            'save file dialog', self.tr('Save to file ...'))
        filename = qstrpy(filename)
        if not filename:
            return
        if not filename.endswith(self.FILE_EXTENSION):
            filename += self.FILE_EXTENSION

        self.setCurrentFile(filename, self.current_tree)
        self.fileSave()

    def __store_gui_data(self):
        root = self.current_tree.getroot()
        gui_data = root.guidata
        gui_data.clear()

        try:
            super(MenuFunctions, self)._store_gui_data(gui_data)
        except AttributeError, e:
            if '_store_gui_data' not in str(e):
                raise

    def __backup_file(self, filename):
        try:
            os.rename(filename, filename + '~')
        except (IOError, OSError):
            pass

    def exportFlat(self):
        try:
            xslt = STYLESHEETS['flat_export']
        except KeyError:
            self.setStatus(self.tr("Stylesheet 'flat_export' not installed."))

        filename = qt.QFileDialog.getSaveFileName(
            None, self.FLAT_FILE_FILTER, self,
            'export file dialog', self.tr('Export to flat file ...'))
        filename = qstrpy(filename)
        if not filename:
            return
        if not filename.endswith(self.FLAT_FILE_EXTENSION):
            filename += self.FLAT_FILE_EXTENSION

        result = xslt.apply(self.current_tree)
        if not self.preferences.optimize_xml_size:
            indent = STYLESHEETS.get('indent')
            if indent:
                result = indent.apply(result)
                xslt = indent

        xml_string = xslt.tostring(result)

        self.__backup_file(filename)
        try:
            xml_file = open(filename, 'w')
        except Exception, e:
            self.setStatus(self.tr('Opening file for writing failed:'), e)
            return

        try:
            xml_file.write(xml_string)
        except Exception, e:
            self.setStatus(self.tr('Writing to file failed:'), e)
        xml_file.close()

    def filePrint(self):
        print "OverlayDesigner_gui.filePrint(): Not implemented yet"

    def fileExit(self):
        self.close(False)

    def editUndo(self):
        print "OverlayDesigner_gui.editUndo(): Not implemented yet"

    def editRedo(self):
        print "OverlayDesigner_gui.editRedo(): Not implemented yet"

    def editCut(self):
        print "OverlayDesigner_gui.editCut(): Not implemented yet"

    def editCopy(self):
        print "OverlayDesigner_gui.editCopy(): Not implemented yet"

    def editPaste(self):
        print "OverlayDesigner_gui.editPaste(): Not implemented yet"

    def editFind(self):
        print "OverlayDesigner_gui.editFind(): Not implemented yet"

    def editPreferences(self):
        self.pref_dialog.show()

    def storePreferences(self, model=None):
        if model is None:
            model = self.preferences
        out_file = open(self.PREF_FILENAME, 'w')
        pref_tree = etree.ElementTree(model)
        pref_tree.write(out_file)

    def loadPreferences(self):
        try:
            in_file = open(self.PREF_FILENAME, 'r')
        except (IOError, OSError):
            self.preferences = buildPreferences()
            return

        try:
            self.preferences = etree.parse(in_file).getroot()
        finally:
            in_file.close()

    def helpIndex(self):
        print "OverlayDesigner_gui.helpIndex(): Not implemented yet"

    def helpContents(self):
        print "OverlayDesigner_gui.helpContents(): Not implemented yet"

    def helpAbout(self):
        self.about_dialog.show()


class OverlayDesigner_gui(MenuFunctions,
                          AttributeEditor, MessageEditor,
                          SLOSLEditor, EDSMEditor, TestEditor,
                          OverlayDesignerMainWindow):
    def __init__(self, parent=None, name=None, fl=0):
        self.__class__.tr = OverlayDesignerMainWindow._OverlayDesignerMainWindow__tr

        self.logger = logging.getLogger('gui')

        OverlayDesignerMainWindow.__init__(self, parent, name, fl)

        self.delete_icon = qt.QIconSet( self.slosl_foreach_remove_button.pixmap() )

        self.loadPreferences()
        self.pref_dialog  = PreferenceDialog(self, self.storePreferences,
                                             self.preferences)
        self.about_dialog = OverlayDesigner_aboutdialog(modal=True)

        self.class_name_validator      = ClassNameValidator(self)
        self.class_name_list_validator = ClassNameValidator(self, allow_list=True)
        self.identifier_validator      = IdentifierValidator(self)
        self.identifier_list_validator = IdentifierValidator(self, allow_list=True)

        for supertype in (MenuFunctions, AttributeEditor, MessageEditor,
                          SLOSLEditor, EDSMEditor, TestEditor):
            supertype.__init__(self)

        self.setupModelFromTree(self.current_tree)

    def polish(self):
        OverlayDesignerMainWindow.polish(self)
        self.FileToolbar.hide()

    def setStatus(self, *args):
        strings = []
        append = strings.append
        for arg in args:
            if isinstance(arg, unicode):
                append(arg)
            elif isinstance(arg, str):
                append(unicode(arg))
            elif isinstance(arg, qt.QString):
                append(qstrpy(arg))
            elif isinstance(arg, Exception):
                self.logger.exception(arg)
                exc_type = arg.__class__.__name__
                try:
                    arg = arg.args[0]
                except (AttributeError, IndexError):
                    arg = unicode(arg)
                append( u" %s: %s" % (exc_type, arg) )
            else:
                append(unicode(arg))

        line = u' '.join(strings)

        statusbar = self.statusBar()
        if line:
            statusbar.message(line)
        else:
            statusbar.clear()

    def overlay_tab_currentChanged(self, tab_widget):
        method = getattr(self, 'activate_%s' % tab_widget.name(), None)
        if method:
            method()
        #print tab_widget, tab_widget.name()

def run():
    import sys, optparse
    app = qt.QApplication(sys.argv)

    opparser = optparse.OptionParser()
    opparser.add_option('-l', '--logfile', dest='logfile',
                        help="write log to FILE", metavar='FILE')

    opparser.add_option('-d', '--loglevel', dest='loglevel',
                        help="set log level", default='ERROR')

    opparser.add_option('-L', '--language', dest='language',
                        help="set user interface language")

    opparser.add_option('-P', '--no-psyco', dest='psyco_off',
                        action='store_true', default=False,
                        help="set user interface language")

    options, args = opparser.parse_args( app.argv() )

    if not options.psyco_off:
        try:
            import psyco
            psyco.profile()
            RUNNING_PSYCO = True
        except ImportError:
            pass

    loglevel = getattr(logging, options.loglevel.upper(), logging.ERROR)
    if options.logfile:
        logging.basicConfig(level=loglevel,
                            filename=options.logfile, filemode='w')
    else:
        logging.basicConfig(level=loglevel)

    if options.language:
        translator = qt.QTranslator()
        if translator.load('gui_%s' % options.language, 'qtgui/ts'):
            app.installTranslator(translator)

    # setup GUI
    qt.QObject.connect(app, qt.SIGNAL("lastWindowClosed()"), app, qt.SLOT("quit()"))

    w = OverlayDesigner_gui()
    app.setMainWidget(w)
    w.show()

    if len(args) > 1:
        w.loadFile(args[1])

    app.exec_loop()

if __name__ == '__main__':
    run()
