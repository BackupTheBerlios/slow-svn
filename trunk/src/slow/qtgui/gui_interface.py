# -*- coding: utf-8 -*-

from qt import *
from genaboutdialog import AboutDialog


class OverlayDesigner_aboutdialog(AboutDialog):

    def __init__(self,parent = None,name = None,modal = 0,fl = 0):
        AboutDialog.__init__(self,parent,name,modal,fl)


    def about_ok_button_clicked(self):
        print "OverlayDesigner_aboutdialog.about_ok_button_clicked(): Not implemented yet"


from genedsmdialog import EDSMDialog


class OverlayDesigner_edsmdialog(EDSMDialog):

    def __init__(self,parent = None,name = None,modal = 0,fl = 0):
        EDSMDialog.__init__(self,parent,name,modal,fl)


    def language_name_activated(self,a0):
        print "OverlayDesigner_edsmdialog.language_name_activated( const QString & ): Not implemented yet"


from gengui import OverlayDesignerMainWindow


class OverlayDesigner_gui(OverlayDesignerMainWindow):

    def __init__(self,parent = None,name = None,fl = 0):
        OverlayDesignerMainWindow.__init__(self,parent,name,fl)


    def fileNew(self):
        print "OverlayDesigner_gui.fileNew(): Not implemented yet"


    def fileOpen(self):
        print "OverlayDesigner_gui.fileOpen(): Not implemented yet"


    def fileSave(self):
        print "OverlayDesigner_gui.fileSave(): Not implemented yet"


    def fileSaveAs(self):
        print "OverlayDesigner_gui.fileSaveAs(): Not implemented yet"


    def filePrint(self):
        print "OverlayDesigner_gui.filePrint(): Not implemented yet"


    def fileExit(self):
        print "OverlayDesigner_gui.fileExit(): Not implemented yet"


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


    def helpIndex(self):
        print "OverlayDesigner_gui.helpIndex(): Not implemented yet"


    def helpContents(self):
        print "OverlayDesigner_gui.helpContents(): Not implemented yet"


    def helpAbout(self):
        print "OverlayDesigner_gui.helpAbout(): Not implemented yet"


    def add_or_replace_node_attribute_clicked(self):
        print "OverlayDesigner_gui.add_or_replace_node_attribute_clicked(): Not implemented yet"


    def remove_node_attribute_clicked(self):
        print "OverlayDesigner_gui.remove_node_attribute_clicked(): Not implemented yet"


    def attribute_type_add_or_replace_clicked(self):
        print "OverlayDesigner_gui.attribute_type_add_or_replace_clicked(): Not implemented yet"


    def attribute_type_remove_clicked(self):
        print "OverlayDesigner_gui.attribute_type_remove_clicked(): Not implemented yet"


    def slosl_foreach_up_button_clicked(self):
        print "OverlayDesigner_gui.slosl_foreach_up_button_clicked(): Not implemented yet"


    def slosl_foreach_down_button_clicked(self):
        print "OverlayDesigner_gui.slosl_foreach_down_button_clicked(): Not implemented yet"


    def slosl_foreach_remove_button_clicked(self):
        print "OverlayDesigner_gui.slosl_foreach_remove_button_clicked(): Not implemented yet"


    def slosl_apply_button_clicked(self):
        print "OverlayDesigner_gui.slosl_apply_button_clicked(): Not implemented yet"


    def slosl_add_button_clicked(self):
        print "OverlayDesigner_gui.slosl_add_button_clicked(): Not implemented yet"


    def slosl_delete_button_clicked(self):
        print "OverlayDesigner_gui.slosl_delete_button_clicked(): Not implemented yet"


    def slosl_foreach_apply_button_clicked(self):
        print "OverlayDesigner_gui.slosl_foreach_apply_button_clicked(): Not implemented yet"


    def slosl_rank_function_activated(self,a0):
        print "OverlayDesigner_gui.slosl_rank_function_activated( int ): Not implemented yet"


    def node_attribute_name_textChanged(self,a0):
        print "OverlayDesigner_gui.node_attribute_name_textChanged( const QString & ): Not implemented yet"


    def node_attribute_list_selectionChanged(self):
        print "OverlayDesigner_gui.node_attribute_list_selectionChanged(): Not implemented yet"


    def attribute_type_select_activated(self,a0):
        print "OverlayDesigner_gui.attribute_type_select_activated( const QString & ): Not implemented yet"


    def overlay_tab_currentChanged(self,a0):
        print "OverlayDesigner_gui.overlay_tab_currentChanged( QWidget * ): Not implemented yet"


    def edsm_tool_button_toggled(self,a0):
        print "OverlayDesigner_gui.edsm_tool_button_toggled( bool ): Not implemented yet"


    def edsm_iconview_contextMenuRequested(self,a0,a1):
        print "OverlayDesigner_gui.edsm_iconview_contextMenuRequested( QIconViewItem *, const QPoint & ): Not implemented yet"


    def slosl_foreach_list_selectionChanged(self):
        print "OverlayDesigner_gui.slosl_foreach_list_selectionChanged(): Not implemented yet"


    def slosl_disable_having(self,a0):
        print "OverlayDesigner_gui.slosl_disable_having( bool ): Not implemented yet"


    def slosl_foreach_new_button_clicked(self):
        print "OverlayDesigner_gui.slosl_foreach_new_button_clicked(): Not implemented yet"


    def slosl_disable_buttons(self,a0):
        print "OverlayDesigner_gui.slosl_disable_buttons( bool ): Not implemented yet"


    def slosl_view_list_selectionChanged(self):
        print "OverlayDesigner_gui.slosl_view_list_selectionChanged(): Not implemented yet"


    def edsm_edit_state(self,a0):
        print "OverlayDesigner_gui.edsm_edit_state( QIconViewItem * ): Not implemented yet"


    def type_name_field_textChanged(self,a0):
        print "OverlayDesigner_gui.type_name_field_textChanged( const QString & ): Not implemented yet"


    def node_attribute_type_activated(self,a0):
        print "OverlayDesigner_gui.node_attribute_type_activated( const QString & ): Not implemented yet"


    def message_listview_contextMenuRequested(self,a0,a1,a2):
        print "OverlayDesigner_gui.message_listview_contextMenuRequested( QListViewItem *, const QPoint &, int ): Not implemented yet"


    def editPreferences(self):
        print "OverlayDesigner_gui.editPreferences(): Not implemented yet"


    def message_listview_dropped(self,a0):
        print "OverlayDesigner_gui.message_listview_dropped( QDropEvent * ): Not implemented yet"


    def exportFlat(self):
        print "OverlayDesigner_gui.exportFlat(): Not implemented yet"


    def test_view_select_activated(self,a0):
        print "OverlayDesigner_gui.test_view_select_activated( const QString & ): Not implemented yet"


    def test_run_button_clicked(self):
        print "OverlayDesigner_gui.test_run_button_clicked(): Not implemented yet"


    def test_profile_button_clicked(self):
        print "OverlayDesigner_gui.test_profile_button_clicked(): Not implemented yet"


