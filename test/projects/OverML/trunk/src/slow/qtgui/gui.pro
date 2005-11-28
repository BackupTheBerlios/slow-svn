TEMPLATE	= app
LANGUAGE	= C++

CONFIG	+= qt warn_on release

FORMS	= gui.ui \
	aboutdialog.ui \
	timerdialog.ui \
	prefdialog.ui \
	statedialog.ui \
	transitiondialog.ui

TRANSLATIONS = ts/gui_de.ts

unix {
  UI_DIR = .ui
  MOC_DIR = .moc
  OBJECTS_DIR = .obj
}
