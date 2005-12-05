/****************************************************************************
** ui.h extension file, included from the uic-generated form implementation.
**
** If you want to add, delete, or rename functions or slots, use
** Qt Designer to update this file, preserving your code.
**
** You should not define a constructor or destructor in this file.
** Instead, write your code in functions called init() and destroy().
** These will automatically be called by the form's constructor and
** destructor.
*****************************************************************************/


void OverlayDesignerMainWindow::fileNew()
{

}


void OverlayDesignerMainWindow::fileOpen()
{

}


void OverlayDesignerMainWindow::fileSave()
{

}


void OverlayDesignerMainWindow::fileSaveAs()
{

}


void OverlayDesignerMainWindow::filePrint()
{

}


void OverlayDesignerMainWindow::fileExit()
{

}


void OverlayDesignerMainWindow::editUndo()
{

}


void OverlayDesignerMainWindow::editRedo()
{

}


void OverlayDesignerMainWindow::editCut()
{

}


void OverlayDesignerMainWindow::editCopy()
{

}


void OverlayDesignerMainWindow::editPaste()
{

}


void OverlayDesignerMainWindow::editFind()
{

}


void OverlayDesignerMainWindow::helpIndex()
{

}


void OverlayDesignerMainWindow::helpContents()
{

}


void OverlayDesignerMainWindow::helpAbout()
{

}


void OverlayDesignerMainWindow::add_or_replace_node_attribute_clicked()
{

}


void OverlayDesignerMainWindow::remove_node_attribute_clicked()
{
        selected_attribute = self.node_attribute_list.selectedItem()
        if selected_attribute:
            self.node_attribute_list.takeItem(selected_attribute)
}


void OverlayDesignerMainWindow::attribute_type_add_or_replace_clicked()
{

}


void OverlayDesignerMainWindow::attribute_type_remove_clicked()
{

}


void OverlayDesignerMainWindow::slosl_foreach_up_button_clicked()
{
    item = self.slosl_foreach_list.selectedItem()
    if item:
        item.moveItem( item.itemAbove() )
}


void OverlayDesignerMainWindow::slosl_foreach_down_button_clicked()
{
    item = self.slosl_foreach_list.selectedItem()
    if item:
        item.moveItem( item.itemBelow() )
}


void OverlayDesignerMainWindow::slosl_foreach_remove_button_clicked()
{
    item = self.slosl_foreach_list.selectedItem()
    if item:
        item.listView().takeItem(item)
}


void OverlayDesignerMainWindow::slosl_apply_button_clicked()
{

}


void OverlayDesignerMainWindow::slosl_add_button_clicked()
{

}


void OverlayDesignerMainWindow::slosl_delete_button_clicked()
{

}


void OverlayDesignerMainWindow::slosl_foreach_apply_button_clicked()
{

}


void OverlayDesignerMainWindow::slosl_rank_function_activated( int )
{

}


void OverlayDesignerMainWindow::node_attribute_name_textChanged( const QString & )
{

}


void OverlayDesignerMainWindow::node_attribute_list_selectionChanged()
{

}


void OverlayDesignerMainWindow::attribute_type_select_activated( const QString & )
{

}



void OverlayDesignerMainWindow::overlay_tab_currentChanged( QWidget * )
{

}


void OverlayDesignerMainWindow::edsm_tool_button_toggled( bool )
{

}


void OverlayDesignerMainWindow::edsm_iconview_contextMenuRequested( QIconViewItem *, const QPoint & )
{

}


void OverlayDesignerMainWindow::slosl_foreach_list_selectionChanged()
{

}


void OverlayDesignerMainWindow::slosl_disable_having( bool )
{
    enabled = not a0 and self.slosl_foreach_list.childCount() > 0
    self.slosl_having.setEnabled(enabled)
    self.slosl_having_textlabel.setEnabled(enabled)
}


void OverlayDesignerMainWindow::slosl_foreach_new_button_clicked()
{
    self.slosl_foreach_list.clearSelection()
    self._current_foreach_entry = None
    self.slosl_foreach_apply_button_clicked()
}


void OverlayDesignerMainWindow::slosl_disable_buttons(bool)
{

}


void OverlayDesignerMainWindow::slosl_view_list_selectionChanged()
{

}


void OverlayDesignerMainWindow::edsm_edit_state( QIconViewItem * )
{

}




void OverlayDesignerMainWindow::type_name_field_textChanged( const QString & )
{

}



void OverlayDesignerMainWindow::node_attribute_type_activated( const QString & )
{

}


void OverlayDesignerMainWindow::message_listview_contextMenuRequested( QListViewItem *, const QPoint &, int )
{

}




void OverlayDesignerMainWindow::editPreferences()
{

}


void OverlayDesignerMainWindow::message_listview_dropped( QDropEvent * )
{

}





void OverlayDesignerMainWindow::exportFlat()
{

}


void OverlayDesignerMainWindow::test_view_select_comboBox_activated( const QString & )
{

}


void OverlayDesignerMainWindow::test_run_button_clicked()
{

}


void OverlayDesignerMainWindow::test_profile_button_clicked()
{

}