from genprefdialog import PrefDialog


class OverlayDesigner_prefdialog(PrefDialog):

    def __init__(self,parent = None,name = None,modal = 0,fl = 0):
        PrefDialog.__init__(self,parent,name,modal,fl)

from genstatedialog import EDSMStateDialog


class OverlayDesigner_statedialog(EDSMStateDialog):

    def __init__(self,parent = None,name = None,modal = 0,fl = 0):
        EDSMStateDialog.__init__(self,parent,name,modal,fl)


    def language_name_activated(self,a0):
        print "OverlayDesigner_statedialog.language_name_activated( const QString & ): Not implemented yet"


    def output_queues_selectionChanged(self):
        print "OverlayDesigner_statedialog.output_queues_selectionChanged(): Not implemented yet"


    def input_queues_selectionChanged(self):
        print "OverlayDesigner_statedialog.input_queues_selectionChanged(): Not implemented yet"


    def queue_name_textChanged(self,a0):
        print "OverlayDesigner_statedialog.queue_name_textChanged( const QString & ): Not implemented yet"


    def add_input_queue_button_clicked(self):
        print "OverlayDesigner_statedialog.add_input_queue_button_clicked(): Not implemented yet"


    def add_output_queue_button_clicked(self):
        print "OverlayDesigner_statedialog.add_output_queue_button_clicked(): Not implemented yet"


    def remove_input_queue_button_clicked(self):
        print "OverlayDesigner_statedialog.remove_input_queue_button_clicked(): Not implemented yet"


    def remove_output_queue_button_clicked(self):
        print "OverlayDesigner_statedialog.remove_output_queue_button_clicked(): Not implemented yet"


from gentimerdialog import EDSMTimerDialog


class OverlayDesigner_timerdialog(EDSMTimerDialog):

    def __init__(self,parent = None,name = None,modal = 0,fl = 0):
        EDSMTimerDialog.__init__(self,parent,name,modal,fl)

from gentransitiondialog import EDSMTransitionDialog


class OverlayDesigner_transitiondialog(EDSMTransitionDialog):

    def __init__(self,parent = None,name = None,modal = 0,fl = 0):
        EDSMTransitionDialog.__init__(self,parent,name,modal,fl)


    def language_name_activated(self,a0):
        print "OverlayDesigner_transitiondialog.language_name_activated( const QString & ): Not implemented yet"


    def language_name_activated(self,a0):
        print "OverlayDesigner_transitiondialog.language_name_activated( const QString & ): Not implemented yet"

