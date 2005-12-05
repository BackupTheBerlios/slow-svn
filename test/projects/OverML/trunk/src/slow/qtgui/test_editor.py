STATIC_GLOBALS = globals().copy()
exec 'import random' in STATIC_GLOBALS
exec 'from random import randint' in STATIC_GLOBALS

from StringIO import StringIO
from time import time
from itertools import count, imap
from qt import QStringList, QDialog, QTabWidget, QTextEdit, QVBoxLayout, QSize
from qt_utils import qstrpy, pyqstr

from slow.vis.view_viz import ViewGraph
from slow.pyexec.pydb.views import NodeView, ViewRegistry, PySlosl
from slow.pyexec.pydb.db    import NodeDB, DBNode, LocalNode, PyAttribute

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

_DEFAULT_CODE = '''\
NODES  = 20
MAX_ID = 2**6

for n in range(0, MAX_ID, MAX_ID // NODES):
    buildNode(id=n)

def make_foreign(local_node, attributes):
    """Do something with the node attribute
    dictionary, then return it.  Returning None
    or an empty dict will discard the node."""
    attributes["knows_chord"]   = True
    attributes["alive"]         = True

    dist = attributes["id"] - local_node.id
    if dist < 0:
        dist = MAX_ID + dist
    attributes["local_chorddist"] = dist
    return attributes
'''

class TestRunner(object):
    def __init__(self, status_writer):
        self.static_globals = STATIC_GLOBALS
        self.status = status_writer

    def run_profile(self, slosl_statements, db_attributes, init_code):
        import hotshot, hotshot.stats, os, sys

	stderr = sys.stderr # discard runtime warning for tempnam
	sys.stderr = StringIO()
        prof_filename = os.tempnam(None, 'slow-')
	sys.stderr = stderr

        prof = hotshot.Profile(prof_filename)

        graph = prof.runcall(self.build_graph, slosl_statements,
                             db_attributes, init_code)
        prof.close()
        stats = hotshot.stats.load(prof_filename)
        stats.strip_dirs()

	stdout = sys.stdout

        stats.sort_stats('time', 'calls')
	sys.stdout = StringIO()
        stats.print_stats()
	profile_data = sys.stdout.getvalue()

        stats.sort_stats('cumulative', 'calls')
	sys.stdout = StringIO()
        stats.print_stats()
	self.profile_data = (profile_data, sys.stdout.getvalue())

	sys.stdout = stdout

        os.remove(prof_filename)
        return graph

    def run_test(self, slosl_statements, db_attributes, init_code):
        return self.build_graph(slosl_statements, db_attributes, init_code)

    def build_graph(self, slosl_statements, db_attributes, init_code):
        ids = sorted(a.name for a in db_attributes if a.identifier)
        if not ids:
            raise RuntimeError, "No identifiers specified."

        pyslosl_statements = map(PySlosl, slosl_statements)
        pyattributes       = dict( (a.name, a) for a in imap(PyAttribute, db_attributes) )

        node_setups = []
        all_nodes   = []
        def buildNode(**kwargs):
            try:
                identifiers = tuple(kwargs[id_name] for id_name in ids)
            except KeyError:
                raise RuntimeError, "Node misses id attribute"

            local_node = LocalNode(ids, **kwargs)
            db = NodeDB('db', local_node, pyattributes)
            viewreg = ViewRegistry(db)

            node_setups.append( (local_node, db, viewreg) )
            all_nodes.append(local_node)

        static_globals = self.static_globals.copy()
        static_globals['make_foreign'] = lambda x:x
        static_globals['buildNode']    = buildNode

	for view in pyslosl_statements:
            for varname, pyvalue in view.withs:
                try:
                    static_globals[varname] = eval(pyvalue, static_globals)
		except NameError:
                    pass

        # initialize nodes
        exec init_code in static_globals

        make_foreign = static_globals['make_foreign']
        if not callable(make_foreign):
            make_foreign = lambda x:x

        # copy nodes to all DBs and build node views
        for local_node, local_db, local_viewreg in node_setups:
            for node in all_nodes:
                if node is not local_node:
                    attrs = make_foreign(local_node, dict(vars(node)))
                    if attrs:
                        local_db.addNode( DBNode(local_db, **attrs) )

        views_by_node = []
        for local_node, local_db, local_viewreg in node_setups:
            node_views = []
            for pyslosl in pyslosl_statements:
                node_views.append( NodeView(pyslosl, local_viewreg) )
            views_by_node.append( (local_node, node_views) )

        return ViewGraph(views_by_node).graph


class TestEditor(object):
    def __init__(self):
        self.__setup_child_calls()
        self.__view_tests = {}
        self.__current_test = None
        self.__running = False

        self.__runner = TestRunner(self.__setStatus)

    def __build_svg(self, graph, graphviz_program):
        use_splines = self.test_splines_checkbox.isChecked() and 'true' or 'false'
        return graph.tostring('svg', graphviz_program,
                              overlap='false', fontsize='8',
			      splines=use_splines)

    def activate_test_tab(self):
        slosl_model = self.slosl_model()
        statement_names = sorted(s.name for s in slosl_model.statements)

        combobox = self.test_view_select_combobox
        old_selection = qstrpy( combobox.currentText() )
        combobox.clear()
        strlist = QStringList()
        for name in statement_names:
            strlist.append(name)
        combobox.insertStringList(strlist)

        try:
            current = statement_names.index(old_selection)
        except ValueError:
            if statement_names:
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
        self.__running = True

        current_test = self.test_view_select_combobox.currentText()
        if current_test:
            current_test = qstrpy(current_test)
        if not current_test:
            self.__setStatus(self.__tr("Please select a view to test"))
            return

        slosl_model = self.slosl_model()
        statement = slosl_model.getStatement(current_test)

        if statement:
            attribute_model = self.attribute_model()
            init_code = qstrpy(self.test_init_code.text())

            graphviz_program = self.test_graphviz_program_combobox.currentText()
            if graphviz_program:
                graphviz_program = qstrpy(graphviz_program)
            else:
                graphviz_program = 'neato'

            try:
                t = time()
                result_graph = test_call([statement], attribute_model, init_code)
                t = time() - t

		result = self.__build_svg(result_graph, graphviz_program)
                self.test_view_graph.set_image_data(result)
                self.__setStatus(self.__tr('Generated graph in %1 seconds.').arg(round(t,2)))
            except Exception, e:
                self.__setStatus(e)
        else:
            self.__setStatus(self.__tr("Error: view '%1' not found").arg(current_test))

    def __store_current_code(self):
        if self.__current_test:
            self.__view_tests[self.__current_test] = qstrpy(self.test_init_code.text())

    def test_view_select_activated(self, view_name):
        view_name = qstrpy(view_name)
        self.__store_current_code()
        self.__current_test = view_name

        test_code = self.__view_tests.get(view_name)
        if not test_code:
            test_code = DEFAULT_CODE
        self.test_init_code.setText(pyqstr(test_code))

    def _store_gui_data(self, gui_data):
        self.__store_current_code()
        slosl_model = self.slosl_model()
        for view_name, code in self.__view_tests.iteritems():
            if slosl_model.getStatement(view_name):
                gui_data.setTestCode(view_name, code)

        super(TestEditor, self)._store_gui_data(gui_data)

    def reset_tests(self, code_dict):
        self.__view_tests = code_dict.copy()
        if self.__current_test:
            test_code = self.__view_tests.get(self.__current_test)
            if not test_code:
                test_code = DEFAULT_CODE
            self.test_init_code.setText(pyqstr(test_code))
