from qt import QCheckBox, QButton, QLineEdit, QTextEdit
from qt_utils import qstrpy, pyqstr

from slow.model.preference_model import buildPreferences
from genprefdialog import PrefDialog

class PreferenceDialog(PrefDialog):
    def __init__(self, parent, store_function, model, name=None, modal=0, fl=0):
        PrefDialog.__init__(self, parent, name, modal, fl)
        self.store_function = store_function
        self.__model = model

    def setModel(self, model):
        self.__model = model
        self.copy_from_model()

    def copy_from_model(self):
        model = self.__model
        for attribute, value in model:
            try: field = getattr(self, attribute)
            except AttributeError:
                continue

            if isinstance(field, QCheckBox):
                field.setChecked( bool(value) )
            elif isinstance(field, QButton):
                field.setDown( bool(value) )
            elif isinstance(field, QLineEdit) or isinstance(field, QTextEdit):
                if isinstance(value, (list, tuple)):
                    value = '\n'.join(v for v in value if v)
                field.setText(pyqstr(value))
            else:
                raise TypeError, "unsupported field type for name '%s': %s" % (attribute, type(field))

    def copy_to_model(self):
        model = self.__model
        for attribute, value in model:
            try: field = getattr(self, attribute)
            except AttributeError:
                continue

            if isinstance(field, QCheckBox):
                value = field.isChecked()
            elif isinstance(field, QButton):
                value = field.isDown()
            elif isinstance(field, QLineEdit):
                value = qstrpy( field.text() )
            elif isinstance(field, QTextEdit):
                value = filter(None, (s.strip() for s in qstrpy(field.text()).split('\n')))
            else:
                raise TypeError, "unsupported field type: %s" % type(field)

            setattr(model, attribute, value)

    def show(self):
        self.copy_from_model()
        PrefDialog.show(self)

    def accept(self):
        PrefDialog.accept(self)
        self.copy_to_model()
        if self.store_function:
            self.store_function(self.__model)
