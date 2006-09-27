from time import time
from qt import QStringList, QDialog, QTabWidget, QTextEdit, QVBoxLayout, QSize
from qt_utils import qstrpy, pyqstr

from slow.vis.view_viz import ViewGraph
from slow.pyexec.runner import TestRunner

DEFAULT_CODE = '''\
NODES = 10

for n in range(NODES):
    "build a new node using buildNode(...)"
    

def make_foreign(local_node, attributes):
    """Do something with the node attribute
    dictionary, then return it.  Returning None
    or an empty dict will not add the node."""
    return attributes
    
'''

class TestEditor(object):
    def __init__(self):
        self.__setup_child_calls()
        self.__tests = None
        self.__current_test = None
        self.__running = False

        self.__runner = TestRunner(self.__setStatus)

    def __build_svg(self, graph, graphviz_program):
        use_splines = self.test_splines_checkbox.isChecked() and 'true' or 'false'
        return graph.tostring('svg', graphviz_program,
                              overlap='false', fontsize='8',
                              splines=use_splines)

    def activate_test_tab(self):
        test_cases = sorted(test.name for test in self.__tests.test_list)
        self.__resetCombobox(self.test_select_combobox, test_cases)
        self.__current_test = qstrpy(self.test_select_combobox.currentText())

        statement_names = sorted(s.name for s in self.slosl_model().statements)
        self.__resetCombobox(self.test_view_select_combobox, statement_names)

        test_code = self.__tests.getTestCode(self.__current_test)
        self.test_init_code.setText(pyqstr(test_code))

    def __resetCombobox(self, combobox, lines):
        old_selection = qstrpy( combobox.currentText() )
        combobox.clear()
        strlist = QStringList()
        for line in lines:
            strlist.append(line)
        combobox.insertStringList(strlist)

        try:
            current = lines.index(old_selection)
        except ValueError:
            if lines:
                current = 0
            else:
                current = -1
        combobox.setCurrentItem(current)

    def __setup_child_calls(self):
        try:
            self.__setStatus = self.setStatus
        except AttributeError:
            def dummy(*args):
                pass
            self.__setStatus = dummy

        try:
            self.__tr = self.tr
        except AttributeError:
            def dummy(self, arg):
                return arg
            self.__tr = dummy

    def __stop_test(self):
        self.__running = False

    def test_profile_button_clicked(self):
        self.__run_test(self.__runner.run_profile)
        profile = self.__runner.profile_data

        dialog = QDialog(self)

        tabs = QTabWidget(dialog)

        for i, output in enumerate(profile):
            browser = QTextEdit(tabs, 'profile')
            browser.setReadOnly(True)
            browser.setWordWrap(browser.NoWrap)
            browser.setTextFormat(browser.PlainText)
            browser.setFamily('Monospace')
            browser.setText(output)
            tabs.addTab(browser, "profile %d" % i)

        layout = QVBoxLayout(dialog, 1, 1, "DialogLayout")
        layout.setResizeMode(QVBoxLayout.FreeResize)
        layout.addWidget(tabs)

        dialog.setCaption(self.tr("Profile"))
        dialog.setMinimumSize(QSize(400,500))

        dialog.show()

    def test_run_button_clicked(self):
        self.__run_test(self.__runner.run_test)

    def __run_test(self, test_call):
        if self.__running:
            self.__stop_test()
        self.__store_current_code()
        self.__running = True

        init_code = None
        if self.__current_test:
            init_code = self.__tests.getTestCode(self.__current_test)
        if not init_code:
            self.__setStatus(self.__tr("Please select a test case"))
            return

        current_view = qstrpy(self.test_view_select_combobox.currentText())
        if not current_view:
            self.__setStatus(self.__tr("Please select a view to test"))
            return

        slosl_model = self.slosl_model()
        statement = slosl_model.getStatement(current_view)

        if statement:
            attribute_model = self.attribute_model()
            graphviz_program = self.test_graphviz_program_combobox.currentText()
            if graphviz_program:
                graphviz_program = qstrpy(graphviz_program)
            else:
                graphviz_program = 'neato'

            try:
                t = time()
                views = test_call([statement], attribute_model, init_code)
                t_views = time() - t

                t = time()
                result_graph = ViewGraph(views).graph
                result = self.__build_svg(result_graph, graphviz_program)
                t_graph = time() - t

                self.test_view_graph.set_image_data(result)
                self.__setStatus(self.__tr(
			'Generated views in %1 seconds, graph in %1 seconds.'
			).arg(round(t_views,2)).arg(round(t_graph,2)))
            except Exception, e:
                self.__setStatus(e)
        else:
            self.__setStatus(self.__tr("Error: view '%1' not found").arg(current_view))

    def __store_current_code(self):
        if self.__current_test:
            text = qstrpy(self.test_init_code.text())
            if not text.strip() or text == DEFAULT_CODE:
                text = ''
            current_test = self.__tests.setTestCode(self.__current_test, text)

    def test_select_activated(self, test_name):
        test_name = qstrpy(test_name)
        self.__store_current_code()
        self.__current_test = test_name
        test_code = self.__tests.getTestCode(self.__current_test)
        self.test_init_code.setText(pyqstr(test_code))

    def _store_gui_data(self, gui_data):
        self.__store_current_code()
        super(TestEditor, self)._store_gui_data(gui_data)

    def reset_tests(self, gui_data):
        self.__tests = gui_data
        if self.__current_test:
            test_code = gui_data.getTestCode(self.__current_test)
            if test_code:
                self.test_init_code.setText(pyqstr(test_code))
