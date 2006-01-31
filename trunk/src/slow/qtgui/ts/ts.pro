FORMS	= gui.ui \
	aboutdialog.ui \
	timerdialog.ui \
	statedialog.ui \
	transitiondialog.ui \
	prefdialog.ui

SOURCES	= gui.py \
	attribute_editor.py \
	custom_widgets.py \
	edsm_editor.py \
	message_editor.py \
	popupmenu.py \
	qt_utils.py \
	slosl_editor.py \
	\
	gengui.py \
	genaboutdialog.py \
	gentimerdialog.py \
	genstatedialog.py \
	gentransitiondialog.py \
        genprefdialog.py
	

TRANSLATIONS =	ts/gui_de.ts \
		ts/gui_fr.ts \
		ts/gui_mock.ts

unix {
  UI_DIR = .ui
  MOC_DIR = .moc
  OBJECTS_DIR = .obj
}
