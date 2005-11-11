TEMPLATE	= app
LANGUAGE	= C++

CONFIG	+= qt warn_on release

FORMS	= gui.ui \
	aboutdialog.ui \
	timerdialog.ui \
	edsmdialog.ui \
	prefdialog.ui

TRANSLATIONS = ts/gui_de.ts

unix {
  UI_DIR = .ui
  MOC_DIR = .moc
  OBJECTS_DIR = .obj
}
